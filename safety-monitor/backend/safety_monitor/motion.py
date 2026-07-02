"""Motion detection via simple frame differencing.

Pure numpy — no OpenCV required. Frames are RGB uint8 arrays (H, W, 3).
"""

from __future__ import annotations

import numpy as np

from .models import MotionResult

# Grid used to localize motion into coarse regions (for zone checks).
GRID = 8


def to_gray(frame: np.ndarray) -> np.ndarray:
    """Convert an RGB frame to grayscale float32."""
    return frame.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def downsample(gray: np.ndarray, factor: int = 4) -> np.ndarray:
    """Cheap blur + shrink: average over factor x factor blocks."""
    h, w = gray.shape
    h2, w2 = h - h % factor, w - w % factor
    g = gray[:h2, :w2]
    return g.reshape(h2 // factor, factor, w2 // factor, factor).mean(axis=(1, 3))


class MotionDetector:
    """Detects motion between consecutive frames using differencing.

    sensitivity: 0..1. Higher sensitivity lowers the pixel-change threshold
    and the fraction of changed pixels needed to flag motion.
    """

    def __init__(self, sensitivity: float = 0.5):
        self.sensitivity = sensitivity
        self._prev: np.ndarray | None = None

    @property
    def pixel_threshold(self) -> float:
        # sensitivity 0 -> 60, 1 -> 12 (out of 255 gray levels)
        return 60.0 - 48.0 * self.sensitivity

    @property
    def ratio_threshold(self) -> float:
        # sensitivity 0 -> 5% of pixels, 1 -> 0.5%
        return 0.05 - 0.045 * self.sensitivity

    def reset(self) -> None:
        self._prev = None

    def process(self, frame: np.ndarray) -> MotionResult:
        gray = downsample(to_gray(frame))
        prev, self._prev = self._prev, gray
        if prev is None or prev.shape != gray.shape:
            return MotionResult()

        diff = np.abs(gray - prev)
        changed = diff > self.pixel_threshold
        ratio = float(changed.mean())
        active = ratio > self.ratio_threshold

        regions: list[tuple[float, float, float, float]] = []
        if active:
            h, w = changed.shape
            cell_h, cell_w = max(1, h // GRID), max(1, w // GRID)
            for gy in range(GRID):
                for gx in range(GRID):
                    cell = changed[
                        gy * cell_h : (gy + 1) * cell_h, gx * cell_w : (gx + 1) * cell_w
                    ]
                    if cell.size and cell.mean() > self.ratio_threshold * 2:
                        regions.append((gx / GRID, gy / GRID, 1 / GRID, 1 / GRID))

        return MotionResult(motion_ratio=ratio, active=active, regions=regions)
