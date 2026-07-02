"""Modular AI vision provider interface.

The rule engine consumes `FrameAnalysis` objects and does not care where
they come from. To plug in a real model later, implement `VisionProvider`
and register it in `PROVIDERS` (see `create_provider`). Candidates:

- A local YOLO / ONNX person detector (label "person", attributes["pose"]).
- A local pose-estimation model for fall detection.
- A multimodal LLM given the JPEG frame and asked for structured output.

Everything in this file's MockVisionProvider is simulated and clearly
labelled as such in its output notes.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from .models import Detection, FrameAnalysis, MotionResult


@dataclass
class AnalysisContext:
    """Extra context handed to providers alongside the raw frame."""

    camera_id: str
    motion: MotionResult
    timestamp: float = field(default_factory=time.time)


class VisionProvider(ABC):
    """Interface every vision/AI analysis backend must implement."""

    name: str = "base"

    @abstractmethod
    async def analyze(self, frame: np.ndarray, context: AnalysisContext) -> FrameAnalysis:
        """Analyze a single RGB frame and return detections."""

    async def close(self) -> None:  # pragma: no cover - trivial
        pass


class MockVisionProvider(VisionProvider):
    """Simulated analysis for the MVP.

    Behaviour:
    - When motion is active, reports a "person" detection near the largest
      motion region with a standing pose.
    - In demo-cycle mode, walks through a scripted loop so every safety
      event type fires within a few minutes (useful for exercising the UI,
      rules, notifications and agent hooks end to end).
    """

    name = "mock"

    # (start_second, duration, label, confidence, attributes)
    DEMO_SCRIPT = [
        (10, 20, "person", 0.86, {"pose": "standing"}),
        (35, 6, "person", 0.78, {"pose": "lying", "transition": "sudden"}),
        (41, 170, "person", 0.80, {"pose": "lying"}),
        (215, 40, "stove_on", 0.71, {}),
        (260, 8, "smoke", 0.64, {}),
        (275, 150, "door_open", 0.69, {}),
    ]
    DEMO_PERIOD = 430.0

    def __init__(self, demo_cycle: bool = True, rng_seed: int = 7):
        self.demo_cycle = demo_cycle
        self._rng = np.random.default_rng(rng_seed)
        self._t0 = time.monotonic()

    async def analyze(self, frame: np.ndarray, context: AnalysisContext) -> FrameAnalysis:
        detections: list[Detection] = []

        if context.motion.active:
            bbox = context.motion.regions[0] if context.motion.regions else (0.4, 0.3, 0.2, 0.5)
            detections.append(
                Detection(
                    label="person",
                    confidence=round(0.6 + 0.3 * min(1.0, context.motion.motion_ratio * 20), 2),
                    bbox=bbox,
                    attributes={"pose": "standing"},
                )
            )

        if self.demo_cycle:
            t = (time.monotonic() - self._t0) % self.DEMO_PERIOD
            for start, duration, label, conf, attrs in self.DEMO_SCRIPT:
                if start <= t < start + duration:
                    # jitter confidence a little so it looks alive
                    jitter = float(self._rng.uniform(-0.05, 0.05))
                    det = Detection(
                        label=label,
                        confidence=round(min(0.95, max(0.3, conf + jitter)), 2),
                        bbox=(0.35, 0.35, 0.3, 0.4) if label == "person" else None,
                        attributes=dict(attrs),
                    )
                    # scripted person replaces the motion-derived one
                    if label == "person":
                        detections = [d for d in detections if d.label != "person"]
                    detections.append(det)

        return FrameAnalysis(
            provider=self.name,
            detections=detections,
            notes="MOCK analysis — simulated detections, not a real vision model.",
        )


def create_provider(name: str, *, mock_demo_cycle: bool = True) -> VisionProvider:
    """Factory for vision providers. Extend here to add real models."""
    if name == "mock":
        return MockVisionProvider(demo_cycle=mock_demo_cycle)
    # e.g. `if name == "yolo-local": return YoloProvider(...)`
    raise ValueError(f"Unknown AI provider: {name!r} (available: mock)")
