"""Camera sources.

Two implementations:
- WebcamSource: real camera via OpenCV (optional dependency).
- SyntheticSource: generated frames with a moving figure, so the whole
  pipeline can run and be demoed with no camera hardware installed.
"""

from __future__ import annotations

import math
import threading
import time
from abc import ABC, abstractmethod

import numpy as np

try:
    import cv2  # type: ignore

    HAS_OPENCV = True
except ImportError:  # pragma: no cover - depends on environment
    cv2 = None
    HAS_OPENCV = False

FRAME_W, FRAME_H = 640, 480


class CameraSource(ABC):
    """A source of RGB frames (H, W, 3) uint8."""

    @abstractmethod
    def read(self) -> np.ndarray | None:
        """Return the current frame, or None if unavailable."""

    def close(self) -> None:  # pragma: no cover - trivial
        pass


class WebcamSource(CameraSource):
    def __init__(self, device_index: int = 0):
        if not HAS_OPENCV:
            raise RuntimeError(
                "OpenCV is not installed. Install with: pip install opencv-python"
            )
        self._cap = cv2.VideoCapture(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open camera device {device_index}")

    def read(self) -> np.ndarray | None:
        ok, frame_bgr = self._cap.read()
        if not ok:
            return None
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def close(self) -> None:
        self._cap.release()


class SyntheticSource(CameraSource):
    """Renders a simple room scene with a figure that wanders around.

    The figure periodically pauses and occasionally 'lies down', which
    exercises the motion detector and gives the mock vision provider
    plausible activity to react to.
    """

    def __init__(self, seed: int = 0):
        self._t0 = time.monotonic()
        self._rng = np.random.default_rng(seed)
        self._background = self._make_background()

    def _make_background(self) -> np.ndarray:
        bg = np.full((FRAME_H, FRAME_W, 3), 38, dtype=np.uint8)
        # floor
        bg[FRAME_H * 2 // 3 :, :] = (55, 48, 42)
        # "door" on the right edge
        bg[120:360, FRAME_W - 70 : FRAME_W - 20] = (70, 52, 36)
        # "stove" block bottom-left
        bg[FRAME_H - 130 : FRAME_H - 60, 40:160] = (60, 60, 66)
        return bg

    def read(self) -> np.ndarray | None:
        t = time.monotonic() - self._t0
        frame = self._background.copy()

        # Figure wanders on a slow Lissajous path; freezes every ~20s for 6s.
        phase = t % 26.0
        moving = phase < 20.0
        tt = t if moving else (t - (phase - 20.0))
        cx = int(FRAME_W / 2 + FRAME_W / 3 * math.sin(tt * 0.35))
        cy = int(FRAME_H * 0.55 + FRAME_H / 6 * math.sin(tt * 0.22 + 1.3))

        # Occasionally "lies down" (horizontal figure) during the frozen phase.
        lying = not moving and int(t / 26.0) % 3 == 1
        half_w, half_h = (60, 18) if lying else (18, 60)

        y0, y1 = max(0, cy - half_h), min(FRAME_H, cy + half_h)
        x0, x1 = max(0, cx - half_w), min(FRAME_W, cx + half_w)
        frame[y0:y1, x0:x1] = (205, 190, 170)

        # sensor noise so consecutive frames are never identical
        noise = self._rng.integers(-4, 5, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return frame


class MjpegSource(CameraSource):
    """Bounded network camera source: an MJPEG-over-HTTP stream on the LAN.

    Works with anything that serves multipart JPEG — phone/tablet "IP
    camera" apps, ESP32-cams, Linux boxes serving a USB camera, another
    safety-monitor instance. Credentials in the URL (http://user:pass@...)
    are honoured.

    Bounds (this is a safety product; a hostile or broken stream must not
    hurt the pipeline):
    - http/https URLs only, connect/read timeouts, no unbounded buffering
      (rolling buffer capped at MAX_PART_BYTES; oversized parts dropped);
    - frames larger than MAX_DIM pixels per side are rejected;
    - decode via PIL from bytes — the stream never touches the filesystem;
    - a background reader keeps only the LATEST frame; if the stream
      stalls longer than STALE_AFTER, read() reports no signal while the
      reader reconnects with backoff.
    """

    CONNECT_TIMEOUT = 8.0
    READ_TIMEOUT = 10.0
    MAX_PART_BYTES = 12 * 1024 * 1024  # cap on one JPEG part / rolling buffer
    MAX_DIM = 4096  # reject absurd frame dimensions
    DOWNSCALE_TO = 1280  # keep pipeline memory sane for hi-res cameras
    STALE_AFTER = 6.0  # seconds without a fresh frame -> "no signal"
    RECONNECT_DELAY = 2.0

    def __init__(self, url: str):
        from urllib.parse import urlparse

        scheme = urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            raise RuntimeError("MJPEG camera URL must start with http:// or https://")
        self.url = url
        self._latest: np.ndarray | None = None
        self._latest_ts = 0.0
        self._error: str | None = "connecting"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._reader, name="mjpeg-reader", daemon=True
        )
        self._thread.start()

    # --- background reader ---------------------------------------------------

    def _reader(self) -> None:
        import httpx

        while not self._stop.is_set():
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(self.READ_TIMEOUT, connect=self.CONNECT_TIMEOUT)
                ) as client:
                    with client.stream("GET", self.url) as resp:
                        resp.raise_for_status()
                        self._consume(resp)
            except Exception as exc:  # noqa: BLE001 - reconnect on any stream error
                with self._lock:
                    self._error = str(exc)
            self._stop.wait(self.RECONNECT_DELAY)

    def _consume(self, resp) -> None:
        """Scan the byte stream for JPEG frames (SOI..EOI), bounded."""
        buffer = b""
        for chunk in resp.iter_bytes():
            if self._stop.is_set():
                return
            buffer += chunk
            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    buffer = buffer[-1:]  # keep possible split marker byte
                    break
                end = buffer.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if len(buffer) - start > self.MAX_PART_BYTES:
                        buffer = b""  # oversized part: drop, stay bounded
                    else:
                        buffer = buffer[start:]
                    break
                self._decode(buffer[start : end + 2])
                buffer = buffer[end + 2 :]
            if len(buffer) > self.MAX_PART_BYTES:
                buffer = b""

    def _decode(self, jpeg: bytes) -> None:
        import io

        from PIL import Image

        try:
            img = Image.open(io.BytesIO(jpeg))
            if img.width > self.MAX_DIM or img.height > self.MAX_DIM:
                return
            if max(img.width, img.height) > self.DOWNSCALE_TO:
                img.thumbnail((self.DOWNSCALE_TO, self.DOWNSCALE_TO))
            frame = np.asarray(img.convert("RGB"))
        except Exception:  # corrupt part: skip it, keep streaming
            return
        with self._lock:
            self._latest = frame
            self._latest_ts = time.monotonic()
            self._error = None

    # --- CameraSource interface ------------------------------------------------

    def read(self) -> np.ndarray | None:
        with self._lock:
            if self._latest is None:
                return None
            if time.monotonic() - self._latest_ts > self.STALE_AFTER:
                return None  # stalled stream: honest "no signal", never a stale frame
            return self._latest

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3.0)


def create_source(
    source_type: str, device_index: int = 0, url: str = ""
) -> CameraSource:
    if source_type == "webcam":
        return WebcamSource(device_index)
    if source_type == "synthetic":
        return SyntheticSource(seed=device_index)
    if source_type == "mjpeg":
        if not url:
            raise RuntimeError("MJPEG camera needs a stream URL (set it in Settings)")
        return MjpegSource(url)
    raise ValueError(f"Unknown camera source type: {source_type}")
