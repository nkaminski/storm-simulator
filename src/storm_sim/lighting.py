"""lighting.py - E1.31 (sACN) lighting engine with channel mapping support.

Renders spatial 1D Gaussian flashes across multiple E1.31 universes with microsecond
temporal stroke decay, custom channel mapping (<sim_ch>:<dmx_ch>), and zero-copy byte streaming.
"""

from __future__ import annotations
import logging
import math
import time
from typing import Dict, List

import numpy as np
import sacn

from .constants import (
    DEFAULT_E131_HOST,
    DMX_MAX_VAL,
    MAX_PIXELS_PER_UNIVERSE,
    STRIKE_ENVELOPE_TAIL_PAD_SEC,
    STROKE_DECAY_TIME_CONSTANT,
)
from .models import StormState, StrikeEvent

logger = logging.getLogger("storm_sim.lighting")


class E131LightingEngine:
    """Renders 1D lightning envelopes to E1.31 DMX universes.

    Manages active lightning flashes, renders temporal envelopes sampled across
    a 1D Gaussian spatial distribution, and outputs sACN packets over UDP unicast
    (default) or multicast across configurable DMX channels and universes.

    Attributes:
        state: Reference to the shared StormState instance.
        active_strikes: Currently playing StrikeEvents undergoing envelope decay.
        sender: sacn.sACNsender instance managing network sockets and threads.
        universes: List of active universe integers assigned to cover all pixels.
        pixel_coords: Normalized coordinates [0.0 to 1.0] across all pixels.
        last_frame_dmx: 1D uint8 array holding the most recently rendered DMX bytes.
    """

    def __init__(self, state: StormState):
        """Initializes the lighting engine and preallocates frame buffers.

        Args:
            state: The shared StormState configuration.
        """
        self.state = state
        self.active_strikes: List[StrikeEvent] = []
        self.sender = sacn.sACNsender(fps=state.fps, bind_port=0)
        self.universes: List[int] = []
        self.pixel_coords = np.linspace(0.0, 1.0, state.pixels, dtype=np.float32)
        self.last_frame_dmx: np.ndarray = np.zeros(state.pixels, dtype=np.uint8)
        self._frame_white: np.ndarray = np.zeros(state.pixels, dtype=np.float32)

    def start(self) -> None:
        """Starts the underlying sACN transmitter background thread and universe outputs."""
        self.sender.start()
        self._configure_universes(self.state.pixels)
        target = "Multicast" if self.state.multicast else f"Unicast -> {self.state.e131_host or DEFAULT_E131_HOST}"
        logger.info(
            "E1.31 Lighting Engine started: %d pixels across universes %s (%s)",
            self.state.pixels,
            self.universes,
            target,
        )

    def _configure_universes(self, pixel_count: int) -> None:
        """Dynamically configures or reallocates sACN universes to match pixel count and channel map.

        Defaults to unicast transmission to e131_host (or 127.0.0.1). If a channel map is set,
        universes are allocated to accommodate all mapped DMX destination offsets.

        Args:
            pixel_count: Total number of active simulated pixels.
        """
        for u in self.universes:
            self.sender.deactivate_output(u)
        self.universes.clear()

        if self.state.channel_map:
            # Allocate all universes referenced in the channel mapping
            needed = set(
                self.state.start_universe + (offset // MAX_PIXELS_PER_UNIVERSE)
                for offset in self.state.channel_map.values()
            )
            self.universes = sorted(needed) if needed else [self.state.start_universe]
        else:
            num_universes = max(1, math.ceil(pixel_count / MAX_PIXELS_PER_UNIVERSE))
            self.universes = [self.state.start_universe + idx for idx in range(num_universes)]

        for univ in self.universes:
            self.sender.activate_output(univ)
            if not self.state.multicast:
                # Unicast mode (default)
                self.sender[univ].destination = self.state.e131_host or DEFAULT_E131_HOST
                self.sender[univ].multicast = False
            else:
                # Multicast mode
                self.sender[univ].multicast = True

        self.pixel_coords = np.linspace(0.0, 1.0, pixel_count, dtype=np.float32)
        self.last_frame_dmx = np.zeros(pixel_count, dtype=np.uint8)
        self._frame_white = np.zeros(pixel_count, dtype=np.float32)

    def trigger_flash(self, strike: StrikeEvent) -> None:
        """Enqueues a new lightning strike for real-time optical rendering.

        Precomputes the spatial Gaussian profile ahead of time to eliminate
        redundant `np.exp` calls from the 44 FPS hot rendering loop.

        Args:
            strike: StrikeEvent containing spatial parameters and stroke timing.
        """
        if not self.state.is_zero_intensity:
            # Precompute spatial profile ahead of time so render loop never calls np.exp
            if strike.spatial_profile is None or len(strike.spatial_profile) != len(self.pixel_coords):
                strike.spatial_profile = np.exp(
                    -((self.pixel_coords - strike.epicenter) ** 2)
                    / (2.0 * (strike.spatial_sigma**2))
                ).astype(np.float32)
            self.active_strikes.append(strike)

    def clear_all(self) -> None:
        """Immediately extinguishes all active lightning flashes and zeros DMX output."""
        self.active_strikes.clear()
        self.last_frame_dmx.fill(0)
        self._frame_white.fill(0.0)
        for univ in self.universes:
            self.sender[univ].dmx_data = ()

    def render_frame(self, now: float) -> None:
        """Renders one animation frame of DMX brightness values and sends via sACN.

        Iterates over all active strikes, calculates exponential decay for each
        stroke pulse, sums spatial contributions into a preallocated float32 buffer,
        clips to [0, 255], and transmits raw bytes to sACN universes using either
        sequential packing or the custom channel map.

        Args:
            now: Current monotonic timestamp in seconds.
        """
        if len(self.pixel_coords) != self.state.pixels:
            self._configure_universes(self.state.pixels)

        if self.state.is_zero_intensity:
            if self.active_strikes:
                self.clear_all()
            return

        num_pixels = self.state.pixels
        self._frame_white.fill(0.0)
        remaining_strikes: List[StrikeEvent] = []

        for strike in self.active_strikes:
            elapsed = now - strike.timestamp
            total_duration = (
                strike.strokes[-1].offset_sec
                + strike.strokes[-1].duration_sec
                + STRIKE_ENVELOPE_TAIL_PAD_SEC
            )
            if elapsed > total_duration:
                continue
            remaining_strikes.append(strike)

            temporal_amp = 0.0
            for stroke in strike.strokes:
                dt = elapsed - stroke.offset_sec
                if 0.0 <= dt <= stroke.duration_sec:
                    decay_rate = STROKE_DECAY_TIME_CONSTANT / stroke.duration_sec
                    stroke_env = stroke.peak_amplitude * math.exp(-decay_rate * dt)
                    temporal_amp = max(temporal_amp, stroke_env)

            if temporal_amp <= 0.001:
                continue

            # Fast hot-path vector multiply-add using precomputed spatial profile
            amp_scalar = (
                temporal_amp
                * strike.peak_brightness
                * self.state.master_brightness
                * DMX_MAX_VAL
            )
            self._frame_white += strike.spatial_profile * amp_scalar

        self.active_strikes = remaining_strikes

        dmx_bytes = np.clip(self._frame_white, 0, DMX_MAX_VAL).astype(np.uint8)
        self.last_frame_dmx = dmx_bytes

        # Output transmission: custom channel mapping or sequential packing
        if self.state.channel_map:
            univ_buffers: Dict[int, bytearray] = {
                u: bytearray(MAX_PIXELS_PER_UNIVERSE) for u in self.universes
            }
            for sim_idx, dmx_offset in self.state.channel_map.items():
                if sim_idx < len(dmx_bytes):
                    univ = self.state.start_universe + (dmx_offset // MAX_PIXELS_PER_UNIVERSE)
                    slot = dmx_offset % MAX_PIXELS_PER_UNIVERSE
                    if univ in univ_buffers and slot < MAX_PIXELS_PER_UNIVERSE:
                        univ_buffers[univ][slot] = dmx_bytes[sim_idx]
            for univ in self.universes:
                self.sender[univ].dmx_data = bytes(univ_buffers[univ])
        else:
            for idx, univ in enumerate(self.universes):
                start_px = idx * MAX_PIXELS_PER_UNIVERSE
                end_px = min(num_pixels, (idx + 1) * MAX_PIXELS_PER_UNIVERSE)
                self.sender[univ].dmx_data = dmx_bytes[start_px:end_px].tobytes()

    def stop(self) -> None:
        """Cleanly stops the sACN sender thread and clears outputs."""
        self.clear_all()
        time.sleep(0.05)
        self.sender.stop()
