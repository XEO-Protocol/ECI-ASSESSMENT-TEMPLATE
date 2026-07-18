"""Real-inference integration tests for the local vision provider.

These exercise the ACTUAL MediaPipe models on a real photograph of a
person — no stubs — and prove the full chain: real detection -> posture
classification -> fall rule firing.

They run only when the models and test photo are present (and mediapipe
is importable); otherwise they skip with an explicit reason, never a
silent pass. Set SAFETY_MONITOR_TEST_ASSETS to a directory containing:

    efficientdet_lite0.tflite   (scripts/download_models.py)
    pose_landmarker_lite.task   (scripts/download_models.py)
    person.jpg                  (any photo of one upright person)
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import numpy as np
import pytest

from safety_monitor.models import EventType, MotionResult, Settings
from safety_monitor.vision import AnalysisContext

ASSETS = Path(os.environ.get("SAFETY_MONITOR_TEST_ASSETS", "/nonexistent"))
REQUIRED = ["efficientdet_lite0.tflite", "pose_landmarker_lite.task", "person.jpg"]

missing = [name for name in REQUIRED if not (ASSETS / name).is_file()]
mediapipe_available = True
try:  # pragma: no cover - env dependent
    import mediapipe  # noqa: F401
except Exception:  # pragma: no cover - env dependent
    mediapipe_available = False

pytestmark = pytest.mark.skipif(
    bool(missing) or not mediapipe_available,
    reason=(
        f"real-model assets missing from {ASSETS}: {missing}"
        if missing
        else "mediapipe not importable"
    ),
)


@pytest.fixture(scope="module")
def provider():
    from safety_monitor.vision_local import LocalVisionProvider

    p = LocalVisionProvider(str(ASSETS))
    yield p
    asyncio.run(p.close())


@pytest.fixture(scope="module")
def photo() -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(ASSETS / "person.jpg").convert("RGB"))


def analyze(provider, frame, camera_id="itest"):
    ctx = AnalysisContext(camera_id=camera_id, motion=MotionResult())
    return asyncio.run(provider.analyze(frame, ctx))


def test_real_model_detects_upright_person(provider, photo):
    analysis = analyze(provider, photo)
    assert analysis.provider == "local"
    persons = [d for d in analysis.detections if d.label == "person"]
    assert persons, "real detector found no person in the test photo"
    best = persons[0]
    assert best.confidence >= 0.5
    x, y, w, h = best.bbox
    assert 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1
    assert best.attributes["pose"] == "standing"


def test_real_model_classifies_rotated_person_as_lying(provider, photo):
    lying = np.ascontiguousarray(np.rot90(photo))
    analysis = analyze(provider, lying, camera_id="itest-rot")
    persons = [d for d in analysis.detections if d.label == "person"]
    assert persons, "real detector found no person in rotated photo"
    assert persons[0].attributes["pose"] == "lying"


def test_real_upright_to_lying_fires_possible_fall_rule(provider, photo):
    """Full real chain: standing photo, then 'fallen' (rotated) photo,
    through the actual rule engine -> a possible_fall event."""
    from safety_monitor.models import CameraSettings
    from safety_monitor.rules import RuleEngine

    camera = CameraSettings(id="fallcam", name="Integration cam")
    settings = Settings(cameras=[camera])
    rules = RuleEngine()

    a1 = analyze(provider, photo, camera_id="fallcam")
    rules.evaluate(camera, MotionResult(), a1, settings)

    lying = np.ascontiguousarray(np.rot90(photo))
    a2 = analyze(provider, lying, camera_id="fallcam")
    events = rules.evaluate(camera, MotionResult(), a2, settings)

    assert any(e.type == EventType.POSSIBLE_FALL for e in events), (
        f"expected a possible_fall event, got {[e.type for e in events]}"
    )
