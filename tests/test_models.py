"""test_models.py - Simple tests for StormState, dataclasses, and channel map parsing."""

import pytest

from storm_sim.models import StormState, StrikeEvent, StrokePulse, parse_channel_map


def test_storm_state_defaults():
    state = StormState()
    assert state.pixels == 4
    assert state.e131_host == "127.0.0.1"
    assert state.multicast is False
    assert state.intensity == 0.5
    assert state.fps == 44
    assert state.running is True
    assert not state.is_zero_intensity
    assert state.effective_rate_per_sec > 0
    assert state.effective_rain_level > 0
    assert state.channel_map is None


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


def test_parse_channel_map_valid_zero_based():
    mapping = parse_channel_map("0:1, 1:5, 2:10, 3:20", pixel_count=4)
    assert mapping == {0: 0, 1: 4, 2: 9, 3: 19}


def test_parse_channel_map_valid_one_based():
    mapping = parse_channel_map("1:10, 2:20, 3:30, 4:40", pixel_count=4)
    assert mapping == {0: 9, 1: 19, 2: 29, 3: 39}


def test_parse_channel_map_empty():
    assert parse_channel_map(None, pixel_count=4) is None
    assert parse_channel_map("", pixel_count=4) is None
    assert parse_channel_map("   ", pixel_count=4) is None


def test_parse_channel_map_invalid_format():
    with pytest.raises(ValueError, match="Expected format"):
        parse_channel_map("0-1,1-2", pixel_count=4)


def test_parse_channel_map_out_of_bounds():
    with pytest.raises(ValueError, match="out of bounds"):
        parse_channel_map("0:1, 4:2", pixel_count=4)
