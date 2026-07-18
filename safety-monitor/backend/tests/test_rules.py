import re

from safety_monitor.models import (
    CameraSettings,
    Detection,
    EventType,
    FrameAnalysis,
    MotionResult,
    Settings,
    Zone,
)
from safety_monitor.rules import RuleEngine

DAY_HOUR = 12
NIGHT_HOUR = 23

HEDGE = re.compile(r"appears?|possible|possibly|may|could", re.IGNORECASE)


def analysis(*detections: Detection) -> FrameAnalysis:
    return FrameAnalysis(provider="test", detections=list(detections))


def person(pose: str = "standing", conf: float = 0.9, bbox=None, **attrs) -> Detection:
    return Detection(
        label="person", confidence=conf, bbox=bbox, attributes={"pose": pose, **attrs}
    )


def make_camera(**kwargs) -> CameraSettings:
    return CameraSettings(name="Test cam", source_type="synthetic", **kwargs)


def evaluate(engine, camera, settings, t, det_analysis, motion=None, hour=DAY_HOUR):
    return engine.evaluate(
        camera,
        motion or MotionResult(),
        det_analysis,
        settings,
        now=t,
        local_hour=hour,
    )


def types(events) -> set[EventType]:
    return {e.type for e in events}


def test_person_detected_fires_once_on_arrival():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    first = evaluate(engine, camera, settings, 1000, analysis(person()))
    second = evaluate(engine, camera, settings, 1002, analysis(person()))
    assert EventType.PERSON_DETECTED in types(first)
    assert EventType.PERSON_DETECTED not in types(second)


def test_possible_fall_on_standing_to_lying_transition():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    evaluate(engine, camera, settings, 1000, analysis(person("standing")))
    events = evaluate(engine, camera, settings, 1005, analysis(person("lying")))
    assert EventType.POSSIBLE_FALL in types(events)


def test_sudden_lying_counts_as_possible_fall():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    events = evaluate(
        engine, camera, settings, 1000, analysis(person("lying", transition="sudden"))
    )
    assert EventType.POSSIBLE_FALL in types(events)


def test_gradual_lying_is_not_a_fall():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    events = evaluate(engine, camera, settings, 1000, analysis(person("lying")))
    assert EventType.POSSIBLE_FALL not in types(events)


def test_person_lying_still_after_threshold():
    engine, camera = RuleEngine(), make_camera()
    settings = Settings(lying_still_seconds=120)
    evaluate(engine, camera, settings, 1000, analysis(person("lying")))
    early = evaluate(engine, camera, settings, 1060, analysis(person("lying")))
    assert EventType.PERSON_LYING_STILL not in types(early)
    late = evaluate(engine, camera, settings, 1130, analysis(person("lying")))
    assert EventType.PERSON_LYING_STILL in types(late)


def test_stove_unattended_requires_absence():
    engine, camera = RuleEngine(), make_camera()
    settings = Settings(stove_unattended_seconds=300)
    stove = Detection(label="stove_on", confidence=0.8)
    early = evaluate(engine, camera, settings, 1000, analysis(stove))
    assert EventType.STOVE_UNATTENDED not in types(early)
    late = evaluate(engine, camera, settings, 1301, analysis(stove))
    assert EventType.STOVE_UNATTENDED in types(late)


def test_stove_with_person_nearby_does_not_fire():
    engine, camera = RuleEngine(), make_camera()
    settings = Settings(stove_unattended_seconds=300)
    stove = Detection(label="stove_on", confidence=0.8)
    evaluate(engine, camera, settings, 1000, analysis(stove, person()))
    events = evaluate(engine, camera, settings, 1301, analysis(stove, person()))
    assert EventType.STOVE_UNATTENDED not in types(events)


def test_smoke_anomaly_fires_immediately():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    smoke = Detection(label="smoke", confidence=0.7)
    events = evaluate(engine, camera, settings, 1000, analysis(smoke))
    assert EventType.SMOKE_FLAME_ANOMALY in types(events)


