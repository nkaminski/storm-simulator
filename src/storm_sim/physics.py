"""physics.py - Mathematical modeling for optics, acoustics, and meteorology.

Provides the pure mathematical physics engine governing distance sampling, Beer-Lambert
optical extinction, spatial Gaussian illumination dispersion, multi-stroke envelope
timing, acoustic speed-of-sound propagation delays, and atmospheric low-pass filtering.

See MODEL_CITATIONS.md for formal scientific literature and theoretical foundations.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional

from .constants import (
    ABSOLUTE_MIN_DIST_MILES,
    ACOUSTIC_CYLINDRICAL_SPREADING_FACTOR,
    ACOUSTIC_REF_DIST_MILES,
    BASE_OPTICAL_EXTINCTION,
    BASE_SPATIAL_SIGMA,
    BETA_DIST_SKEW_WEIGHT,
    INTENSITY_ACOUSTIC_BOOST_DB,
    INTER_STROKE_GAP_RANGE_SEC,
    LPF_DISTANCE_ROLLOFF_FACTOR,
    LPF_REFERENCE_NUMERATOR_HZ,
    MAX_EXTRA_STROKES_AT_PEAK,
    MAX_LPF_CUTOFF_HZ,
    MIN_LPF_CUTOFF_HZ,
    MIN_PEAK_BRIGHTNESS,
    OPTICAL_DISTANCE_EXPONENT,
    OPTICAL_NORM_OFFSET,
    OPTICAL_SOFTENING_DIST_MILES,
    PRIMARY_STROKE_DURATION_RANGE_SEC,
    RAIN_OPTICAL_EXTINCTION_SCALE,
    SECONDARY_STROKE_AMP_RANGE,
    SECONDARY_STROKE_DURATION_RANGE_SEC,
    SPATIAL_SIGMA_PER_MILE,
    SPEED_OF_SOUND_MILES_PER_SEC,
)
from .models import StormState, StrikeEvent, StrokePulse


class PhysicsEngine:
    """Pure mathematical modeling for optics, acoustics, and meteorology."""

    @classmethod
    def generate_strike(
        cls,
        state: StormState,
        now: float,
        forced_dist: Optional[float] = None,
        forced_epicenter: Optional[float] = None,
    ) -> StrikeEvent:
        """Generates a complete deterministic physical plan for a lightning strike.

        Combines optical propagation, luminous envelope generation, and acoustic
        speed-of-sound delay calculation into a unified StrikeEvent.

        Args:
            state: The active StormState containing meteorology settings and bounds.
            now: Current monotonic timestamp in seconds.
            forced_dist: Optional forced distance in miles (used for manual triggers).
            forced_epicenter: Optional forced horizontal epicenter [0.0 - 1.0].

        Returns:
            A StrikeEvent containing the optical envelope, spatial sigma, audio delay,
            LPF cutoff, gain scalar, and stereo pan position.
        """
        # ----------------------------------------------------------------------
        # 1. Distance sampling via Intensity-Skewed Beta Distribution
        # ----------------------------------------------------------------------
        # When intensity s -> 1.0, beta increases and alpha decreases, skewing
        # random draws toward the minimum distance (frequent close overhead bolts).
        # When intensity s -> 0.0, alpha increases, pushing strikes to the horizon.
        if forced_dist is not None:
            d = max(ABSOLUTE_MIN_DIST_MILES, forced_dist)
        else:
            s = max(0.0, min(1.0, state.intensity))
            alpha = 1.0 + BETA_DIST_SKEW_WEIGHT * (1.0 - s)
            beta = 1.0 + BETA_DIST_SKEW_WEIGHT * s
            norm_d = random.betavariate(alpha, beta)
            d = state.min_dist_miles + norm_d * (
                state.max_dist_miles - state.min_dist_miles
            )

        # ----------------------------------------------------------------------
        # 2. Horizontal Epicenter
        # ----------------------------------------------------------------------
        # Coordinates along the LED strip: 0.0 = Leftmost pixel, 1.0 = Rightmost
        epicenter = (
            forced_epicenter
            if forced_epicenter is not None
            else random.uniform(0.0, 1.0)
        )
        epicenter = max(0.0, min(1.0, epicenter))

        # ----------------------------------------------------------------------
        # 3. Optical Attenuation: Diffuse Line-Source + Beer-Lambert Extinction
        # ----------------------------------------------------------------------
        # Combines diffuse geometric 1/(d^p + d_min^p) attenuation (cloud scattering
        # and extended channel length) with exponential atmospheric extinction:
        # exp(-extinction * d), scaled by current rainfall density.
        rain_extinction = (
            BASE_OPTICAL_EXTINCTION
            + RAIN_OPTICAL_EXTINCTION_SCALE * state.effective_rain_level
        )
        d_min = OPTICAL_SOFTENING_DIST_MILES
        p = OPTICAL_DISTANCE_EXPONENT
        raw_intensity = (
            (d_min**p + OPTICAL_NORM_OFFSET)
            * math.exp(-rain_extinction * d)
            / (d**p + d_min**p)
        )
        peak_brightness = max(MIN_PEAK_BRIGHTNESS, min(1.0, raw_intensity))

        # ----------------------------------------------------------------------
        # 4. Spatial Width (Sigma): Gaussian flash dispersion across LED strip
        # ----------------------------------------------------------------------
        # Close strikes illuminate a focused, localized region of pixels; distant
        # strikes scatter through clouds and sheet across the entire horizon.
        spatial_sigma = BASE_SPATIAL_SIGMA + SPATIAL_SIGMA_PER_MILE * d

        # ----------------------------------------------------------------------
        # 5. Multi-Stroke Return Envelope Generation
        # ----------------------------------------------------------------------
        # Multi-stroke lightning flashes: an initial leader/stroke pulse followed
        # by 0 to N secondary pulses along the ionized channel.
        max_extra_strokes = int(round(MAX_EXTRA_STROKES_AT_PEAK * state.intensity))
        num_strokes = 1 + random.randint(0, max_extra_strokes)
        strokes: List[StrokePulse] = []
        t_cursor = 0.0
        for idx in range(num_strokes):
            amp = 1.0 if idx == 0 else random.uniform(*SECONDARY_STROKE_AMP_RANGE)
            dur = (
                random.uniform(*PRIMARY_STROKE_DURATION_RANGE_SEC)
                if idx == 0
                else random.uniform(*SECONDARY_STROKE_DURATION_RANGE_SEC)
            )
            strokes.append(
                StrokePulse(
                    offset_sec=t_cursor, duration_sec=dur, peak_amplitude=amp
                )
            )
            t_cursor += dur + random.uniform(*INTER_STROKE_GAP_RANGE_SEC)

        # ----------------------------------------------------------------------
        # 6. Acoustic Propagation Delay, Attenuation, and Atmospheric LPF
        # ----------------------------------------------------------------------
        # Delay: Speed of sound (~4.69 sec/mile).
        # Geometric Attenuation: Line-source cylindrical wave expansion (-11 dB per decade)
        # reflecting the multi-kilometer vertical/horizontal lightning channel.
        # LPF: High frequencies are absorbed over distance, leaving deep sub-bass rumbles.
        audio_delay = d / SPEED_OF_SOUND_MILES_PER_SEC
        eff_d = max(ACOUSTIC_REF_DIST_MILES, d)
        loss_db = -ACOUSTIC_CYLINDRICAL_SPREADING_FACTOR * math.log10(
            eff_d / ACOUSTIC_REF_DIST_MILES
        )
        gain_db = loss_db + (INTENSITY_ACOUSTIC_BOOST_DB * state.intensity)
        audio_gain = max(0.05, min(1.0, math.pow(10.0, gain_db / 20.0)))

        lpf_hz = max(
            MIN_LPF_CUTOFF_HZ,
            min(
                MAX_LPF_CUTOFF_HZ,
                LPF_REFERENCE_NUMERATOR_HZ
                / (1.0 + LPF_DISTANCE_ROLLOFF_FACTOR * d),
            ),
        )

        return StrikeEvent(
            timestamp=now,
            distance_miles=d,
            epicenter=epicenter,
            peak_brightness=peak_brightness,
            spatial_sigma=spatial_sigma,
            strokes=strokes,
            audio_delay_sec=audio_delay,
            audio_gain_linear=audio_gain,
            audio_lpf_hz=lpf_hz,
            stereo_pan=epicenter,
        )
