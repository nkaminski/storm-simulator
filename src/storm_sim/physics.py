"""physics.py - Mathematical modeling for optics, acoustics, and meteorology."""

from __future__ import annotations
import math
import random
from typing import List, Optional

from .constants import (
    ABSOLUTE_MIN_DIST_MILES,
    ACOUSTIC_AIR_ABSORPTION_DB_PER_MILE,
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
        # 1. Distance sampling via Intensity-skewed Beta Distribution
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

        # 2. Horizontal Epicenter
        epicenter = (
            forced_epicenter
            if forced_epicenter is not None
            else random.uniform(0.0, 1.0)
        )
        epicenter = max(0.0, min(1.0, epicenter))

        # 3. Optical Attenuation: Inverse-Square + Beer-Lambert Extinction
        rain_extinction = (
            BASE_OPTICAL_EXTINCTION
            + RAIN_OPTICAL_EXTINCTION_SCALE * state.effective_rain_level
        )
        d_min = OPTICAL_SOFTENING_DIST_MILES
        raw_intensity = (
            (d_min**2 + OPTICAL_NORM_OFFSET)
            * math.exp(-rain_extinction * d)
            / (d**2 + d_min**2)
        )
        peak_brightness = max(MIN_PEAK_BRIGHTNESS, min(1.0, raw_intensity))

        # 4. Spatial Width (Sigma): Close strikes are tight; distant strikes wash wide
        spatial_sigma = BASE_SPATIAL_SIGMA + SPATIAL_SIGMA_PER_MILE * d

        # 5. Multi-Stroke Return Envelope Generation
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

        # 6. Acoustic Propagation Delay, Attenuation, and Atmospheric LPF
        audio_delay = d / SPEED_OF_SOUND_MILES_PER_SEC
        gain_db = -20.0 * math.log10(
            max(d, ACOUSTIC_REF_DIST_MILES) / ACOUSTIC_REF_DIST_MILES
        ) - (ACOUSTIC_AIR_ABSORPTION_DB_PER_MILE * d)
        gain_db += INTENSITY_ACOUSTIC_BOOST_DB * state.intensity
        audio_gain = min(1.0, math.pow(10.0, gain_db / 20.0))

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