def test_door_left_open_after_threshold():
    engine, camera = RuleEngine(), make_camera()
    settings = Settings(door_open_seconds=120)
    door = Detection(label="door_open", confidence=0.7)
    early = evaluate(engine, camera, settings, 1000, analysis(door))
    assert EventType.DOOR_LEFT_OPEN not in types(early)
    late = evaluate(engine, camera, settings, 1121, analysis(door))
    assert EventType.DOOR_LEFT_OPEN in types(late)


def test_restricted_zone_entry():
    camera = make_camera(
        restricted_zones=[Zone(label="the medicine cabinet", x=0, y=0, w=0.5, h=0.5)]
    )
    engine, settings = RuleEngine(), Settings()
    inside = person(bbox=(0.1, 0.1, 0.2, 0.2))
    events = evaluate(engine, camera, settings, 1000, analysis(inside))
    assert EventType.RESTRICTED_ZONE_ENTRY in types(events)


def test_no_restricted_zone_event_outside_zone():
    camera = make_camera(restricted_zones=[Zone(x=0, y=0, w=0.3, h=0.3)])
    engine, settings = RuleEngine(), Settings()
    outside = person(bbox=(0.7, 0.7, 0.2, 0.2))
    events = evaluate(engine, camera, settings, 1000, analysis(outside))
    assert EventType.RESTRICTED_ZONE_ENTRY not in types(events)


def test_unusual_night_motion_only_at_night():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    motion = MotionResult(motion_ratio=0.05, active=True)
    day = evaluate(engine, camera, settings, 1000, analysis(), motion, hour=DAY_HOUR)
    assert EventType.UNUSUAL_NIGHT_MOTION not in types(day)
    night = evaluate(
        RuleEngine(), camera, settings, 1000, analysis(), motion, hour=NIGHT_HOUR
    )
    assert EventType.UNUSUAL_NIGHT_MOTION in types(night)


def test_cooldown_suppresses_repeat_events():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    smoke = Detection(label="smoke", confidence=0.7)
    assert types(evaluate(engine, camera, settings, 1000, analysis(smoke)))
    again = evaluate(engine, camera, settings, 1030, analysis(smoke))
    assert EventType.SMOKE_FLAME_ANOMALY not in types(again)
    later = evaluate(engine, camera, settings, 1200, analysis(smoke))
    assert EventType.SMOKE_FLAME_ANOMALY in types(later)


def test_low_confidence_detections_are_ignored():
    engine, camera, settings = RuleEngine(), make_camera(), Settings()
    weak = person(conf=0.2)
    events = evaluate(engine, camera, settings, 1000, analysis(weak))
    assert EventType.PERSON_DETECTED not in types(events)


def test_all_safety_messages_use_hedged_language():
    """Safety events must never claim certainty."""
    engine = RuleEngine()
    settings = Settings(
        lying_still_seconds=1, stove_unattended_seconds=60, door_open_seconds=60
    )
    camera = make_camera(restricted_zones=[Zone(x=0, y=0, w=1, h=1)])
    collected = []
    smoke = Detection(label="smoke", confidence=0.7)
    stove = Detection(label="stove_on", confidence=0.8)
    door = Detection(label="door_open", confidence=0.7)
    collected += evaluate(
        engine, camera, settings, 1000,
        analysis(person("lying", transition="sudden", bbox=(0.4, 0.4, 0.2, 0.2)), smoke, stove, door),
    )
    collected += evaluate(
        engine, camera, settings, 1005, analysis(person("lying"), stove, door)
    )
    # person leaves; stove and door remain in view long past their thresholds
    collected += evaluate(engine, camera, settings, 2000, analysis(stove, door))
    fired = {e.type for e in collected}
    assert {
        EventType.POSSIBLE_FALL,
        EventType.SMOKE_FLAME_ANOMALY,
        EventType.RESTRICTED_ZONE_ENTRY,
        EventType.PERSON_LYING_STILL,
        EventType.STOVE_UNATTENDED,
        EventType.DOOR_LEFT_OPEN,
    } <= fired
    for event in collected:
        if event.type in (EventType.MOTION,):
            continue
        assert HEDGE.search(event.message), (
            f"{event.type}: message not hedged: {event.message!r}"
        )
