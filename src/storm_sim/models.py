"""models.py - Core dataclasses for lightning return strokes, strike events, and simulation state.

Defines the fundamental data models representing lightning discharge physics,
return stroke sequences, and the runtime state of the storm simulator.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import List, Optional

import numpy as np

from .constants import (
    DEFAULT_FPS,
    DEFAULT_INTENSITY,
    DEFAULT_MASTER_BRIGHTNESS,
    DEFAULT_MASTER_VOLUME,
    DEFAULT_MAX_DIST_MILES,
    DEFAULT_MAX_RATE_PER_MIN,
    DEFAULT_MIN_DIST_MILES,
    DEFAULT_PIXELS,
    DEFAULT_START_UNIVERSE,
    INTENSITY_RATE_EXPONENT,
    INTENSITY_RAIN_EXPONENT,
    ZERO_INTENSITY_EPSILON,
)


@dataclass
class StrokePulse:
    """Represents a single return stroke pulse within a multi-stroke lightning flash.

    Natural lightning discharges frequently consist of an initial leader followed by
    several subsequent return strokes occurring along the same ionized plasma channel.

    Attributes:
        offset_sec: Time in seconds from the start of the strike event to this pulse.
        duration_sec: Total duration in seconds of this return stroke pulse.
        peak_amplitude: Normalized luminous amplitude [0.0 to 1.0] relative to primary stroke.
    """

    offset_sec: float
    duration_sec: float
    peak_amplitude: float


@dataclass
class StrikeEvent:
    """Complete physical plan for a deterministic lightning flash and its acoustic wave.

    Created deterministically by PhysicsEngine and dispatched to the lighting and audio
    subsystems to drive synchronized DMX optical envelopes and speed-of-sound delayed thunder.

    Attributes:
        timestamp: Monotonic start timestamp (seconds) of the strike flash.
        distance_miles: Distance from observer to the lightning strike in miles.
        epicenter: Normalized horizontal strike position [0.0 = Left, 1.0 = Right].
        peak_brightness: Attenuated optical intensity [0.0 to 1.0] from Beer-Lambert extinction.
        spatial_sigma: Standard deviation (width) of the spatial Gaussian illumination curve.
        strokes: Sequence of return stroke pulses comprising the optical envelope.
        audio_delay_sec: Acoustic travel time delay (distance / speed of sound).
        audio_gain_linear: Attenuated acoustic gain factor accounting for distance & air absorption.
        audio_lpf_hz: Low-pass filter cutoff frequency modeling atmospheric high-frequency absorption.
        stereo_pan: Stereo panning coordinate [0.0 = Left, 1.0 = Right] matching the epicenter.
        spatial_profile: Optional precomputed 1D numpy array representing the spatial Gaussian curve.
    """

    timestamp: float
    distance_miles: float
    epicenter: float  # Normalized [0.0, 1.0] across horizontal array
    peak_brightness: float  # Beer-Lambert + Inverse-Square attenuated [0.0, 1.0]
    spatial_sigma: float  # Gaussian flash width across the LED strip
    strokes: List[StrokePulse] = field(default_factory=list)
    audio_delay_sec: float = 0.0
    audio_gain_linear: float = 1.0
    audio_lpf_hz: float = 12000.0
    stereo_pan: float = 0.5  # Normalized [0.0 = Left, 1.0 = Right]
    spatial_profile: Optional[np.ndarray] = None


@dataclass
class StormState:
    """Mutable runtime state controlled via CLI defaults, live UI, and OSC messages.

    Holds the configuration for lighting hardware, meteorological intensity, distance
    bounds, timed intensity ramps, and manual parameter overrides.

    Attributes:
        pixels: Total count of 1-channel monochrome white pixels in the active array.
        e131_host: Optional IP address for unicast E1.31 sACN packets (None = multicast).
        multicast: Flag forcing E1.31 multicast operation.
        start_universe: The first E1.31 DMX universe index (typically 1).
        fps: Target frame rate for the lighting rendering loop.
        intensity: Current master storm intensity [0.0 = off / killswitch, 1.0 = maximum].
        min_dist_miles: Near boundary for strike distance sampling in miles.
        max_dist_miles: Far boundary for strike distance sampling in miles.
        max_rate_per_min: Maximum strike rate per minute at intensity 1.0.
        override_rate: Manual strike rate override (strikes/min), or None to couple to intensity.
        override_rain: Manual background rain volume override [0.0 - 1.0], or None to couple.
        master_brightness: Master lighting ceiling gain scalar [0.0 - 1.0].
        master_volume: Master audio playback volume scalar [0.0 - 1.0].
        ramp_start_val: Initial intensity value at the beginning of an active timed ramp.
        ramp_target_val: Target intensity value at the end of an active timed ramp.
        ramp_start_time: Monotonic timestamp when the current ramp began.
        ramp_duration: Duration in seconds of the active ramp (0.0 if no ramp active).
        running: Engine lifecycle control flag (False stops background task loops).
    """

    pixels: int = DEFAULT_PIXELS
    e131_host: Optional[str] = None
    multicast: bool = True
    start_universe: int = DEFAULT_START_UNIVERSE
    fps: int = DEFAULT_FPS

    intensity: float = DEFAULT_INTENSITY
    min_dist_miles: float = DEFAULT_MIN_DIST_MILES
    max_dist_miles: float = DEFAULT_MAX_DIST_MILES
    max_rate_per_min: float = DEFAULT_MAX_RATE_PER_MIN

    override_rate: Optional[float] = None
    override_rain: Optional[float] = None

    master_brightness: float = DEFAULT_MASTER_BRIGHTNESS
    master_volume: float = DEFAULT_MASTER_VOLUME

    ramp_start_val: float = DEFAULT_INTENSITY
    ramp_target_val: float = DEFAULT_INTENSITY
    ramp_start_time: float = 0.0
    ramp_duration: float = 0.0

    running: bool = True

    @property
    def is_zero_intensity(self) -> bool:
        """Indicates whether storm intensity is effectively zero.

        When True, serves as an emergency killswitch: halts background rain, cancels
        all in-transit thunder sound waves, and clears all DMX pixel outputs.
        """
        return self.intensity <= ZERO_INTENSITY_EPSILON

    def update_ramp(self, now: float) -> None:
        """Smoothly interpolates storm intensity over time if a ramp is active.

        Args:
            now: Current monotonic timestamp in seconds.
        """
        if self.ramp_duration > 0.0:
            elapsed = now - self.ramp_start_time
            if elapsed >= self.ramp_duration:
                self.intensity = self.ramp_target_val
                self.ramp_duration = 0.0
            else:
                alpha = elapsed / self.ramp_duration
                self.intensity = self.ramp_start_val + alpha * (
                    self.ramp_target_val - self.ramp_start_val
                )

    @property
    def effective_rate_per_sec(self) -> float:
        """Calculates current strike generation rate in strikes per second.

        Returns 0.0 immediately if storm intensity is zero. If a manual rate override
        is set, uses that value; otherwise computes rate via non-linear power-law scaling:
            rate = (max_rate / 60) * (intensity ^ INTENSITY_RATE_EXPONENT)
        """
        if self.is_zero_intensity:
            return 0.0
        if self.override_rate is not None:
            return max(0.0, self.override_rate / 60.0)
        return (
            self.max_rate_per_min
            * math.pow(max(0.0, self.intensity), INTENSITY_RATE_EXPONENT)
        ) / 60.0

    @property
    def effective_rain_level(self) -> float:
        """Calculates current background rain audio volume [0.0 to 1.0].

        Returns 0.0 immediately if storm intensity is zero. If a manual rain override
        is set, uses that value; otherwise computes volume via non-linear power-law scaling:
            rain = intensity ^ INTENSITY_RAIN_EXPONENT
        """
        if self.is_zero_intensity:
            return 0.0
        if self.override_rain is not None:
            return max(0.0, min(1.0, self.override_rain))
        return math.pow(
            max(0.0, min(1.0, self.intensity)), INTENSITY_RAIN_EXPONENT
        )
