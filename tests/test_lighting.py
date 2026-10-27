"""test_lighting.py - Simple tests for E1.31 universe allocation, DMX rendering, and channel mapping."""

import numpy as np

from storm_sim.constants import MIN_STROKE_ON_TIME_SEC
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


def test_lighting_minimum_on_time_sustained():
    """Verify lightning pulse holds full peak amplitude for >= 1/15th second before decaying."""
    state = StormState(pixels=4, intensity=1.0)
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

    strike = PhysicsEngine.generate_strike(
        state, now=10.0, forced_dist=0.2, forced_epicenter=0.0
    )
    engine.trigger_flash(strike)

    # Initial frame
    engine.render_frame(10.01)
    peak_val_start = np.max(engine.last_frame_dmx)
    assert peak_val_start == 255

    # At exactly 1/15th second (0.0667 s), the pulse must still be sustained at full peak
    engine.render_frame(10.0 + (1.0 / 15.0))
    peak_val_at_15th = np.max(engine.last_frame_dmx)
    assert peak_val_at_15th == peak_val_start

    # Later during decay (e.g. at 0.16s), the pulse should have decayed below peak
    engine.render_frame(10.16)
    peak_val_decay = np.max(engine.last_frame_dmx)
    assert peak_val_decay < peak_val_start


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


def test_lighting_channel_map_grouped_channels():
    # 5 simulated pixels with grouped DMX outputs matching user setup:
    # 0 -> 44 (Ch 45), 1 -> 45 (Ch 46), 2 -> 46 (Ch 47)
    # 3 -> 87, 88, 89 (Ch 88-90)
    # 4 -> 92, 93, 94 (Ch 93-95)
    mapping = {
        0: 44,
        1: 45,
        2: 46,
        3: [87, 88, 89],
        4: [92, 93, 94],
    }
    state = StormState(pixels=5, intensity=1.0, channel_map=mapping)
    engine = E131LightingEngine(state)
    engine._configure_universes(5)

    # Strike with epicenter at right side (1.0) -> illuminates pixel 4
    strike = PhysicsEngine.generate_strike(
        state, now=10.0, forced_dist=0.1, forced_epicenter=1.0
    )
    engine.trigger_flash(strike)
    engine.render_frame(10.02)

    dmx_output = engine.sender[engine.universes[0]].dmx_data
    # Pixel 4 group (DMX 93, 94, 95 -> slots 92, 93, 94) should all be illuminated equally
    assert dmx_output[92] > 0
    assert dmx_output[92] == dmx_output[93] == dmx_output[94]



def test_passthrough_conditional_nonzero_override_sequential():
    state = StormState(pixels=4, intensity=0.7, passthrough_listen="0.0.0.0:5568")
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

    # Simulate desk sending 512 channels
    desk_universe = bytearray(512)
    desk_universe[0] = 50   # Desk Ch 1
    desk_universe[1] = 75   # Desk Ch 2
    desk_universe[2] = 100  # Desk Ch 3
    desk_universe[3] = 125  # Desk Ch 4
    desk_universe[10] = 200 # Desk Ch 11 (stage light)
    desk_universe[511] = 255 # Desk Ch 512
    engine._passthrough_buffers[1] = desk_universe

    # Case 1: No lightning active -> ALL channels pass through from desk
    engine.render_frame(now=1.0)
    out_dmx = engine.sender[1].dmx_data
    assert len(out_dmx) == 512
    assert out_dmx[0] == 50
    assert out_dmx[1] == 75
    assert out_dmx[2] == 100
    assert out_dmx[3] == 125
    assert out_dmx[10] == 200
    assert out_dmx[511] == 255

    # Case 2: Lightning strikes with epicenter focused near pixel 0
    strike = PhysicsEngine.generate_strike(
        state, now=2.0, forced_dist=0.1, forced_epicenter=0.0
    )
    engine.trigger_flash(strike)
    engine.render_frame(now=2.02)
    out_dmx = engine.sender[1].dmx_data

    # Pixel 0 is nonzero -> OVERRIDDEN by lightning (> 0)
    assert out_dmx[0] > 0
    assert out_dmx[0] != 50  # Overridden from desk value of 50
    # Pixel 3 is far from epicenter 0.0 and equals 0 -> PRESERVED from desk!
    if engine.last_frame_dmx[3] == 0:
        assert out_dmx[3] == 125  # Preserved from desk
    # Channels 11 and 512 are not lightning channels -> 100% PRESERVED from desk!
    assert out_dmx[10] == 200
    assert out_dmx[511] == 255


