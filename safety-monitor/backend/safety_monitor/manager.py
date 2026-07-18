"""Camera manager: capture loops, privacy masking, and the analysis pipeline.

Pipeline per camera, every `capture_interval_seconds`:
  read frame -> apply privacy masks -> motion detection -> vision provider
  -> rule engine -> store event (+snapshot/clip if recording enabled)
  -> broadcast to UI websocket -> dispatch to agent hooks.

Privacy notes:
- Mask zones are blacked out *before* analysis, storage or streaming, so
  masked pixels never leave this function.
- When paused, no frames are read at all; the preview shows a placeholder.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from collections import deque
from typing import Awaitable, Callable

import numpy as np
from PIL import Image, ImageDraw

from .agent_hook import AgentGateway
from .camera_sources import FRAME_H, FRAME_W, CameraSource, create_source
from .config import ConfigStore
from .models import CameraSettings, Event
from .motion import MotionDetector
from .rules import RuleEngine
from .store import EventStore
from .vision import (
    AnalysisContext,
    UnavailableVisionProvider,
    VisionProvider,
    create_provider,
)

logger = logging.getLogger(__name__)

PREVIEW_FPS = 8
CLIP_FRAMES = 8  # frames kept around an event as a mini "clip"

EventCallback = Callable[[Event], Awaitable[None]]


def apply_masks(frame: np.ndarray, camera: CameraSettings) -> np.ndarray:
    """Black out mask zones in place (normalized zone coords)."""
    h, w = frame.shape[:2]
    for zone in camera.mask_zones:
        x0 = max(0, int(zone.x * w))
        y0 = max(0, int(zone.y * h))
        x1 = min(w, int((zone.x + zone.w) * w))
        y1 = min(h, int((zone.y + zone.h) * h))
        frame[y0:y1, x0:x1] = 0
    return frame


def placeholder_frame(text: str) -> bytes:
    img = Image.new("RGB", (FRAME_W, FRAME_H), (24, 24, 28))
    draw = ImageDraw.Draw(img)
    draw.text((FRAME_W // 2 - 60, FRAME_H // 2 - 8), text, fill=(160, 160, 170))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, "JPEG", quality=quality)
    return buf.getvalue()


class CameraWorker:
    """Owns one camera source and runs its capture/analysis loop."""

    def __init__(
        self,
        camera: CameraSettings,
        config: ConfigStore,
        store: EventStore,
        rules: RuleEngine,
        provider: VisionProvider,
        gateway: AgentGateway,
        on_event: EventCallback,
    ):
        self.camera = camera
        self.config = config
        self.store = store
        self.rules = rules
        self.provider = provider
        self.gateway = gateway
        self.on_event = on_event

        self.motion = MotionDetector(config.settings.motion_sensitivity)
        self.source: CameraSource | None = None
        self.error: str | None = None
        self.latest_jpeg: bytes = placeholder_frame("starting...")
        self._ring: deque[np.ndarray] = deque(maxlen=CLIP_FRAMES)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"camera-{self.camera.id}")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
        if self.source:
            await asyncio.to_thread(self.source.close)
            self.source = None

    async def _open_source(self) -> bool:
        try:
            self.source = await asyncio.to_thread(
                create_source, self.camera.source_type, self.camera.device_index
            )
            self.error = None
            return True
        except Exception as exc:
            self.error = str(exc)
            self.latest_jpeg = placeholder_frame("camera unavailable")
            logger.error("camera %s failed to open: %s", self.camera.id, exc)
            return False

    async def _run(self) -> None:
        if not await self._open_source():
            return
        last_analysis = 0.0
        while not self._stop.is_set():
            settings = self.config.settings
            if settings.paused:
                self.latest_jpeg = placeholder_frame("paused")
                self.motion.reset()
                self._ring.clear()
                await asyncio.sleep(0.5)
                continue

            frame = await asyncio.to_thread(self.source.read)
            if frame is None:
                self.latest_jpeg = placeholder_frame("no signal")
                await asyncio.sleep(1.0)
                continue

            # Privacy masking happens before anything else sees the frame.
            frame = apply_masks(frame, self.camera)
            self.latest_jpeg = encode_jpeg(frame)

            now = time.monotonic()
            if now - last_analysis >= settings.capture_interval_seconds:
                last_analysis = now
                self._ring.append(frame)
                try:
                    await self._analyze(frame)
                except Exception:
                    logger.exception("analysis failed for camera %s", self.camera.id)

            await asyncio.sleep(1.0 / PREVIEW_FPS)

    async def _analyze(self, frame: np.ndarray) -> None:
        settings = self.config.settings
        self.motion.sensitivity = settings.motion_sensitivity
        motion = self.motion.process(frame)
        context = AnalysisContext(camera_id=self.camera.id, motion=motion)
        analysis = await self.provider.analyze(frame, context)
        events = self.rules.evaluate(self.camera, motion, analysis, settings)

        for event in events:
            snapshot = frame if settings.recording_enabled else None
            clip = list(self._ring) if settings.recording_enabled else None
            self.store.add(event, snapshot=snapshot, clip_frames=clip)

            assessments = await self.gateway.dispatch(event)
            for assessment in assessments:
                self.store.set_assessment(event.id, assessment)
                event.agent_assessment = assessment
                self.gateway.resolve(event.id)

            await self.on_event(event)


class CameraManager:
    """Creates and supervises a CameraWorker per enabled camera."""

    def __init__(
        self,
        config: ConfigStore,
        store: EventStore,
        gateway: AgentGateway,
        on_event: EventCallback,
    ):
        self.config = config
        self.store = store
        self.gateway = gateway
        self.on_event = on_event
        self.rules = RuleEngine()
        self.provider: VisionProvider
        self.provider_error: str | None = None
        self._create_provider()
        self.workers: dict[str, CameraWorker] = {}

    def _create_provider(self) -> None:
        """Create the configured provider; on failure of a REAL provider,
        run with no analysis (never a mock fallback) and surface the error."""
        settings = self.config.settings
        models_dir = settings.models_dir or str(self.config.data_dir / "models")
        try:
            self.provider = create_provider(
                settings.ai_provider,
                mock_demo_cycle=settings.mock_demo_cycle,
                models_dir=models_dir,
            )
            self.provider_error = None
        except Exception as exc:
            self.provider_error = str(exc)
            self.provider = UnavailableVisionProvider(settings.ai_provider, str(exc))
            logger.error(
                "vision provider %r failed to load — AI analysis is OFF, "
                "no simulated fallback: %s",
                settings.ai_provider,
                exc,
            )

    async def reload_provider(self) -> None:
        """Swap providers after a settings change (mock <-> onnx etc.)."""
        old = self.provider
        self._create_provider()
        for worker in self.workers.values():
            worker.provider = self.provider
        await old.close()

    async def start(self) -> None:
        for camera in self.config.settings.cameras:
            if camera.enabled:
                self._start_worker(camera)

    def _start_worker(self, camera: CameraSettings) -> None:
        worker = CameraWorker(
            camera,
            self.config,
            self.store,
            self.rules,
            self.provider,
            self.gateway,
            self.on_event,
        )
        self.workers[camera.id] = worker
        worker.start()

    async def stop(self) -> None:
        await asyncio.gather(*(w.stop() for w in self.workers.values()))
        self.workers.clear()
        await self.provider.close()

    async def apply_settings(self, previous_cameras: list[CameraSettings]) -> None:
        """Restart workers whose camera config changed; start/stop as needed."""
        prev = {c.id: c for c in previous_cameras}
        current = {c.id: c for c in self.config.settings.cameras}

        for cam_id in list(self.workers):
            cam = current.get(cam_id)
            if cam is None or not cam.enabled or cam != prev.get(cam_id):
                await self.workers[cam_id].stop()
                del self.workers[cam_id]
                self.rules.reset(cam_id)

        for cam_id, cam in current.items():
            if cam.enabled and cam_id not in self.workers:
                self._start_worker(cam)

    def worker(self, camera_id: str) -> CameraWorker | None:
        return self.workers.get(camera_id)

    async def mjpeg_stream(self, camera_id: str):
        """Async generator yielding multipart JPEG chunks for live preview."""
        boundary = b"--frame"
        while True:
            worker = self.workers.get(camera_id)
            jpeg = worker.latest_jpeg if worker else placeholder_frame("offline")
            yield (
                boundary
                + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpeg)).encode()
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
            await asyncio.sleep(1.0 / PREVIEW_FPS)
