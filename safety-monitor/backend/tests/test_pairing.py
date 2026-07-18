"""Tests for phone pairing and the phone frame-ingest websocket."""

from __future__ import annotations

import io
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from safety_monitor import pairing as pairing_mod
from safety_monitor.app import PhoneSurfaceApp, create_app
from safety_monitor.camera_sources import PhoneSource
from safety_monitor.pairing import PairingManager


@pytest.fixture()
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        yield client


def jpeg_bytes(color=(120, 40, 40), size=(320, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=85)
    return buf.getvalue()


# --- token lifecycle ----------------------------------------------------------


def test_pairing_start_returns_token_and_url(client):
    data = client.post("/api/pairing/start").json()
    assert data["token"]
    assert f"/pair/{data['token']}" in data["url"]
    assert client.get(f"/api/pairing/{data['token']}").json() == {"status": "pending"}


def test_claim_creates_phone_camera_with_device_key(client):
    token = client.post("/api/pairing/start").json()["token"]
    resp = client.post(
        "/api/pairing/claim", json={"token": token, "name": "iPad — hall"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["device_key"]) == 64

    cameras = client.get("/api/settings").json()["cameras"]
    cam = next(c for c in cameras if c["id"] == data["camera_id"])
    assert cam["source_type"] == "phone"
    assert cam["name"] == "iPad — hall"
    assert cam["device_key"] == data["device_key"]

    status = client.get(f"/api/pairing/{token}").json()
    assert status == {"status": "claimed", "camera_id": data["camera_id"]}


def test_token_is_single_use(client):
    token = client.post("/api/pairing/start").json()["token"]
    assert client.post("/api/pairing/claim", json={"token": token}).status_code == 200
    assert client.post("/api/pairing/claim", json={"token": token}).status_code == 410


def test_unknown_and_expired_tokens_rejected(client, monkeypatch):
    assert client.post("/api/pairing/claim", json={"token": "nope"}).status_code == 410
    assert client.get("/api/pairing/nope").json() == {"status": "expired"}
    assert client.get("/pair/nope").status_code == 410
    assert client.get("/api/pairing/nope/qr.png").status_code == 404

    monkeypatch.setattr(pairing_mod, "PAIRING_TTL", 0.01)
    manager = PairingManager()
    entry = manager.start()
    time.sleep(0.03)
    assert manager.get(entry.token) is None
    assert manager.claim(entry.token, "cam") is False


def test_pair_page_and_qr_served_for_valid_token(client):
    token = client.post("/api/pairing/start").json()["token"]
    page = client.get(f"/pair/{token}")
    assert page.status_code == 200
    assert "Start camera" in page.text
    qr = client.get(f"/api/pairing/{token}/qr.png")
    assert qr.status_code == 200
    assert qr.content[:8] == b"\x89PNG\r\n\x1a\n"


# --- frame websocket ------------------------------------------------------------


def paired_camera(client) -> dict:
    token = client.post("/api/pairing/start").json()["token"]
    return client.post(
        "/api/pairing/claim", json={"token": token, "name": "Test phone"}
    ).json()


def test_phone_ws_rejects_bad_key_and_unknown_camera(client):
    cam = paired_camera(client)
    with client.websocket_connect(f"/ws/phone/{cam['camera_id']}") as ws:
        ws.send_json({"device_key": "wrong"})
        assert ws.receive()["type"] == "websocket.close"
    with client.websocket_connect("/ws/phone/doesnotexist") as ws:
        assert ws.receive()["type"] == "websocket.close"


def test_phone_frames_flow_into_snapshot(client):
    cam = paired_camera(client)
    with client.websocket_connect(f"/ws/phone/{cam['camera_id']}") as ws:
        ws.send_json({"device_key": cam["device_key"]})
        for _ in range(4):
            ws.send_bytes(jpeg_bytes((30, 160, 60)))
            time.sleep(0.1)
        deadline = time.monotonic() + 6.0
        frame = None
        while time.monotonic() < deadline:
            resp = client.get(f"/api/cameras/{cam['camera_id']}/snapshot.jpg")
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                px = np.asarray(img)
                # green test frame, not the "no signal"/placeholder gray
                if px[..., 1].mean() > 100 and px[..., 1].mean() > px[..., 0].mean():
                    frame = px
                    break
            ws.send_bytes(jpeg_bytes((30, 160, 60)))
            time.sleep(0.2)
        assert frame is not None, "pushed phone frame never reached the snapshot"


def test_phone_source_bounds_and_staleness():
    src = PhoneSource()
    assert src.read() is None

    # bounded decode: oversized and corrupt frames rejected
    assert PhoneSource.decode_jpeg_bounded(b"") is None
    assert PhoneSource.decode_jpeg_bounded(b"garbage") is None
    assert (
        PhoneSource.decode_jpeg_bounded(b"x" * (PhoneSource.MAX_FRAME_BYTES + 1))
        is None
    )
    frame = PhoneSource.decode_jpeg_bounded(jpeg_bytes())
    assert frame is not None and frame.shape == (240, 320, 3)

    src.push(frame)
    assert src.read() is not None
    src._latest_ts -= PhoneSource.STALE_AFTER + 1  # simulate phone gone quiet
    assert src.read() is None, "stale phone frame must read as no signal"


# --- LAN surface allowlist ---------------------------------------------------------


def test_lan_surface_exposes_only_phone_endpoints(tmp_path):
    app = create_app(data_dir=tmp_path)
    lan = TestClient(PhoneSurfaceApp(app))
    with lan:
        assert lan.get("/phone-camera").status_code == 200
        assert lan.get("/api/settings").status_code == 404
        assert lan.get("/api/events").status_code == 404
        assert lan.get("/api/health").status_code == 404
        assert lan.delete("/api/history").status_code == 404
