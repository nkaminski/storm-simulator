"""lighting.py - E1.31 (sACN) monochrome white lighting engine."""

from __future__ import annotations
import logging
import math
import time
from typing import List

import numpy as np
import sacn

from .constants import (
    DMX_MAX_VAL,
    MAX_PIXELS_PER_UNIVERSE,
    STRIKE_ENVELOPE_TAIL_PAD_SEC,
    STROKE_DECAY_TIME_CONSTANT,
)
from .models import StormState, StrikeEvent

logger = logging.getLogger("storm_sim.lighting")


class E131LightingEngine:
    """Renders 1D monochrome white lightning envelopes to E1.31 DMX universes."""

    def __init__(self, state: StormState):
        self.state = state
        self.active_strikes: List[StrikeEvent] = []
        self.sender = sacn.sACNsender(fps=state.fps, bind_port=0)
        self.universes: List[int] = []
        self.pixel_coords = np.linspace(0.0, 1.0, state.pixels, dtype=np.float32)
        self.last_frame_dmx: np.ndarray = np.zeros(state.pixels, dtype=np.uint8)
        self._frame_white: np.ndarray = np.zeros(state.pixels, dtype=np.float32)

    def start(self) -> None:
        self.sender.start()
        self._configure_universes(self.state.pixels)
        logger.info(
            "E1.31 Monochrome Engine started: %d white pixels across universes %s (Multicast=%s, Host=%s)",
            self.state.pixels,
            self.universes,
            self.state.multicast,
            self.state.e131_host,
        )

    def _configure_universes(self, pixel_count: int) -> None:
        for u in self.universes:
            self.sender.deactivate_output(u)
        self.universes.clear()

        num_universes = math.ceil(pixel_count / MAX_PIXELS_PER_UNIVERSE)
        for idx in range(num_universes):
            univ = self.state.start_universe + idx
            self.universes.append(univ)
            self.sender.activate_output(univ)
            if self.state.e131_host and not self.state.multicast:
                self.sender[univ].destination = self.state.e131_host
                self.sender[univ].multicast = False
            else:
                self.sender[univ].multicast = True

        self.pixel_coords = np.linspace(0.0, 1.0, pixel_count, dtype=np.float32)
        self.last_frame_dmx = np.zeros(pixel_count, dtype=np.uint8)
        self._frame_white = np.zeros(pixel_count, dtype=np.float32)

    def trigger_flash(self, strike: StrikeEvent) -> None:
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

        # Transmit raw bytes directly without intermediate Python integer tuple conversion
        for idx, univ in enumerate(self.universes):
            start_px = idx * MAX_PIXELS_PER_UNIVERSE
            end_px = min(num_pixels, (idx + 1) * MAX_PIXELS_PER_UNIVERSE)
            self.sender[univ].dmx_data = dmx_bytes[start_px:end_px].tobytes()

    def stop(self) -> None:
        self.clear_all()
        time.sleep(0.05)
        self.sender.stop()
