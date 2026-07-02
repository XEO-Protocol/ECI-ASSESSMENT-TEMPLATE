"""Camera sources.

Two implementations:
- WebcamSource: real camera via OpenCV (optional dependency).
- SyntheticSource: generated frames with a moving figure, so the whole
  pipeline can run and be demoed with no camera hardware installed.
"""

from __future__ import annotations

import math
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


def create_source(source_type: str, device_index: int = 0) -> CameraSource:
    if source_type == "webcam":
        return WebcamSource(device_index)
    if source_type == "synthetic":
        return SyntheticSource(seed=device_index)
    raise ValueError(f"Unknown camera source type: {source_type}")
