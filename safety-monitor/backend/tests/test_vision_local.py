"""Contract tests for the real local vision provider.

These use deterministic stub model objects (allowed for contract tests
only) so they run everywhere without model files. Real-inference evidence
lives in test_vision_local_integration.py, which runs when the actual
models and a test photo are available.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from safety_monitor.models import MotionResult
from safety_monitor.vision import AnalysisContext, UnavailableVisionProvider, create_provider
from safety_monitor.vision_local import (
    L_HIP,
    L_SHOULDER,
    R_HIP,
    R_SHOULDER,
    SUDDEN_FALL_WINDOW,
    LocalVisionProvider,
    _FallTracker,
    classify_torso,
)


def landmarks(shoulder, hip, visibility=1.0):
    """Build a 33-landmark list with the torso points placed as given."""
    pts = [SimpleNamespace(x=0.0, y=0.0, visibility=visibility) for _ in range(33)]
    for i in (L_SHOULDER, R_SHOULDER):
        pts[i] = SimpleNamespace(x=shoulder[0], y=shoulder[1], visibility=visibility)
    for i in (L_HIP, R_HIP):
        pts[i] = SimpleNamespace(x=hip[0], y=hip[1], visibility=visibility)
    return pts


def context(camera_id="cam1"):
    return AnalysisContext(camera_id=camera_id, motion=MotionResult())


class StubDetector:
    """Duck-typed stand-in for mediapipe's ObjectDetector."""

    def __init__(self, boxes):
        # boxes: list of (score, x, y, w, h) in pixels
        self.boxes = boxes

    def detect(self, _image):
        detections = [
            SimpleNamespace(
                bounding_box=SimpleNamespace(
                    origin_x=x, origin_y=y, width=w, height=h
                ),
                categories=[SimpleNamespace(score=score)],
            )
            for score, x, y, w, h in self.boxes
        ]
        return SimpleNamespace(detections=detections)


class StubLandmarker:
    def __init__(self, pose_landmarks):
        self.pose_landmarks = pose_landmarks

    def detect(self, _image):
        return SimpleNamespace(pose_landmarks=self.pose_landmarks)


def make_provider(boxes, pose):
    return LocalVisionProvider(
        models_dir="/nonexistent",
        detector=StubDetector(boxes),
        landmarker=StubLandmarker(pose),
    )


FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


# --- torso classification ----------------------------------------------------


def test_vertical_torso_is_standing():
    pose, angle = classify_torso(landmarks(shoulder=(0.5, 0.3), hip=(0.5, 0.6)))
    assert pose == "standing"
    assert angle == pytest.approx(0.0, abs=1e-6)


def test_horizontal_torso_is_lying():
    pose, angle = classify_torso(landmarks(shoulder=(0.2, 0.7), hip=(0.6, 0.7)))
    assert pose == "lying"
    assert angle == pytest.approx(90.0, abs=1e-6)


def test_diagonal_torso_is_unknown():
    pose, _ = classify_torso(landmarks(shoulder=(0.3, 0.3), hip=(0.55, 0.55)))
    assert pose == "unknown"


def test_low_visibility_torso_is_unknown():
    pose, angle = classify_torso(
        landmarks(shoulder=(0.5, 0.3), hip=(0.5, 0.6), visibility=0.1)
    )
    assert pose == "unknown"
    assert angle is None


# --- fall transition tracking --------------------------------------------------


def test_fall_tracker_flags_sudden_transition_once():
    t = _FallTracker()
    assert t.update("standing", 100.0) is False
    assert t.update("lying", 104.0) is True  # upright 4s ago -> sudden
    assert t.update("lying", 106.0) is False  # still lying: not a new fall


def test_fall_tracker_ignores_slow_transition():
    t = _FallTracker()
    t.update("standing", 100.0)
    t.update("unknown", 105.0)
    assert t.update("lying", 100.0 + SUDDEN_FALL_WINDOW + 5) is False


def test_fall_tracker_needs_prior_upright():
    t = _FallTracker()
    assert t.update("lying", 50.0) is False


# --- provider output contract --------------------------------------------------


def test_person_detection_maps_to_normalized_bbox():
    provider = make_provider(
        boxes=[(0.9, 64, 48, 320, 240)],
        pose=[landmarks(shoulder=(0.5, 0.3), hip=(0.5, 0.6))],
    )
    analysis = asyncio.run(provider.analyze(FRAME, context()))
    assert analysis.provider == "local"
    assert "REAL" in analysis.notes
    [det] = analysis.detections
    assert det.label == "person"
    assert det.confidence == 0.9
    assert det.bbox == pytest.approx((0.1, 0.1, 0.5, 0.5))
    assert det.attributes["pose"] == "standing"


def test_standing_then_lying_yields_sudden_transition():
    provider = make_provider(
        boxes=[(0.85, 100, 100, 100, 200)],
        pose=[landmarks(shoulder=(0.5, 0.3), hip=(0.5, 0.6))],
    )
    asyncio.run(provider.analyze(FRAME, context()))

    provider.landmarker = StubLandmarker([landmarks(shoulder=(0.2, 0.7), hip=(0.6, 0.7))])
    analysis = asyncio.run(provider.analyze(FRAME, context()))
    [det] = analysis.detections
    assert det.attributes["pose"] == "lying"
    assert det.attributes.get("transition") == "sudden"

    # a third lying frame is not a new fall
    analysis3 = asyncio.run(provider.analyze(FRAME, context()))
    assert analysis3.detections[0].attributes.get("transition") is None


def test_no_person_yields_no_detections():
    provider = make_provider(boxes=[], pose=[])
    analysis = asyncio.run(provider.analyze(FRAME, context()))
    assert analysis.detections == []


def test_only_top_person_carries_tracked_pose():
    provider = make_provider(
        boxes=[(0.6, 0, 0, 50, 100), (0.95, 200, 200, 100, 200)],
        pose=[landmarks(shoulder=(0.5, 0.3), hip=(0.5, 0.6))],
    )
    analysis = asyncio.run(provider.analyze(FRAME, context()))
    assert analysis.detections[0].confidence == 0.95
    assert analysis.detections[0].attributes["pose"] == "standing"
    assert analysis.detections[1].attributes["pose"] == "unknown"


# --- failure honesty -------------------------------------------------------------


def test_unavailable_provider_never_fabricates_detections():
    provider = UnavailableVisionProvider("local", "model files missing")
    analysis = asyncio.run(provider.analyze(FRAME, context()))
    assert analysis.detections == []
    assert "no simulated detections" in analysis.notes.lower()


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown AI provider"):
        create_provider("cloud-magic")


def test_factory_requires_models_dir_for_local():
    with pytest.raises(ValueError, match="models directory"):
        create_provider("local", models_dir=None)


def test_manager_surfaces_error_and_runs_without_fallback(tmp_path):
    """A configured-but-broken real provider must run with NO analysis,
    never fall back to mock."""
    from safety_monitor.agent_hook import AgentGateway
    from safety_monitor.config import ConfigStore
    from safety_monitor.manager import CameraManager
    from safety_monitor.store import EventStore

    config = ConfigStore(tmp_path)
    config.settings.ai_provider = "local"  # no model files exist in tmp_path
    config.save()

    async def on_event(_event):
        pass

    store = EventStore(
        config.data_dir / "events.db", config.snapshots_dir, config.clips_dir
    )
    manager = CameraManager(config, store, AgentGateway(), on_event)
    assert manager.provider_error is not None
    assert manager.provider.name == "unavailable"
    analysis = asyncio.run(manager.provider.analyze(FRAME, context()))
    assert analysis.detections == []
