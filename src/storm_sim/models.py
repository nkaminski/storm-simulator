"""models.py - Core dataclasses for lightning return strokes, strike events, and simulation state."""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import List, Optional

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
    """Represents a single return stroke within a multi-stroke lightning flash."""

    offset_sec: float
    duration_sec: float
    peak_amplitude: float


@dataclass
class StrikeEvent:
    """Complete deterministic physical plan for a single lightning strike."""

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
    spatial_profile: Optional[object] = None  # Precalculated 1D numpy array profile


@dataclass
class StormState:
    """Mutable runtime state controlled via CLI defaults, live UI, and OSC messages."""

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
        """True when storm intensity is effectively zero (halts all rain, thunder, and lightning)."""
        return self.intensity <= ZERO_INTENSITY_EPSILON

    def update_ramp(self, now: float) -> None:
        """Interpolates intensity smoothly if a timed ramp is active."""
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
        """Returns 0.0 immediately if intensity is 0, otherwise calculates strike rate."""
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
        """Returns 0.0 immediately if intensity is 0, otherwise calculates rain level."""
        if self.is_zero_intensity:
            return 0.0
        if self.override_rain is not None:
            return max(0.0, min(1.0, self.override_rain))
        return math.pow(
            max(0.0, min(1.0, self.intensity)), INTENSITY_RAIN_EXPONENT
        )
