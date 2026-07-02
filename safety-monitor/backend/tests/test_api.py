import time

import pytest
from fastapi.testclient import TestClient

from safety_monitor.app import create_app
from safety_monitor.models import Event, EventType, Severity


@pytest.fixture()
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as test_client:
        test_client.app = app
        yield test_client


def add_event(client, **overrides) -> Event:
    store = client.app.state.store
    camera_id = client.app.state.config.settings.cameras[0].id
    defaults = dict(
        camera_id=camera_id,
        type=EventType.POSSIBLE_FALL,
        severity=Severity.ALERT,
        confidence=0.8,
        message="A person may have fallen.",
        created_at=time.time(),
    )
    defaults.update(overrides)
    return store.add(Event(**defaults))


def test_health(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["paused"] is False
    assert data["cameras"], "default synthetic camera should be running"


def test_settings_roundtrip(client):
    settings = client.get("/api/settings").json()
    assert settings["cameras"][0]["source_type"] == "synthetic"
    settings["motion_sensitivity"] = 0.9
    settings["capture_interval_seconds"] = 1.0
    updated = client.put("/api/settings", json=settings).json()
    assert updated["motion_sensitivity"] == 0.9
    assert client.get("/api/settings").json()["motion_sensitivity"] == 0.9


def test_live_snapshot(client):
    camera_id = client.get("/api/cameras").json()[0]["id"]
    # give the capture loop a moment to produce a real frame
    time.sleep(0.5)
    resp = client.get(f"/api/cameras/{camera_id}/snapshot.jpg")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:2] == b"\xff\xd8"  # JPEG magic


def test_privacy_pause_and_recording(client):
    assert client.post("/api/privacy/pause", json={"paused": True}).json() == {
        "paused": True
    }
    assert client.get("/api/health").json()["paused"] is True
    client.post("/api/privacy/pause", json={"paused": False})

    resp = client.post("/api/privacy/recording", json={"enabled": False}).json()
    assert resp == {"recording_enabled": False}


def test_events_listing_and_ack(client):
    event = add_event(client)
    events = client.get("/api/events").json()
    assert any(e["id"] == event.id for e in events)

    filtered = client.get("/api/events", params={"type": "possible_fall"}).json()
    assert all(e["type"] == "possible_fall" for e in filtered)

    assert client.post(f"/api/events/{event.id}/ack").status_code == 200
    assert client.get(f"/api/events/{event.id}").json()["acknowledged"] is True


def test_delete_history(client):
    add_event(client)
    resp = client.delete("/api/history")
    assert resp.status_code == 200
    assert client.get("/api/events").json() == []


def test_emergency_action_requires_confirmation(client):
    event = add_event(client)
    unconfirmed = client.post(
        "/api/actions/emergency",
        json={"event_id": event.id, "action": "notify_contact", "confirmed": False},
    )
    assert unconfirmed.status_code == 428

    confirmed = client.post(
        "/api/actions/emergency",
        json={"event_id": event.id, "action": "notify_contact", "confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["executed"] == "notify_contact"


def test_agent_assessment_flow(client):
    event = add_event(client)
    client.app.state.gateway._pending[event.id] = event

    pending = client.get("/api/agent/pending").json()
    match = [p for p in pending if p["event"]["id"] == event.id]
    assert match and "guidelines" in match[0]

    assessment = {
        "event_id": event.id,
        "agent_name": "test-agent",
        "summary": "The person appears to be moving again; risk may be low.",
        "risk_level": "low",
        "recommended_action": "No action appears necessary.",
    }
    resp = client.post("/api/agent/assessments", json=assessment)
    assert resp.status_code == 200

    stored = client.get(f"/api/events/{event.id}").json()
    assert stored["agent_assessment"]["agent_name"] == "test-agent"
    assert not [
        p
        for p in client.get("/api/agent/pending").json()
        if p["event"]["id"] == event.id
    ]


def test_agent_webhook_registration(client):
    client.post(
        "/api/agent/webhooks",
        json={"name": "my-agent", "url": "http://127.0.0.1:9999/hook"},
    )
    hooks = client.get("/api/agent/webhooks").json()
    assert any(h["name"] == "my-agent" for h in hooks)
    assert client.delete("/api/agent/webhooks/my-agent").status_code == 200


def test_zone_update(client):
    camera_id = client.get("/api/cameras").json()[0]["id"]
    resp = client.put(
        f"/api/cameras/{camera_id}/zones",
        json={
            "mask_zones": [{"label": "window", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
            "restricted_zones": [
                {"label": "stairs", "x": 0.6, "y": 0.4, "w": 0.3, "h": 0.5}
            ],
        },
    )
    assert resp.status_code == 200
    camera = resp.json()
    assert camera["mask_zones"][0]["label"] == "window"
    assert camera["restricted_zones"][0]["label"] == "stairs"
