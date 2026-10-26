"""test_lighting.py - Simple tests for E1.31 universe allocation and DMX rendering."""

import numpy as np

from storm_sim.lighting import E131LightingEngine
from storm_sim.models import StormState
from storm_sim.physics import PhysicsEngine


def test_lighting_universe_allocation():
    state = StormState(pixels=512)
    engine = E131LightingEngine(state)
    engine._configure_universes(512)
    assert len(engine.universes) == 1

    engine._configure_universes(1024)
    assert len(engine.universes) == 2


def test_lighting_render_frame_and_clear():
    state = StormState(pixels=512, intensity=0.7)
    engine = E131LightingEngine(state)
    engine._configure_universes(512)

    strike = PhysicsEngine.generate_strike(
        state, now=10.0, forced_dist=0.5, forced_epicenter=0.5
    )
    engine.trigger_flash(strike)
    assert len(engine.active_strikes) == 1

    # Render at start of stroke
    engine.render_frame(10.02)
    assert np.max(engine.last_frame_dmx) > 0
    assert engine.last_frame_dmx.dtype == np.uint8

    # Clearing extinguishes output
    engine.clear_all()
    assert len(engine.active_strikes) == 0
    assert np.max(engine.last_frame_dmx) == 0


def test_lighting_zero_intensity_ignores_flash():
    state = StormState(pixels=512, intensity=0.0)
    engine = E131LightingEngine(state)
    strike = PhysicsEngine.generate_strike(state, now=10.0, forced_dist=0.5)
    engine.trigger_flash(strike)
    assert len(engine.active_strikes) == 0