def test_passthrough_remapping_does_not_affect_passthrough():
    # Map simulator pixels 0 and 1 to DMX channels 10 and 25 (slots 9 and 24)
    state = StormState(
        pixels=4,
        intensity=1.0,
        channel_map={0: 9, 1: 24},
        passthrough_listen="0.0.0.0:5568",
    )
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

    # Populate desk buffer with distinct values across the entire universe
    desk_universe = bytearray(val % 256 for val in range(1, 513))
    engine._passthrough_buffers[1] = bytearray(desk_universe)

    # 1. Before strike: all 512 channels pass through untouched and unshifted
    engine.render_frame(now=1.0)
    out_dmx = engine.sender[1].dmx_data
    assert bytes(out_dmx) == bytes(desk_universe)

    # 2. Strike occurring at pixel 0 (slot 9)
    strike = PhysicsEngine.generate_strike(
        state, now=2.0, forced_dist=0.1, forced_epicenter=0.0
    )
    engine.trigger_flash(strike)
    engine.render_frame(now=2.02)
    out_dmx = engine.sender[1].dmx_data

    # Channel 10 (slot 9) is overridden by lightning
    assert out_dmx[9] > 0
    assert out_dmx[9] != desk_universe[9]

    # Critical check: Remapping did NOT shift or remap passthrough channels!
    # Channel 1 (slot 0) has desk value 1
    assert out_dmx[0] == desk_universe[0]
    # Channel 2 (slot 1) has desk value 2
    assert out_dmx[1] == desk_universe[1]
    # Channel 9 (slot 8) has desk value 9
    assert out_dmx[8] == desk_universe[8]
    # Channel 11 (slot 10) has desk value 11
    assert out_dmx[10] == desk_universe[10]
    # Channel 50 (slot 49) has desk value 50
    assert out_dmx[49] == desk_universe[49]
    # Channel 512 (slot 511) has desk value 256 % 256 = 0
    assert out_dmx[511] == desk_universe[511]


def test_passthrough_zero_intensity_streams_desk():
    state = StormState(pixels=4, intensity=0.0, passthrough_listen="0.0.0.0:5568")
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

    desk_universe = bytearray(512)
    desk_universe[0] = 99
    desk_universe[50] = 123
    engine._passthrough_buffers[1] = desk_universe

    engine.render_frame(now=1.0)
    out_dmx = engine.sender[1].dmx_data
    assert out_dmx[0] == 99
    assert out_dmx[50] == 123


def test_passthrough_custom_universe_mapping():
    # Desk sends on universe 2, simulator outputs on universe 1
    state = StormState(
        pixels=4,
        start_universe=1,
        passthrough_listen="0.0.0.0:5568",
        passthrough_universe=2,
    )
    engine = E131LightingEngine(state)
    engine._configure_universes(4)

    desk_universe_2 = bytearray(512)
    desk_universe_2[15] = 222
    engine._passthrough_buffers[2] = desk_universe_2

    engine.render_frame(now=1.0)
    out_dmx = engine.sender[1].dmx_data
    # Output universe 1 receives desk data from universe 2
    assert out_dmx[15] == 222


def test_passthrough_data_packet_callback():
    import sacn
    state = StormState(pixels=4, passthrough_listen="0.0.0.0:5568")
    engine = E131LightingEngine(state)

    packet = sacn.DataPacket(
        cid=tuple([0] * 16),
        sourceName="LightingDesk",
        universe=1,
        dmxData=tuple([10, 20, 30, 40] + [0] * 508),
    )
    engine._on_sacn_passthrough_data(packet)

    buf = engine._get_passthrough_buffer(1)
    assert len(buf) == 512
    assert buf[0] == 10
    assert buf[1] == 20
    assert buf[2] == 30
    assert buf[3] == 40
    assert buf[4] == 0


def test_passthrough_receiver_network_lifecycle():
    state = StormState(pixels=4, passthrough_listen="127.0.0.1:5589")
    engine = E131LightingEngine(state)
    assert engine.receiver is None
    engine.start()
    assert engine.receiver is not None
    engine.stop()
    assert engine.receiver is None
