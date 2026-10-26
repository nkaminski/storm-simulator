"""test_osc.py - Simple tests for OSC routing and state updates."""

from storm_sim.models import StormState
from storm_sim.osc_control import OSCController


def test_osc_intensity_and_halt():
    state = StormState(intensity=0.5)
    halt_called = False
    triggered_args = []

    def on_halt():
        nonlocal halt_called
        halt_called = True

    def on_trigger(dist, epi):
        triggered_args.append((dist, epi))

    controller = OSCController(state, on_trigger, on_halt)

    # Change intensity
    controller._on_intensity("/storm/intensity", 0.85)
    assert abs(state.intensity - 0.85) < 1e-5
    assert not halt_called

    # Killswitch (0.0) invokes halt callback
    controller._on_intensity("/storm/intensity", 0.0)
    assert state.is_zero_intensity
    assert halt_called is True


def test_osc_overrides_and_recouple():
    state = StormState(intensity=0.5)
    controller = OSCController(state, lambda d, e: None, lambda: None)

    controller._on_rate("/storm/rate", 24.0)
    assert state.override_rate == 24.0

    controller._on_rain("/storm/rain/level", 0.9)
    assert state.override_rain == 0.9

    controller._on_couple("/storm/intensity/couple")
    assert state.override_rate is None
    assert state.override_rain is None


def test_osc_manual_strike():
    state = StormState(intensity=0.5)
    received = []
    controller = OSCController(state, lambda d, e: received.append((d, e)), lambda: None)

    controller._on_manual_strike("/storm/strike/trigger", 1.5, 0.3)
    assert received == [(1.5, 0.3)]
