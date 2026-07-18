"""FastAPI application: REST API + WebSocket for the desktop app and agents."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import __version__
from .agent_hook import AgentGateway, AgentWebhook
from .camera_sources import PhoneSource
from .config import ConfigStore
from .manager import CameraManager
from .models import AgentAssessment, CameraSettings, Event, Settings, Zone
from .pairing import PAIRING_TTL, PairingManager, lan_ip, new_device_key
from .phone_page import PHONE_PAGE
from .store import EventStore

logger = logging.getLogger(__name__)


class PhoneSurfaceApp:
    """ASGI wrapper exposing ONLY the phone-camera surface.

    The LAN-facing HTTPS listener wraps the app in this, so a device on
    the network can reach the pairing page, the claim endpoint and the
    frame websocket — and nothing else. The full API stays loopback-only.
    """

    ALLOWED_HTTP_PREFIXES = ("/pair/", "/phone-camera", "/api/pairing/claim")
    ALLOWED_WS_PREFIXES = ("/ws/phone/",)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if any(path.startswith(p) for p in self.ALLOWED_HTTP_PREFIXES):
                return await self.app(scope, receive, send)
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"not found"})
            return
        if scope["type"] == "websocket":
            path = scope.get("path", "")
            if any(path.startswith(p) for p in self.ALLOWED_WS_PREFIXES):
                return await self.app(scope, receive, send)
            await send({"type": "websocket.close", "code": 4404})
            return
        return await self.app(scope, receive, send)


class WebSocketHub:
    """Broadcasts events to all connected desktop-app clients."""

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(ws)


# --- request bodies ---------------------------------------------------------


class PauseRequest(BaseModel):
    paused: bool


class RecordingRequest(BaseModel):
    enabled: bool


class ZonesRequest(BaseModel):
    mask_zones: list[Zone] | None = None
    restricted_zones: list[Zone] | None = None


class EmergencyActionRequest(BaseModel):
    event_id: str
    action: str  # e.g. "notify_contact"
    confirmed: bool = False  # must be true; set only after an explicit user dialog


class WebhookRequest(BaseModel):
    name: str
    url: str


class PairingClaimRequest(BaseModel):
    token: str
    name: str = "Phone camera"


def create_app(data_dir: Path | None = None) -> FastAPI:
    config = ConfigStore(data_dir)
    store = EventStore(
        config.data_dir / "events.db", config.snapshots_dir, config.clips_dir
    )
    hub = WebSocketHub()
    gateway = AgentGateway()
    pairing = PairingManager()

    async def on_event(event: Event) -> None:
        await hub.broadcast({"kind": "event", "event": event.model_dump(mode="json")})

    manager = CameraManager(config, store, gateway, on_event)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await manager.start()
        yield
        await manager.stop()
        store.close()

    app = FastAPI(
        title="Safety Monitor Backend", version=__version__, lifespan=lifespan
    )
    app.state.config = config
    app.state.store = store
    app.state.gateway = gateway
    app.state.manager = manager

    # The Electron renderer runs from vite (http://localhost:5173) in dev
    # and from file:// in production builds; only local origins are allowed.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(http://(localhost|127\.0\.0\.1)(:\d+)?|file://.*)$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- health / settings ---------------------------------------------------

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "version": __version__,
            "paused": config.settings.paused,
            "cameras": {
                cam_id: {"error": w.error} for cam_id, w in manager.workers.items()
            },
            "vision": {
                "provider": manager.provider.name,
                "configured": config.settings.ai_provider,
                "real": manager.provider.name == "local",
                "error": manager.provider_error,
            },
        }

    @app.get("/api/settings", response_model=Settings)
    async def get_settings():
        return config.settings

    @app.put("/api/settings", response_model=Settings)
    async def put_settings(new_settings: Settings):
        previous = config.settings
        config.update(new_settings)
        await manager.apply_settings(previous.cameras)
        if (
            new_settings.ai_provider != previous.ai_provider
            or new_settings.mock_demo_cycle != previous.mock_demo_cycle
            or new_settings.models_dir != previous.models_dir
        ):
            await manager.reload_provider()
        return config.settings

    # --- cameras --------------------------------------------------------------

    @app.get("/api/cameras", response_model=list[CameraSettings])
    async def list_cameras():
        return config.settings.cameras

    @app.post("/api/cameras", response_model=CameraSettings)
    async def add_camera(camera: CameraSettings):
        previous = list(config.settings.cameras)
        config.settings.cameras.append(camera)
        config.save()
        await manager.apply_settings(previous)
        return camera

    @app.delete("/api/cameras/{camera_id}")
    async def delete_camera(camera_id: str):
        previous = list(config.settings.cameras)
        remaining = [c for c in config.settings.cameras if c.id != camera_id]
        if len(remaining) == len(previous):
            raise HTTPException(404, "camera not found")
        config.settings.cameras = remaining
        config.save()
        await manager.apply_settings(previous)
        return {"deleted": camera_id}

    def _get_camera(camera_id: str) -> CameraSettings:
        for cam in config.settings.cameras:
            if cam.id == camera_id:
                return cam
        raise HTTPException(404, "camera not found")

    @app.get("/api/cameras/{camera_id}/stream")
    async def camera_stream(camera_id: str):
        _get_camera(camera_id)
        return StreamingResponse(
            manager.mjpeg_stream(camera_id),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/api/cameras/{camera_id}/snapshot.jpg")
    async def camera_snapshot(camera_id: str):
        _get_camera(camera_id)
        worker = manager.worker(camera_id)
        if worker is None:
            raise HTTPException(409, "camera is not running")
        return Response(worker.latest_jpeg, media_type="image/jpeg")

    @app.put("/api/cameras/{camera_id}/zones", response_model=CameraSettings)
    async def put_zones(camera_id: str, body: ZonesRequest):
        camera = _get_camera(camera_id)
        previous = [c.model_copy(deep=True) for c in config.settings.cameras]
        if body.mask_zones is not None:
            camera.mask_zones = body.mask_zones
        if body.restricted_zones is not None:
            camera.restricted_zones = body.restricted_zones
        config.save()
        await manager.apply_settings(previous)
        return camera

    # --- privacy controls -------------------------------------------------------

    @app.post("/api/privacy/pause")
    async def set_paused(body: PauseRequest):
        config.settings.paused = body.paused
        config.save()
        return {"paused": config.settings.paused}

    @app.post("/api/privacy/recording")
    async def set_recording(body: RecordingRequest):
        config.settings.recording_enabled = body.enabled
        config.save()
        return {"recording_enabled": config.settings.recording_enabled}

    @app.delete("/api/history")
    async def delete_history():
        deleted = store.delete_all()
        await hub.broadcast({"kind": "history_deleted"})
        return {"deleted_events": deleted}

    # --- events -------------------------------------------------------------------

    @app.get("/api/events", response_model=list[Event])
    async def list_events(
        camera_id: str | None = None,
        type: str | None = None,
        since: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        return store.list(
            camera_id=camera_id,
            event_type=type,
            since=since,
            limit=min(limit, 500),
            offset=offset,
        )

    @app.get("/api/events/{event_id}", response_model=Event)
    async def get_event(event_id: str):
        event = store.get(event_id)
        if event is None:
            raise HTTPException(404, "event not found")
        return event

    @app.post("/api/events/{event_id}/ack")
    async def acknowledge_event(event_id: str):
        if not store.acknowledge(event_id):
            raise HTTPException(404, "event not found")
        return {"acknowledged": event_id}

    @app.get("/api/events/{event_id}/snapshot.jpg")
    async def event_snapshot(event_id: str):
        event = store.get(event_id)
        if event is None or not event.snapshot_path:
            raise HTTPException(404, "snapshot not found")
        path = Path(event.snapshot_path)
        if not path.exists():
            raise HTTPException(404, "snapshot file missing")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/api/events/{event_id}/frames")
    async def event_frames(event_id: str):
        event = store.get(event_id)
        if event is None:
            raise HTTPException(404, "event not found")
        if not event.clip_dir or not Path(event.clip_dir).exists():
            return {"frames": []}
        frames = sorted(p.name for p in Path(event.clip_dir).glob("*.jpg"))
        return {
            "frames": [
                f"/api/events/{event_id}/frames/{name}" for name in frames
            ]
        }

    @app.get("/api/events/{event_id}/frames/{frame_name}")
    async def event_frame(event_id: str, frame_name: str):
        event = store.get(event_id)
        if event is None or not event.clip_dir:
            raise HTTPException(404, "event not found")
        path = (Path(event.clip_dir) / frame_name).resolve()
        if path.parent != Path(event.clip_dir).resolve() or not path.exists():
            raise HTTPException(404, "frame not found")
        return FileResponse(path, media_type="image/jpeg")

    # --- agent integration -----------------------------------------------------------

    @app.post("/api/agent/webhooks")
    async def register_webhook(body: WebhookRequest):
        gateway.register_webhook(AgentWebhook(name=body.name, url=body.url))
        return {"registered": body.name}

    @app.delete("/api/agent/webhooks/{name}")
    async def remove_webhook(name: str):
        if not gateway.remove_webhook(name):
            raise HTTPException(404, "webhook not found")
        return {"removed": name}

    @app.get("/api/agent/webhooks")
    async def list_webhooks():
        return list(gateway.webhooks.values())

    @app.get("/api/agent/pending")
    async def pending_events():
        return [gateway.payload_for(e).model_dump(mode="json") for e in gateway.pending()]

    @app.post("/api/agent/assessments")
    async def submit_assessment(assessment: AgentAssessment):
        if store.get(assessment.event_id) is None:
            raise HTTPException(404, "event not found")
        store.set_assessment(assessment.event_id, assessment)
        gateway.resolve(assessment.event_id)
        await hub.broadcast(
            {"kind": "assessment", "assessment": assessment.model_dump(mode="json")}
        )
        return {"stored": assessment.event_id}

    # --- emergency-style actions (require explicit user confirmation) ------------------

    @app.post("/api/actions/emergency")
    async def emergency_action(body: EmergencyActionRequest):
        event = store.get(body.event_id)
        if event is None:
            raise HTTPException(404, "event not found")
        if not body.confirmed:
            # Hard requirement: the UI must show a confirmation dialog and
            # only set confirmed=true after the user explicitly approves.
            raise HTTPException(
                428, "user confirmation required before emergency actions"
            )
        # MVP: record and broadcast the confirmed action. Extension point:
        # notify an emergency contact via a user-configured local channel.
        logger.warning(
            "user-confirmed emergency action %r for event %s", body.action, event.id
        )
        await hub.broadcast(
            {
                "kind": "emergency_action",
                "event_id": event.id,
                "action": body.action,
            }
        )
        return {"executed": body.action, "event_id": event.id}

    # --- phone pairing ------------------------------------------------------------------

    def phone_base_url() -> str:
        configured = getattr(app.state, "phone_base_url", None)
        return configured or f"http://{lan_ip()}:8765"

    @app.post("/api/pairing/start")
    async def pairing_start():
        entry = pairing.start()
        return {
            "token": entry.token,
            "url": f"{phone_base_url()}/pair/{entry.token}",
            "expires_in": int(PAIRING_TTL),
        }

    @app.get("/api/pairing/{token}")
    async def pairing_status(token: str):
        return pairing.status(token)

    @app.get("/api/pairing/{token}/qr.png")
    async def pairing_qr(token: str):
        if pairing.get(token) is None:
            raise HTTPException(404, "Pairing code expired — start again")
        import io

        import qrcode

        img = qrcode.make(f"{phone_base_url()}/pair/{token}")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png")

    @app.post("/api/pairing/claim")
    async def pairing_claim(body: PairingClaimRequest):
        entry = pairing.get(body.token)
        if entry is None or entry.claimed_camera_id:
            raise HTTPException(
                410, "Pairing code expired or already used"
            )
        camera = CameraSettings(
            name=body.name.strip()[:60] or "Phone camera",
            source_type="phone",
            device_key=new_device_key(),
        )
        previous = config.settings.cameras
        config.settings.cameras.append(camera)
        config.save()
        pairing.claim(body.token, camera.id)
        await manager.apply_settings(previous)
        logger.info("paired phone camera %s (%r)", camera.id, camera.name)
        return {
            "camera_id": camera.id,
            "device_key": camera.device_key,
            "name": camera.name,
        }

    @app.get("/pair/{token}", response_class=HTMLResponse)
    async def pair_page(token: str):
        if pairing.get(token) is None:
            return HTMLResponse(
                "<h3 style='font-family:system-ui;padding:2rem'>Pairing link expired."
                "<br>Open the desktop app and generate a fresh QR code.</h3>",
                status_code=410,
            )
        return HTMLResponse(PHONE_PAGE)

    @app.get("/phone-camera", response_class=HTMLResponse)
    async def phone_camera_page():
        # resume page for already-paired devices (credentials in localStorage)
        return HTMLResponse(PHONE_PAGE)

    @app.websocket("/ws/phone/{camera_id}")
    async def ws_phone(ws: WebSocket, camera_id: str):
        await ws.accept()
        camera = next(
            (c for c in config.settings.cameras if c.id == camera_id), None
        )
        if camera is None or camera.source_type != "phone" or not camera.device_key:
            await ws.close(code=4401)
            return
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
        except Exception:
            await ws.close(code=4400)
            return
        import secrets as _secrets

        if not _secrets.compare_digest(
            str(first.get("device_key", "")), camera.device_key
        ):
            await ws.close(code=4401)
            return

        try:
            while True:
                data = await ws.receive_bytes()
                worker = manager.worker(camera_id)
                if worker is None:  # camera deleted or disabled mid-stream
                    await ws.close(code=4401)
                    return
                frame = await asyncio.to_thread(PhoneSource.decode_jpeg_bounded, data)
                if frame is not None and isinstance(worker.source, PhoneSource):
                    worker.source.push(frame)
        except WebSocketDisconnect:
            pass

    # --- websocket ---------------------------------------------------------------------

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket):
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()  # keepalive pings from the client
        except WebSocketDisconnect:
            await hub.disconnect(ws)

    return app
