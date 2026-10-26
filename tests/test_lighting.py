"""test_lighting.py - Simple tests for E1.31 universe allocation, DMX rendering, and channel mapping."""

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
    state = StormState(pixels=4, intensity=0.7)
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

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
    state = StormState(pixels=4, intensity=0.0)
    engine = E131LightingEngine(state)
    strike = PhysicsEngine.generate_strike(state, now=10.0, forced_dist=0.5)
    engine.trigger_flash(strike)
    assert len(engine.active_strikes) == 0


def test_lighting_channel_map_routing():
    # Map pixel 0 to DMX slot 9 (channel 10) and pixel 3 to DMX slot 19 (channel 20)
    state = StormState(pixels=4, intensity=1.0, channel_map={0: 9, 3: 19})
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

    strike = PhysicsEngine.generate_strike(
        state, now=10.0, forced_dist=0.1, forced_epicenter=0.0
    )
    engine.trigger_flash(strike)
    engine.render_frame(10.02)

    dmx_output = engine.sender[engine.universes[0]].dmx_data
    # Pixel 0 was illuminated at epicenter 0.0 -> mapped to slot 9
    assert dmx_output[9] > 0
    # Slot 0 was not mapped -> should be 0
    assert dmx_output[0] == 0
