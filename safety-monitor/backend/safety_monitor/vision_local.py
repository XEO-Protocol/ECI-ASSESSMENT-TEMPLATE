"""Real on-device vision provider: MediaPipe person detection + pose.

This is REAL inference — no simulated detections. Two official Google
models (Apache-2.0) run fully locally on CPU; frames never leave the
machine:

- EfficientDet-Lite0 (object detector, filtered to "person") gives person
  presence and bounding boxes, multi-person.
- Pose Landmarker Lite gives 33 body keypoints for the most prominent
  person. Posture is classified from the torso axis (shoulder-midpoint ->
  hip-midpoint angle from vertical): upright when near-vertical, lying
  when near-horizontal. A recent upright->lying flip is tagged
  transition="sudden" for the fall rule.

Honesty:
- Posture comes from real keypoints, but "lying" vs "standing" is still a
  geometric classification; the provider says so in its notes.
- If models or the mediapipe runtime are unavailable, the provider fails
  LOUDLY at startup and the manager runs UnavailableVisionProvider (see
  vision.py), which emits NO detections. Real-model failure is never
  papered over with simulated alerts.

Get the models with:  python scripts/download_models.py
"""

from __future__ import annotations

import asyncio
import math
import time
from pathlib import Path

import numpy as np

from .models import Detection, FrameAnalysis
from .vision import AnalysisContext, VisionProvider

DETECTOR_FILE = "efficientdet_lite0.tflite"
POSE_FILE = "pose_landmarker_lite.task"

PERSON_THRESHOLD = 0.45
# Torso angle from vertical (degrees): below -> upright, above -> lying.
UPRIGHT_MAX_DEG = 40.0
LYING_MIN_DEG = 55.0
# Minimum mean visibility of the four torso landmarks to trust the pose.
MIN_TORSO_VISIBILITY = 0.5
# A lying pose within this many seconds of an upright one counts as sudden.
SUDDEN_FALL_WINDOW = 12.0

# Pose Landmarker indices.
L_SHOULDER, R_SHOULDER, L_HIP, R_HIP = 11, 12, 23, 24


def classify_torso(landmarks) -> tuple[str, float | None]:
    """Classify posture from torso-axis angle. Returns (pose, angle_deg)."""
    pts = [landmarks[i] for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)]
    visibility = [getattr(p, "visibility", 1.0) or 1.0 for p in pts]
    if sum(visibility) / 4 < MIN_TORSO_VISIBILITY:
        return "unknown", None
    sx = (pts[0].x + pts[1].x) / 2
    sy = (pts[0].y + pts[1].y) / 2
    hx = (pts[2].x + pts[3].x) / 2
    hy = (pts[2].y + pts[3].y) / 2
    angle = math.degrees(math.atan2(abs(hx - sx), abs(hy - sy)))
    if angle <= UPRIGHT_MAX_DEG:
        return "standing", angle
    if angle >= LYING_MIN_DEG:
        return "lying", angle
    return "unknown", angle


class _FallTracker:
    """Tracks upright->lying transitions per camera for the fall rule."""

    def __init__(self) -> None:
        self.last_pose: str | None = None
        self.last_upright_ts: float | None = None

    def update(self, pose: str, ts: float) -> bool:
        """Returns True when this lying pose should count as a sudden fall."""
        sudden = (
            pose == "lying"
            and self.last_pose != "lying"
            and self.last_upright_ts is not None
            and ts - self.last_upright_ts <= SUDDEN_FALL_WINDOW
        )
        if pose == "standing":
            self.last_upright_ts = ts
        if pose in ("standing", "lying"):
            self.last_pose = pose
        return sudden


class LocalVisionProvider(VisionProvider):
    """MediaPipe person + pose models running locally on CPU."""

    name = "local"

    def __init__(
        self,
        models_dir: str,
        detector: object | None = None,
        landmarker: object | None = None,
    ):
        self.models_dir = Path(models_dir)
        self._trackers: dict[str, _FallTracker] = {}
        self._mp = None

        if detector is not None and landmarker is not None:
            # Deterministic stubs, allowed for contract tests only.
            self.detector = detector
            self.landmarker = landmarker
            return

        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "mediapipe is not installed — run: "
                "pip install -r requirements-vision.txt"
            ) from exc

        det_path = self.models_dir / DETECTOR_FILE
        pose_path = self.models_dir / POSE_FILE
        missing = [p.name for p in (det_path, pose_path) if not p.is_file()]
        if missing:
            raise RuntimeError(
                f"model file(s) missing in {self.models_dir}: {', '.join(missing)}. "
                "Download them with: python scripts/download_models.py"
            )

        self._mp = mp
        self.detector = vision.ObjectDetector.create_from_options(
            vision.ObjectDetectorOptions(
                base_options=BaseOptions(model_asset_path=str(det_path)),
                score_threshold=PERSON_THRESHOLD,
                category_allowlist=["person"],
            )
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(pose_path))
            )
        )

    # --- inference -----------------------------------------------------------

    def _detect_sync(self, frame: np.ndarray) -> tuple[list, list]:
        """Blocking model calls; run via asyncio.to_thread."""
        if self._mp is not None:
            image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(frame),
            )
        else:  # stubs take the raw array
            image = frame
        persons = self.detector.detect(image).detections
        poses = self.landmarker.detect(image).pose_landmarks
        return persons, poses

    async def analyze(self, frame: np.ndarray, context: AnalysisContext) -> FrameAnalysis:
        h, w = frame.shape[:2]
        persons, poses = await asyncio.to_thread(self._detect_sync, frame)

        pose_label = "unknown"
        torso_angle: float | None = None
        if poses:
            pose_label, torso_angle = classify_torso(poses[0])

        tracker = self._trackers.setdefault(context.camera_id, _FallTracker())
        sudden = tracker.update(pose_label, time.monotonic())

        detections: list[Detection] = []
        ranked = sorted(
            persons, key=lambda d: d.categories[0].score, reverse=True
        )
        for rank, det in enumerate(ranked):
            box = det.bounding_box
            attrs: dict = {"pose_source": "pose_landmarks"}
            if rank == 0:
                # The pose landmarker tracks the most prominent person.
                attrs["pose"] = pose_label
                if torso_angle is not None:
                    attrs["torso_angle_deg"] = round(torso_angle, 1)
                if sudden:
                    attrs["transition"] = "sudden"
            else:
                attrs["pose"] = "unknown"
            detections.append(
                Detection(
                    label="person",
                    confidence=round(float(det.categories[0].score), 3),
                    bbox=(
                        max(0.0, box.origin_x / w),
                        max(0.0, box.origin_y / h),
                        min(1.0, box.width / w),
                        min(1.0, box.height / h),
                    ),
                    attributes=attrs,
                )
            )

        return FrameAnalysis(
            provider=self.name,
            detections=detections,
            notes=(
                "REAL on-device inference (MediaPipe EfficientDet-Lite0 + "
                "Pose Landmarker, CPU). Posture is classified from torso "
                "keypoint geometry."
            ),
        )

    async def close(self) -> None:
        for model in (self.detector, self.landmarker):
            close = getattr(model, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # pragma: no cover - shutdown best-effort
                    pass
