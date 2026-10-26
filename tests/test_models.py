"""test_models.py - Simple tests for StormState and dataclasses."""

from storm_sim.models import StormState, StrikeEvent, StrokePulse


def test_storm_state_defaults():
    state = StormState()
    assert state.pixels == 512
    assert state.intensity == 0.5
    assert state.fps == 44
    assert state.running is True
    assert not state.is_zero_intensity
    assert state.effective_rate_per_sec > 0
    assert state.effective_rain_level > 0


def test_storm_state_zero_intensity():
    state = StormState(intensity=0.0)
    assert state.is_zero_intensity is True
    assert state.effective_rate_per_sec == 0.0
    assert state.effective_rain_level == 0.0


def test_storm_state_overrides():
    state = StormState(intensity=0.5, override_rate=30.0, override_rain=0.8)
    assert state.effective_rate_per_sec == 0.5  # 30 per min = 0.5 per sec
    assert state.effective_rain_level == 0.8


def test_storm_state_ramp():
    state = StormState(
        intensity=0.2,
        ramp_start_val=0.2,
        ramp_target_val=0.8,
        ramp_start_time=10.0,
        ramp_duration=2.0,
    )
    # Midway through ramp
    state.update_ramp(11.0)
    assert 0.49 < state.intensity < 0.51

    # End of ramp
    state.update_ramp(12.5)
    assert state.intensity == 0.8
    assert state.ramp_duration == 0.0
