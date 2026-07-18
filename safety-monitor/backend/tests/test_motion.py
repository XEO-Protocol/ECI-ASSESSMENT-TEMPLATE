import numpy as np

from safety_monitor.motion import MotionDetector


def make_frame(block_x: int | None = None) -> np.ndarray:
    frame = np.full((240, 320, 3), 40, dtype=np.uint8)
    if block_x is not None:
        frame[100:180, block_x : block_x + 60] = 220
    return frame


def test_first_frame_reports_no_motion():
    det = MotionDetector(sensitivity=0.5)
    result = det.process(make_frame())
    assert not result.active
    assert result.motion_ratio == 0.0


def test_static_scene_reports_no_motion():
    det = MotionDetector(sensitivity=0.5)
    det.process(make_frame(block_x=50))
    result = det.process(make_frame(block_x=50))
    assert not result.active


def test_moving_block_triggers_motion():
    det = MotionDetector(sensitivity=0.5)
    det.process(make_frame(block_x=50))
    result = det.process(make_frame(block_x=150))
    assert result.active
    assert result.motion_ratio > 0
    assert result.regions, "motion should be localized into regions"


def test_higher_sensitivity_detects_smaller_changes():
    low = MotionDetector(sensitivity=0.0)
    high = MotionDetector(sensitivity=1.0)
    a, b = make_frame(block_x=50), make_frame(block_x=58)  # small shift
    low.process(a)
    high.process(a)
    assert high.process(b).motion_ratio >= low.process(b).motion_ratio
    assert high.ratio_threshold < low.ratio_threshold
