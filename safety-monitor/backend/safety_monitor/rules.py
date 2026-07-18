"""Rule engine turning motion + vision analysis into safety events.

Every rule produces hedged, non-certain language. This is deliberate:
the system flags *possible* situations for a human (or agent) to review,
it never diagnoses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import (
    CameraSettings,
    Detection,
    Event,
    EventType,
    FrameAnalysis,
    MotionResult,
    Settings,
    Severity,
)

# Minimum confidence for a detection to be considered by rules at all.
MIN_CONFIDENCE = 0.5

# Seconds before the same event type may fire again for a camera.
COOLDOWNS: dict[EventType, float] = {
    EventType.MOTION: 60,
    EventType.PERSON_DETECTED: 120,
    EventType.POSSIBLE_FALL: 60,
    EventType.PERSON_LYING_STILL: 300,
    EventType.STOVE_UNATTENDED: 300,
    EventType.SMOKE_FLAME_ANOMALY: 120,
    EventType.DOOR_LEFT_OPEN: 300,
    EventType.RESTRICTED_ZONE_ENTRY: 120,
    EventType.UNUSUAL_NIGHT_MOTION: 300,
}

# How recently a person must have been standing for a lying pose to count
# as a possible fall (seconds).
FALL_WINDOW = 15.0


@dataclass
class CameraRuleState:
    person_present: bool = False
    last_person_seen: float | None = None
    last_standing_seen: float | None = None
    lying_since: float | None = None
    stove_on_since: float | None = None
    door_open_since: float | None = None
    last_fired: dict[EventType, float] = field(default_factory=dict)


class RuleEngine:
    """Stateful per-camera evaluation of safety rules."""

    def __init__(self):
        self._state: dict[str, CameraRuleState] = {}

    def state_for(self, camera_id: str) -> CameraRuleState:
        return self._state.setdefault(camera_id, CameraRuleState())

    def reset(self, camera_id: str | None = None) -> None:
        if camera_id is None:
            self._state.clear()
        else:
            self._state.pop(camera_id, None)

    def evaluate(
        self,
        camera: CameraSettings,
        motion: MotionResult,
        analysis: FrameAnalysis,
        settings: Settings,
        now: float | None = None,
        local_hour: int | None = None,
    ) -> list[Event]:
        now = time.time() if now is None else now
        local_hour = time.localtime(now).tm_hour if local_hour is None else local_hour
        st = self.state_for(camera.id)
        events: list[Event] = []

        person = analysis.best("person")
        if person is not None and person.confidence < MIN_CONFIDENCE:
            person = None
        pose = (person.attributes.get("pose") if person else None) or "unknown"

        def fire(
            etype: EventType, severity: Severity, confidence: float, message: str
        ) -> None:
            last = st.last_fired.get(etype)
            if last is not None and now - last < COOLDOWNS[etype]:
                return
            st.last_fired[etype] = now
            events.append(
                Event(
                    camera_id=camera.id,
                    type=etype,
                    severity=severity,
                    confidence=round(confidence, 2),
                    message=message,
                    created_at=now,
                )
            )

        # --- person presence -------------------------------------------------
        if person is not None:
            newly_arrived = not st.person_present
            st.person_present = True
            st.last_person_seen = now
            if newly_arrived:
                fire(
                    EventType.PERSON_DETECTED,
                    Severity.INFO,
                    person.confidence,
                    f"A person appears to be present on {camera.name}.",
                )
        elif st.last_person_seen is not None and now - st.last_person_seen > 30:
            st.person_present = False

        # --- possible fall ----------------------------------------------------
        if person is not None and pose == "lying":
            recently_standing = (
                st.last_standing_seen is not None
                and now - st.last_standing_seen <= FALL_WINDOW
            )
            sudden = person.attributes.get("transition") == "sudden"
            if st.lying_since is None:
                st.lying_since = now
                if recently_standing or sudden:
                    fire(
                        EventType.POSSIBLE_FALL,
                        Severity.ALERT,
                        person.confidence,
                        f"A person on {camera.name} may have fallen — they appear "
                        "to have gone from upright to lying down suddenly. "
                        "Please review the snapshot.",
                    )
            # --- person lying still ------------------------------------------
            elif (
                now - st.lying_since >= settings.lying_still_seconds
                and not motion.active
            ):
                minutes = int((now - st.lying_since) // 60) or 1
                fire(
                    EventType.PERSON_LYING_STILL,
                    Severity.ALERT,
                    person.confidence,
                    f"A person on {camera.name} appears to have been lying still "
                    f"for around {minutes} minute(s). This may be normal rest, "
                    "but it could need checking.",
                )
        else:
            st.lying_since = None
            if person is not None and pose == "standing":
                st.last_standing_seen = now

        # --- stove possibly left unattended ----------------------------------
        stove = analysis.best("stove_on")
        if stove is not None and stove.confidence >= MIN_CONFIDENCE:
            if st.stove_on_since is None:
                st.stove_on_since = now
            person_recent = (
                st.last_person_seen is not None
                and now - st.last_person_seen < settings.stove_unattended_seconds
            )
            if (
                now - st.stove_on_since >= settings.stove_unattended_seconds
                and not person_recent
            ):
                fire(
                    EventType.STOVE_UNATTENDED,
                    Severity.WARNING,
                    stove.confidence,
                    f"The stove/hob on {camera.name} appears to be on with no one "
                    "nearby for a while — it may have been left unattended.",
                )
        else:
            st.stove_on_since = None

        # --- smoke / flame-like anomaly --------------------------------------
        for label in ("smoke", "flame"):
            det = analysis.best(label)
            if det is not None and det.confidence >= MIN_CONFIDENCE:
                fire(
                    EventType.SMOKE_FLAME_ANOMALY,
                    Severity.ALERT,
                    det.confidence,
                    f"A {label}-like visual anomaly appears on {camera.name}. "
                    "This may be a false alarm, but please check.",
                )

        # --- door left open ---------------------------------------------------
        door = analysis.best("door_open")
        if door is not None and door.confidence >= MIN_CONFIDENCE:
            if st.door_open_since is None:
                st.door_open_since = now
            elif now - st.door_open_since >= settings.door_open_seconds:
                fire(
                    EventType.DOOR_LEFT_OPEN,
                    Severity.WARNING,
                    door.confidence,
                    f"A door on {camera.name} appears to have been left open "
                    "for a while.",
                )
        else:
            st.door_open_since = None

        # --- restricted zone entry ---------------------------------------------
        if person is not None and person.bbox is not None:
            bx, by, bw, bh = person.bbox
            cx, cy = bx + bw / 2, by + bh / 2
            for zone in camera.restricted_zones:
                if zone.contains_point(cx, cy) or zone.intersects(bx, by, bw, bh):
                    label = zone.label or "a restricted zone"
                    fire(
                        EventType.RESTRICTED_ZONE_ENTRY,
                        Severity.WARNING,
                        person.confidence,
                        f"A person appears to have entered {label} on {camera.name}.",
                    )
                    break

        # --- unusual motion at night -------------------------------------------
        if motion.active and _is_night(local_hour, settings):
            fire(
                EventType.UNUSUAL_NIGHT_MOTION,
                Severity.WARNING,
                min(0.9, 0.5 + motion.motion_ratio * 10),
                f"There appears to be unusual motion on {camera.name} during "
                "night hours.",
            )

        # --- generic motion (info-level, heavily rate limited) ------------------
        if motion.active:
            fire(
                EventType.MOTION,
                Severity.INFO,
                min(0.9, 0.5 + motion.motion_ratio * 10),
                f"Motion detected on {camera.name}.",
            )

        return events


def _is_night(hour: int, settings: Settings) -> bool:
    start, end = settings.night_start_hour, settings.night_end_hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # window crosses midnight
