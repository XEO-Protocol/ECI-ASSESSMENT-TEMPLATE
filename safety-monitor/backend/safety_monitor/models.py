"""Shared data models for events, detections, zones and settings.

Language policy: safety events are never stated as certainties. Every
user-facing message generated here uses hedged phrasing ("possible",
"appears", "may be"). Keep that convention when adding new event types.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    MOTION = "motion"
    PERSON_DETECTED = "person_detected"
    POSSIBLE_FALL = "possible_fall"
    PERSON_LYING_STILL = "person_lying_still"
    STOVE_UNATTENDED = "stove_unattended"
    SMOKE_FLAME_ANOMALY = "smoke_flame_anomaly"
    DOOR_LEFT_OPEN = "door_left_open"
    RESTRICTED_ZONE_ENTRY = "restricted_zone_entry"
    UNUSUAL_NIGHT_MOTION = "unusual_night_motion"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"


class Zone(BaseModel):
    """A rectangular region in normalized coordinates (0..1)."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: str = ""
    x: float
    y: float
    w: float
    h: float

    def contains_point(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def intersects(self, bx: float, by: float, bw: float, bh: float) -> bool:
        return not (
            bx + bw < self.x
            or bx > self.x + self.w
            or by + bh < self.y
            or by > self.y + self.h
        )


class Detection(BaseModel):
    """A single detection from a vision provider."""

    label: str  # e.g. "person", "stove_on", "smoke", "flame", "door_open"
    confidence: float
    bbox: Optional[tuple[float, float, float, float]] = None  # normalized x,y,w,h
    attributes: dict = Field(default_factory=dict)  # e.g. {"pose": "lying"}


class FrameAnalysis(BaseModel):
    """Result of analysing one frame with a vision provider."""

    provider: str
    detections: list[Detection] = Field(default_factory=list)
    notes: str = ""

    def best(self, label: str) -> Optional[Detection]:
        matches = [d for d in self.detections if d.label == label]
        return max(matches, key=lambda d: d.confidence) if matches else None


class MotionResult(BaseModel):
    """Result of frame-differencing motion detection."""

    motion_ratio: float = 0.0  # fraction of pixels that changed
    active: bool = False
    regions: list[tuple[float, float, float, float]] = Field(default_factory=list)


class Event(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    camera_id: str
    type: EventType
    severity: Severity
    confidence: float
    message: str  # always hedged, never a claim of certainty
    created_at: float = Field(default_factory=time.time)
    snapshot_path: Optional[str] = None
    clip_dir: Optional[str] = None
    acknowledged: bool = False
    agent_assessment: Optional["AgentAssessment"] = None


class AgentAssessment(BaseModel):
    """An assessment returned by an external agent for a specific event."""

    event_id: str
    agent_name: str
    summary: str  # agents are asked to use hedged language as well
    risk_level: Literal["none", "low", "medium", "high"]
    recommended_action: str = ""
    requires_user_confirmation: bool = True
    created_at: float = Field(default_factory=time.time)


class CameraSettings(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = "Camera"
    source_type: Literal["webcam", "synthetic", "mjpeg"] = "synthetic"
    device_index: int = 0
    url: str = ""  # mjpeg only: http(s) URL of the network camera stream
    enabled: bool = True
    mask_zones: list[Zone] = Field(default_factory=list)
    restricted_zones: list[Zone] = Field(default_factory=list)


class Settings(BaseModel):
    """Runtime settings, persisted to <data_dir>/settings.json."""

    capture_interval_seconds: float = 2.0
    motion_sensitivity: float = 0.5  # 0 (least) .. 1 (most sensitive)
    night_start_hour: int = 22
    night_end_hour: int = 6
    lying_still_seconds: float = 120.0
    stove_unattended_seconds: float = 300.0
    door_open_seconds: float = 120.0
    notifications_enabled: bool = True
    recording_enabled: bool = True  # save snapshots/clips for events
    paused: bool = False  # privacy: pause all capture and analysis
    ai_provider: str = "mock"  # "mock" (simulated) or "local" (real on-device models)
    mock_demo_cycle: bool = True  # mock provider cycles through demo scenarios
    models_dir: str = ""  # empty -> <data_dir>/models (see scripts/download_models.py)
    cameras: list[CameraSettings] = Field(default_factory=list)


Event.model_rebuild()
