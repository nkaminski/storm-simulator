"""test_ui.py - Simple tests for desktop UI controls and slider interactions."""

from storm_sim.engine import StormCoordinator
from storm_sim.models import StormState
from storm_sim.ui import StormDesktopUI


def test_ui_rain_slider_immediate_override():
    state = StormState(intensity=0.65)
    coord = StormCoordinator(state)
    ui = StormDesktopUI(coord)
    try:
        # Initial state: Auto mode
        assert not ui.var_override_enable.get()
        assert state.override_rain is None

        # Moving rain slider immediately takes manual control
        ui._on_rain_override_change(0.15)
        assert ui.var_override_enable.get() is True
        assert state.override_rain == 0.15
        assert "Manual" in ui.lbl_rain_val.cget("text")

        # Sliding to 0.0 silences rain
        ui._on_rain_override_change(0.0)
        assert state.override_rain == 0.0
        assert state.effective_rain_level == 0.0

        # Unchecking manual overrides re-couples back to auto intensity
        ui.var_override_enable.set(False)
        ui._on_toggle_overrides()
        assert state.override_rain is None
        assert state.effective_rain_level > 0.0
        assert "Auto" in ui.lbl_rain_val.cget("text")
    finally:
        coord.stop()
        ui.root.destroy()
