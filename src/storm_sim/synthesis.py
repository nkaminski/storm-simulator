"""synthesis.py - Procedural audio synthesis for thunder and ambient rain.

Dedicated generator class with its own CLI to produce dry thunderclap models
and seamless stereo rain loops ahead-of-time (AOT) for resource-constrained systems.
"""

from __future__ import annotations
import argparse
import logging
from pathlib import Path
import random
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import signal
import soundfile as sf

from .constants import (
    AUDIO_SAMPLE_RATE,
    BUTTERWORTH_FILTER_ORDER,
    DEFAULT_SMALL_SPEAKERS,
    PROCEDURAL_VARIATIONS_PER_TIER,
    SAMPLE_PEAK_NORMALIZE_TARGET,
    SYNTH_BURST_AMP_RANGE,
    SYNTH_BURST_TIME_SPAN_FACTOR,
    SYNTH_BURST_WIDTH_RANGE_SEC,
    SYNTH_CLOSE_DECAY_TIME,
    SYNTH_CLOSE_INITIAL_SNAP_AMP,
    SYNTH_CLOSE_INITIAL_SNAP_DECAY,
    SYNTH_FAR_DECAY_TIME,
    SYNTH_INFRA_BAND_HZ,
    SYNTH_INFRA_BAND_SMALL_SPEAKERS_HZ,
    SYNTH_RAIN_BANDPASS_HZ,
    SYNTH_RAIN_CROSSFADE_SEC,
    SYNTH_RAIN_LOOP_DURATION_SEC,
    SYNTH_RAIN_NOISE_AMPLITUDE,
    SYNTH_SUB_BASS_BAND_HZ,
    SYNTH_SUB_BASS_BAND_SMALL_SPEAKERS_HZ,
    SYNTH_THUNDER_BURSTS_RANGE,
    SYNTH_THUNDER_DURATIONS_SEC,
    SYNTH_THUNDER_LPF_HZ,
)

logger = logging.getLogger("storm_sim.synthesis")


class ThunderSynthesizer:
    """Dedicated procedural acoustic synthesizer for lightning thunder and rain.

    Produces synthetic acoustic waveforms using multi-burst filtered Gaussian noise
    and exponential envelopes. Capable of generating in-memory numpy audio arrays or
    exporting pre-rendered 24/48kHz WAV files to disk for zero-overhead runtime loading.

    Attributes:
        sample_rate: Target sample rate in Hz (default: 44100).
    """

    def __init__(
        self,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        small_speakers: bool = DEFAULT_SMALL_SPEAKERS,
    ):
        """Initializes the procedural synthesizer.

        Args:
            sample_rate: Target audio sample rate in Hz.
            small_speakers: If True, tunes infrasonic/sub-bass frequencies higher (48-140 Hz)
                with harmonic overtone saturation for compact speakers lacking subwoofers.
        """
        self.sample_rate = sample_rate
        self.small_speakers = small_speakers

    def _get_explosion_attack(self) -> Optional[np.ndarray]:
        """Loads, extracts, and caches the authentic outdoor explosion attack transient."""
        if hasattr(self, "_cached_explosion_attack"):
            return self._cached_explosion_attack

        candidates = [
            Path("assets/explosion-outdoors-medium.wav"),
            Path("explosion-outdoors-medium.wav"),
            Path(__file__).resolve().parent.parent.parent / "explosion-outdoors-medium.wav",
            Path(__file__).resolve().parent.parent.parent / "assets" / "explosion-outdoors-medium.wav",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    data, sr = sf.read(str(p))
                    if data.ndim > 1:
                        data = data[:, 0]
                    pk_idx = int(np.argmax(np.abs(data)))
                    start_idx = max(0, pk_idx - int(0.004 * sr))
                    end_idx = start_idx + int(0.380 * sr)
                    attack = data[start_idx:end_idx].copy().astype(np.float32)
                    if sr != self.sample_rate:
                        num_s = int(len(attack) * self.sample_rate / sr)
                        attack = signal.resample(attack, num_s).astype(np.float32)
                    fade_len = int(0.070 * self.sample_rate)
                    attack[-fade_len:] *= 0.5 * (
                        1.0 + np.cos(np.linspace(0, np.pi, fade_len, dtype=np.float32))
                    )
                    peak = float(np.max(np.abs(attack)))
                    if peak > 0:
                        attack /= peak
                    self._cached_explosion_attack = attack
                    return attack
                except Exception as e:
                    logger.debug("Failed reading explosion sound: %s", e)

        self._cached_explosion_attack = None
        return None

    def synthesize_thunder(self, tier: str) -> np.ndarray:
        """Synthesizes an authentic, floor-shaking multi-layer thunderclap for a given distance tier.

        Grounded in empirical thunder acoustics (Few 1969; Holmes et al. 1971; Ribner & Roy 1982):
        1. Infrasonic & Sub-Bass Cylindrical Shockwave Body (20 Hz - 85 Hz):
           Plasma channel expansion wave producing dominant acoustic power density (>90% of power
           below 100 Hz) in the wall-shaking sub-bass region. When small_speakers is active,
           elevates to 48-140 Hz with harmonic saturation for playback on compact monitors.
        2. Low-Frequency Tortuous Channel Resonance & Echoes (55 Hz - 190 Hz):
           Multi-burst packet arrivals modeling tortuous channel kinks across kilometers with natural
           1/f^2 spectral roll-off.
        3. Tortuous N-Wave Shock Cluster Clap (Close and Mid tiers, 90 Hz - 2400 Hz):
           Single dominant, explosive primary crack followed by much quieter secondary return-stroke
           kinks (eliminating repetitive clicks) with calibrated multi-band saturation.
        4. Environmental Building Reflections & Canyon Reverberation:
           Smeared specular facade slapbacks and diffuse horizon reverberation.

        Args:
            tier: Distance tier string: 'close', 'mid', or 'far'.

        Returns:
            1D float32 numpy array containing the synthesized mono thunderclap.
        """
        dur = SYNTH_THUNDER_DURATIONS_SEC.get(tier, 7.5)
        n = int(self.sample_rate * dur)
        t = np.linspace(0.0, dur, n, dtype=np.float32)

        # ----------------------------------------------------------------------
        # Layer 1: Infrasonic & Sub-Bass Shockwave Body
        # Dominates total acoustic energy (>90% of power in 20-100 Hz band).
        # In small_speakers mode, elevates to 48-140 Hz for compact monitors.
        # ----------------------------------------------------------------------
        sub_band = (
            SYNTH_SUB_BASS_BAND_SMALL_SPEAKERS_HZ
            if self.small_speakers
            else SYNTH_SUB_BASS_BAND_HZ
        )
        infra_band = (
            SYNTH_INFRA_BAND_SMALL_SPEAKERS_HZ
            if self.small_speakers
            else SYNTH_INFRA_BAND_HZ
        )

        white_sub = np.random.normal(0.0, 1.0, n).astype(np.float32)
        sos_sub = signal.butter(
            4, list(sub_band), btype="bandpass", fs=self.sample_rate, output="sos"
        )
        sub_noise = signal.sosfilt(sos_sub, white_sub)

        # Deep infrasonic/sub-bass rolling tail carrier from upper channel & horizon
        white_infra = np.random.normal(0.0, 1.0, n).astype(np.float32)
        sos_infra = signal.butter(
            4, list(infra_band), btype="bandpass", fs=self.sample_rate, output="sos"
        )
        infra_noise = signal.sosfilt(sos_infra, white_infra)

        # Infrasonic/Sub-bass plasma expansion wave pulses (1 to 3 distinct return-stroke booms)
        attack_ramp = 1.0 - np.exp(-t / 0.012)
        n_booms = random.randint(1, 3)
        boom = np.zeros(n, dtype=np.float32)
        boom_times = []
        if tier == "close":
            sub_decay = 1.8
            infra_tail_decay = 2.4
        elif tier == "mid":
            sub_decay = 3.2
            infra_tail_decay = 4.5
        else:  # far
            sub_decay = 5.0
            infra_tail_decay = 7.0

        t_boom = 0.0
        for b_idx in range(n_booms):
            boom_times.append(t_boom)
            dt_b = t - t_boom
            mask_b = dt_b >= 0.0
            dt_bp = dt_b[mask_b]
            attack_b = 1.0 - np.exp(-dt_bp / 0.012)
            if self.small_speakers:
                # Elevated sub-bass chirp profile (50-95 Hz) audible on small bookshelf/desktop drivers
                if tier == "close":
                    b_env = attack_b * np.exp(-dt_bp / random.uniform(0.42, 0.65))
                    b_freq = (56.0 + random.uniform(-4.0, 4.0)) + 38.0 * np.exp(-dt_bp / 0.12)
                    b_gain = 2.2 if b_idx == 0 else random.uniform(1.2, 1.7)
                elif tier == "mid":
                    b_env = attack_b * np.exp(-dt_bp / random.uniform(0.70, 1.05))
                    b_freq = (50.0 + random.uniform(-4.0, 4.0)) + 28.0 * np.exp(-dt_bp / 0.18)
                    b_gain = 1.6 if b_idx == 0 else random.uniform(1.0, 1.4)
                else:  # far
                    b_env = attack_b * np.exp(-dt_bp / random.uniform(1.2, 1.7))
                    b_freq = (44.0 + random.uniform(-3.0, 3.0)) + 20.0 * np.exp(-dt_bp / 0.25)
                    b_gain = 1.1 if b_idx == 0 else random.uniform(0.7, 1.0)
            else:
                # Standard true infrasonic/sub-bass chirp (24-58 Hz) for subwoofers/full-range systems
                if tier == "close":
                    b_env = attack_b * np.exp(-dt_bp / random.uniform(0.42, 0.65))
                    b_freq = (34.0 + random.uniform(-3.0, 3.0)) + 22.0 * np.exp(-dt_bp / 0.12)
                    b_gain = 2.2 if b_idx == 0 else random.uniform(1.2, 1.7)
                elif tier == "mid":
                    b_env = attack_b * np.exp(-dt_bp / random.uniform(0.70, 1.05))
                    b_freq = (30.0 + random.uniform(-3.0, 3.0)) + 16.0 * np.exp(-dt_bp / 0.18)
                    b_gain = 1.6 if b_idx == 0 else random.uniform(1.0, 1.4)
                else:  # far
                    b_env = attack_b * np.exp(-dt_bp / random.uniform(1.2, 1.7))
                    b_freq = (26.0 + random.uniform(-2.0, 2.0)) + 12.0 * np.exp(-dt_bp / 0.25)
                    b_gain = 1.1 if b_idx == 0 else random.uniform(0.7, 1.0)

            phase = 2.0 * np.pi * np.cumsum(b_freq) / self.sample_rate
            boom[mask_b] += np.sin(phase) * b_env * b_gain
            t_boom += random.uniform(0.12, 0.28)

        if self.small_speakers:
            # Subtle soft-clip saturation adds 2nd & 3rd harmonic overtones audible on compact speakers
            boom = np.tanh(boom * 1.35)

        # Tortuous channel secondary bursts (interference from upper segments)
        sub_env = attack_ramp * np.exp(-t / sub_decay)
        n_bursts = random.randint(4, 7) if tier == "close" else random.randint(6, 10)
        max_burst_span = min(dur * 0.45, 2.5) if tier == "close" else dur * 0.65
        for _ in range(n_bursts):
            bt = random.uniform(0.20, max_burst_span)
            bw = random.uniform(0.25, 0.75)
            bamp = random.uniform(0.30, 0.70) * np.exp(-bt / (max_burst_span * 1.2))
            sub_env += bamp * np.exp(-((t - bt) ** 2) / (2.0 * (bw**2)))

        # Infrasonic tail (20 - 52 Hz) with fast, natural decay (fades cleanly by 3-4s)
        infra_env = (1.0 - np.exp(-t / 0.18)) * np.exp(-t / infra_tail_decay)
        for _ in range(random.randint(3, 5)):
            bt_i = random.uniform(0.8, min(dur * 0.5, 3.2))
            bw_i = random.uniform(0.40, 0.90)
            bamp_i = random.uniform(0.25, 0.55) * np.exp(-bt_i / (dur * 0.5))
            infra_env += bamp_i * np.exp(-((t - bt_i) ** 2) / (2.0 * (bw_i**2)))

        # Smooth cosine fade-out on final 1.0s so tail ends cleanly
        fade_len = int(1.0 * self.sample_rate)
        if fade_len < n:
            fade_win = np.ones(n, dtype=np.float32)
            fade_win[-fade_len:] = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, fade_len)))
            sub_env *= fade_win
            infra_env *= fade_win

        sub_layer = (sub_noise * 3.0 * sub_env) + (infra_noise * 3.2 * infra_env) + boom
        sub_layer = sub_layer / max(float(np.max(np.abs(sub_layer))), 1e-6)

        # ----------------------------------------------------------------------
        # Layer 2: Low-Mid Tortuous Resonance & Channel Echoes (55 - 185 Hz)
        # ----------------------------------------------------------------------
        white_mid = np.random.normal(0.0, 1.0, n).astype(np.float32)
        sos_mid = signal.butter(
            3, [55.0, 185.0], btype="bandpass", fs=self.sample_rate, output="sos"
        )
        mid_noise = signal.sosfilt(sos_mid, white_mid)
        mid_env = attack_ramp * np.exp(-t / (sub_decay * 0.70))
        for _ in range(n_bursts):
            bt = random.uniform(0.12, dur * 0.55)
            bw = random.uniform(0.10, 0.38)
            bamp = random.uniform(0.35, 0.80)
            mid_env += bamp * np.exp(-((t - bt) ** 2) / (2.0 * (bw**2)))
        mid_layer = mid_noise * mid_env
        mid_layer = mid_layer / max(float(np.max(np.abs(mid_layer))), 1e-6)

        # ----------------------------------------------------------------------
        # Layer 3: Multi-Band Dry Thunder Crack & Stepped-Leader Tear (90 - 2400 Hz)
        # Calibrated directly against empirical analysis of dry-thunder3.wav:
        #   - Stepped-Leader Tearing Prelude (0.01 - 0.16s, 350 - 2350 Hz):
        #     Staccato, high-crest-factor micro-snaps preceding the main shockwave.
        #   - Low-Bark (90 - 250 Hz, Crest ~6.1): Nonlinear shock-steepened artillery punch.
        #   - Mid-Crack (250 - 700 Hz, Crest ~5.1): Dry, woody explosive crack body.
        #   - High-Tear (700 - 2350 Hz, Crest ~8.3, Kurtosis ~7.0): Super-Gaussian spiky
        #     crackle gated to the leading edges of each shockwave kink, rolling off
        #     steeply above 2.4 kHz (<0.05% energy >3 kHz) to avoid white-noise hiss.
        # ----------------------------------------------------------------------
        # Layer 3: Multi-Clap Dry Thunder Crack & Outdoor Pressure Shockwave
        # Grounded in empirical analysis of dry-thunder3.wav & explosion-outdoors-medium.wav:
        #   - Friedlander Bipolar Outdoor Shock Front: Razor-sharp pressure wave arrival
        #     (positive compression peak + 2.2 ms ground reflection rarefaction).
        #   - Multi-Clap Barrage (6 to 9 claps for close): Overlapping shock arrivals from
        #     crooked channel kinks (Ribner & Roy 1982) delivering continuous explosive tearing.
        #   - Low-Bark (90 - 250 Hz, Crest ~14): Visceral outdoor explosion body punch.
        #   - Mid-Crack (250 - 700 Hz, Crest ~13): Dry, woody explosive crack body.
        #   - High-Tear (700 - 2350 Hz, Crest ~16): Ripping air displacement.
        # ----------------------------------------------------------------------
        if tier in ("close", "mid"):
            # Generate 3 band-limited carriers matching dry-thunder3.wav sub-bands
            w1 = np.random.normal(0.0, 1.0, n).astype(np.float32)
            w2 = np.random.normal(0.0, 1.0, n).astype(np.float32)
            w3 = np.random.normal(0.0, 1.0, n).astype(np.float32)

            sos_bark = signal.butter(
                3, [90.0, 250.0], btype="bandpass", fs=self.sample_rate, output="sos"
            )
            sos_midc = signal.butter(
                3, [250.0, 700.0], btype="bandpass", fs=self.sample_rate, output="sos"
            )
            sos_tear = signal.butter(
                3, [700.0, 2350.0], btype="bandpass", fs=self.sample_rate, output="sos"
            )

            c_bark = signal.sosfilt(sos_bark, w1)
            c_midc = signal.sosfilt(sos_midc, w2)
            c_tear = signal.sosfilt(sos_tear, w3)

            # Smooth natural tearing modulation on high-tear band
            w_mod = np.random.normal(0.0, 1.0, n).astype(np.float32)
            sos_mod = signal.butter(
                2, [45.0, 280.0], btype="bandpass", fs=self.sample_rate, output="sos"
            )
            grain_mod = np.abs(signal.sosfilt(sos_mod, w_mod))
            grain_mod = np.tanh(grain_mod / max(float(np.std(grain_mod)), 1e-6))
            c_tear = c_tear * (0.45 + 1.10 * grain_mod)

            env_bark = np.zeros(n, dtype=np.float32)
            env_midc = np.zeros(n, dtype=np.float32)
            env_tear = np.zeros(n, dtype=np.float32)
            shock_layer = np.zeros(n, dtype=np.float32)

            # Multi-clap barrage: 6 to 9 claps (close) or 4 to 6 claps (mid)
            n_claps = random.randint(6, 9) if tier == "close" else random.randint(4, 6)
            t_clap = 0.08 if tier == "close" else 0.05
            for c_idx in range(n_claps):
                dt_c = t - t_clap
                mask_c = (dt_c >= 0.0) & (dt_c <= 0.65)
                dt_cp = dt_c[mask_c]

                # Main claps peak across primary tortuous kinks, then decay smoothly
                c_amp = (
                    random.uniform(0.85, 1.0)
                    if c_idx in (0, 1, 2)
                    else random.uniform(0.40, 0.75) * np.exp(-(c_idx - 2) / 3.2)
                )
                w_bark = random.uniform(0.040, 0.080)
                w_midc = random.uniform(0.028, 0.058)
                w_tear = random.uniform(0.016, 0.034)

                env_bark[mask_c] += c_amp * (1.0 - np.exp(-dt_cp / 0.003)) * np.exp(-dt_cp / w_bark)
                env_midc[mask_c] += c_amp * (1.0 - np.exp(-dt_cp / 0.002)) * np.exp(-dt_cp / w_midc)
                env_tear[mask_c] += c_amp * (1.0 - np.exp(-dt_cp / 0.0015)) * np.exp(-dt_cp / w_tear)

                # Friedlander outdoor pressure shockwave (ground truth from explosion-outdoors-medium.wav)
                mask_s = (dt_c >= 0.0) & (dt_c < 0.045)
                dt_s = dt_c[mask_s]
                p_direct = (1.0 - dt_s / 0.0035) * np.exp(-dt_s / 0.005)
                p_refl = np.zeros_like(dt_s)
                mask_r = dt_s >= 0.0022
                p_refl[mask_r] = (
                    -0.42 * (1.0 - (dt_s[mask_r] - 0.0022) / 0.004)
                    * np.exp(-(dt_s[mask_r] - 0.0022) / 0.007)
                )
                shock_layer[mask_s] += c_amp * (p_direct + p_refl)

                t_clap += random.uniform(0.045, 0.095)

            # Shape each band with soft-saturation to match outdoor explosion crest factors (10 - 15)
            sig_bark = np.tanh(
                (c_bark / max(float(np.std(c_bark)), 1e-6)) * env_bark * 0.85
            )
            sig_bark = sig_bark / max(float(np.max(np.abs(sig_bark))), 1e-6)

            sig_midc = np.tanh(
                (c_midc / max(float(np.std(c_midc)), 1e-6)) * env_midc * 0.85
            )
            sig_midc = sig_midc / max(float(np.max(np.abs(sig_midc))), 1e-6)

            sig_tear = np.tanh(
                (c_tear / max(float(np.std(c_tear)), 1e-6)) * env_tear * 0.70
            )
            sig_tear = sig_tear / max(float(np.max(np.abs(sig_tear))), 1e-6)

            shock_norm = shock_layer / max(float(np.max(np.abs(shock_layer))), 1e-6)

            if tier == "close":
                crack_raw = (
                    (sig_bark * 0.85)
                    + (sig_midc * 0.65)
                    + (sig_tear * 0.50)
                    + (shock_norm * 0.42)
                )
                cutoff_crack = 2450.0
            else:  # mid
                crack_raw = (
                    (sig_bark * 0.55)
                    + (sig_midc * 0.35)
                    + (sig_tear * 0.16)
                    + (shock_norm * 0.22)
                )
                cutoff_crack = 1050.0

            sos_crack_lpf = signal.butter(
                4, cutoff_crack, btype="low", fs=self.sample_rate, output="sos"
            )
            crack_layer = signal.sosfilt(sos_crack_lpf, crack_raw)

            # Blend authentic outdoor explosion attack transient for close overhead strikes (< 1 mile).
            # As distance increases past 1 mile (mid tier), atmospheric molecular relaxation absorption
            # dissolves the shock front, transitioning into traditional rolling thunder.
            exp_attack = self._get_explosion_attack()
            if exp_attack is not None:
                att_len = len(exp_attack)
                t_start = int(0.02 * self.sample_rate)
                if t_start + att_len < n:
                    if tier == "close":
                        # Full razor-sharp blast wave attack (< 1 mile)
                        crack_layer[t_start : t_start + att_len] = (
                            crack_layer[t_start : t_start + att_len] * 0.45
                            + exp_attack * 0.88
                        )
                    else:  # mid tier (> 1 mile)
                        # Absorbed by distance: traditional thunder dominates, explosion reduced & rounded
                        sos_att = signal.butter(
                            2, 320.0, btype="low", fs=self.sample_rate, output="sos"
                        )
                        att_soft = signal.sosfilt(sos_att, exp_attack)
                        crack_layer[t_start : t_start + att_len] = (
                            crack_layer[t_start : t_start + att_len] * 0.85
                            + att_soft * 0.18
                        )
        else:
            crack_layer = np.zeros(n, dtype=np.float32)

        # ----------------------------------------------------------------------
        # Layer 4: Environmental Building Echoes & Urban Canyon Reverberation
        # Models discrete specular reflections off nearby/mid-field building facades
        # and structures plus diffuse urban canyon / terrain late reverberation.
        # ----------------------------------------------------------------------
        low_body = (sub_layer * 0.85) + (mid_layer * 0.35)
        rev_body = self._apply_environmental_reflections(low_body, tier)
        rev_body = rev_body / max(float(np.max(np.abs(rev_body))), 1e-6)

        if tier in ("close", "mid"):
            rev_crack = self._apply_crack_building_echoes(crack_layer, tier)
            rev_crack = rev_crack / max(float(np.max(np.abs(rev_crack))), 1e-6)
            rev_crack = np.tanh(rev_crack * 1.35)
            rev_crack = rev_crack / max(float(np.max(np.abs(rev_crack))), 1e-6)
            if tier == "close":
                # Keep scary infrasonic/sub-bass strong (0.68) alongside dry-thunder3.wav sharp crack (1.05)
                composite = (rev_body * 0.68) + (rev_crack * 1.05)
            else:
                composite = (rev_body * 0.82) + (rev_crack * 0.58)
        else:
            composite = rev_body

        sos_master_lpf = signal.butter(
            3,
            SYNTH_THUNDER_LPF_HZ.get(tier, 280.0),
            btype="low",
            fs=self.sample_rate,
            output="sos",
        )
        composite = signal.sosfilt(sos_master_lpf, composite)
        peak = float(np.max(np.abs(composite)))
        normalized = (composite / max(peak, 1e-6)) * SAMPLE_PEAK_NORMALIZE_TARGET
        return normalized.astype(np.float32)

    def _apply_crack_building_echoes(
        self, crack: np.ndarray, tier: str
    ) -> np.ndarray:
        """Applies discrete specular building facade echoes to the mid/high thunder crack.

        Preserves the 120-1600 Hz slapback and multi-building echoes of a sharp thunderclap
        bouncing off nearby structures without swamping it in sub-bass reverberation.
        """
        n = len(crack)
        out = crack.copy().astype(np.float64)
        tap_delays = [
            (0.080, 0.150, 0.38, 1400.0),
            (0.220, 0.380, 0.25, 850.0),
            (0.480, 0.780, 0.16, 520.0),
        ]
        for idx, (d_min, d_max, gain, lpf_hz) in enumerate(tap_delays):
            delay_sec = random.uniform(d_min, d_max)
            delay_samples = int(delay_sec * self.sample_rate)
            if delay_samples >= n:
                continue
            sos_e = signal.butter(
                2,
                lpf_hz if tier == "close" else lpf_hz * 0.6,
                btype="low",
                fs=self.sample_rate,
                output="sos",
            )
            echo_sig = signal.sosfilt(sos_e, crack)
            smear_len = max(3, int(0.012 * self.sample_rate))
            k_t = np.linspace(-2.0, 2.0, smear_len)
            kernel = np.exp(-0.5 * (k_t**2))
            kernel /= np.sum(kernel)
            smeared_echo = signal.fftconvolve(echo_sig, kernel, mode="same")
            polarity = -1.0 if (idx % 2 == 1) else 1.0
            out[delay_samples:] += (
                polarity * gain * random.uniform(0.8, 1.2) * smeared_echo[: n - delay_samples]
            )
        return out.astype(np.float32)

    def _apply_environmental_reflections(
        self, direct: np.ndarray, tier: str
    ) -> np.ndarray:
        """Applies discrete specular building reflections and diffuse urban/terrain reverberation.

        Models acoustic wave propagation through a built/natural environment (Kang 2006;
        Hornikx & Forssén 2009):
        1. Discrete Specular Building Reflections (65 ms - 2,400 ms):
           Multi-tap reflections from nearby building facades, street canyons, and distant
           structures. Each reflection undergoes inverse-distance attenuation, finite-width
           facade temporal smearing (8-22 ms), and progressive low-pass filtering due to
           high-frequency scattering and low-frequency diffraction around structures.
        2. Diffuse Urban Canyon / Terrain Late Reverberation Tail:
           Exponentially decaying velvet-noise scatterer network low-pass filtered below
           115 Hz, turning initial claps into rolling, booming architectural/horizon echoes.

        Args:
            direct: 1D numpy array containing the dry synthesized thunder waveform.
            tier: Distance tier ('close', 'mid', or 'far').

        Returns:
            1D float32 numpy array with specular building echoes and diffuse reverberation.
        """
        n = len(direct)
        out = direct.copy().astype(np.float64)

        # 1. Discrete specular building & structure echoes (staggered delay zones)
        if tier == "close":
            delay_zones = [
                (0.065, 0.140),
                (0.150, 0.280),
                (0.310, 0.520),
                (0.560, 0.850),
                (0.920, 1.350),
                (1.420, 1.950),
                (2.050, 2.750),
                (2.900, 3.800),
                (4.000, 5.200),
            ]
            base_echo_gain = 0.44
            reverb_decay = 2.40
            reverb_mix = 0.36
        elif tier == "mid":
            delay_zones = [
                (0.090, 0.210),
                (0.240, 0.450),
                (0.490, 0.820),
                (0.880, 1.350),
                (1.450, 2.100),
                (2.200, 3.100),
                (3.300, 4.500),
                (4.700, 6.200),
            ]
            base_echo_gain = 0.46
            reverb_decay = 2.95
            reverb_mix = 0.40
        else:  # far
            delay_zones = [
                (0.140, 0.350),
                (0.420, 0.850),
                (0.950, 1.600),
                (1.750, 2.700),
                (2.850, 4.100),
                (4.300, 5.800),
                (6.000, 7.800),
            ]
            base_echo_gain = 0.50
            reverb_decay = 3.60
            reverb_mix = 0.45

        for idx, (d_min, d_max) in enumerate(delay_zones):
            delay_sec = random.uniform(d_min, d_max)
            delay_samples = int(delay_sec * self.sample_rate)
            if delay_samples >= n:
                continue

            # Distance + reflection absorption loss; alternate phase for multipath interference
            atten = (
                base_echo_gain
                * ((1.0 + delay_sec / 0.32) ** -0.78)
                * random.uniform(0.75, 1.18)
            )
            polarity = -1.0 if (idx % 2 == 1) else 1.0

            # Progressive wall/air absorption LPF: later reflections are darker and deeper
            base_echo_hz = 580.0 if tier == "close" else (320.0 if tier == "mid" else 185.0)
            echo_cutoff_hz = max(58.0, base_echo_hz / (1.0 + 1.15 * delay_sec))
            sos_echo = signal.butter(
                2, echo_cutoff_hz, btype="low", fs=self.sample_rate, output="sos"
            )
            filtered_echo = signal.sosfilt(sos_echo, direct)

            # Finite building facade width smearing (10 - 22 ms Gaussian reflection kernel)
            smear_sec = random.uniform(0.010, 0.022)
            smear_len = max(3, int(smear_sec * self.sample_rate))
            k_t = np.linspace(-2.0, 2.0, smear_len)
            kernel = np.exp(-0.5 * (k_t**2))
            kernel /= np.sum(kernel)
            smeared_echo = signal.fftconvolve(filtered_echo, kernel, mode="same")

            out[delay_samples:] += (
                polarity * atten * smeared_echo[: n - delay_samples]
            )

        # 2. Diffuse urban canyon / terrain multi-scattering reverberation tail
        ir_dur = min(float(n) / self.sample_rate, reverb_decay * 2.6)
        ir_len = max(16, int(ir_dur * self.sample_rate))
        t_ir = np.linspace(0.0, ir_dur, ir_len)

        # Velvet-noise sparse random scatterers (avoids metallic comb resonances)
        ir = np.zeros(ir_len, dtype=np.float64)
        grid_step = max(4, int(0.0035 * self.sample_rate))
        for g_start in range(int(0.045 * self.sample_rate), ir_len - grid_step, grid_step):
            pulse_idx = g_start + random.randint(0, grid_step - 1)
            ir[pulse_idx] = 1.0 if random.random() > 0.5 else -1.0

        # Exponential buildup (50 ms) and reverberant canyon decay envelope
        ir_env = (1.0 - np.exp(-t_ir / 0.050)) * np.exp(-t_ir / reverb_decay)
        ir *= ir_env

        # Low-pass filter diffuse tail below 110 Hz so building reverberation is warm & booming
        sos_rev = signal.butter(
            2, 110.0, btype="low", fs=self.sample_rate, output="sos"
        )
        ir_filtered = signal.sosfilt(sos_rev, ir)
        ir_rms = float(np.sqrt(np.mean(ir_filtered**2)))
        if ir_rms > 1e-9:
            ir_filtered /= ir_rms * 18.0

        diffuse_tail = signal.fftconvolve(direct, ir_filtered, mode="full")[:n]
        out += reverb_mix * diffuse_tail

        return out.astype(np.float32)

    def synthesize_rain_loop(
        self, duration_sec: float = SYNTH_RAIN_LOOP_DURATION_SEC
    ) -> np.ndarray:
        """Generates a seamlessly looping stereo rain bed using crossfaded filtered noise.

        Generates 2-channel Gaussian white noise, filters with a Butterworth bandpass
        (400 Hz - 6500 Hz), and applies a linear crossfade window between the head and
        tail to produce a seamless loop without audible splices.

        Args:
            duration_sec: Total duration in seconds of the generated rain bed.

        Returns:
            2D float32 numpy array (N, 2) containing seamless stereo ambient rain.
        """
        n = int(self.sample_rate * duration_sec)
        white = np.random.normal(0.0, SYNTH_RAIN_NOISE_AMPLITUDE, (n, 2)).astype(np.float32)
        sos = signal.butter(
            BUTTERWORTH_FILTER_ORDER,
            list(SYNTH_RAIN_BANDPASS_HZ),
            btype="bandpass",
            fs=self.sample_rate,
            output="sos",
        )
        rain = signal.sosfilt(sos, white, axis=0).astype(np.float32)
        peak = np.max(np.abs(rain))
        if peak > 0:
            rain = rain / peak
        fade_len = int(self.sample_rate * SYNTH_RAIN_CROSSFADE_SEC)
        fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)[:, np.newaxis]
        fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)[:, np.newaxis]
        rain[:fade_len] = rain[:fade_len] * fade_in + rain[-fade_len:] * fade_out
        return rain[:-fade_len]

    def build_soundbank(
        self, variations_per_tier: int = PROCEDURAL_VARIATIONS_PER_TIER
    ) -> Tuple[Dict[str, List[np.ndarray]], np.ndarray]:
        """Generates a complete in-memory soundbank for immediate engine consumption.

        Args:
            variations_per_tier: Number of unique thunder variations per distance tier.

        Returns:
            Tuple of (thunder_bank_dict, rain_loop_stereo_array).
        """
        bank: Dict[str, List[np.ndarray]] = {"close": [], "mid": [], "far": []}
        for tier in ("close", "mid", "far"):
            for _ in range(variations_per_tier):
                bank[tier].append(self.synthesize_thunder(tier))
        rain = self.synthesize_rain_loop()
        return bank, rain

    def export_soundbank(
        self,
        output_dir: Path,
        variations_per_tier: int = PROCEDURAL_VARIATIONS_PER_TIER,
    ) -> None:
        """Pre-renders and exports all WAV assets to disk ahead-of-time.

        Args:
            output_dir: Target root directory for audio tiers and rain WAV.
            variations_per_tier: Number of unique WAV files to generate per tier.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"[*] Pre-rendering procedural soundbank into: {output_dir.resolve()}")

        for tier in ("close", "mid", "far"):
            tier_dir = output_dir / tier
            tier_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(variations_per_tier):
                filename = f"synth_{tier}_{idx + 1:02d}.wav"
                audio_data = self.synthesize_thunder(tier)
                sf.write(tier_dir / filename, audio_data, self.sample_rate)
                print(f"  + Generated {tier}/{filename}")

        rain_path = output_dir / "rain_loop.wav"
        rain_data = self.synthesize_rain_loop()
        sf.write(rain_path, rain_data, self.sample_rate)
        print(f"  + Generated {rain_path.name}")
        print("[+] Audio asset generation complete.")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments for the storm-synth generator CLI.

    Args:
        args: Optional list of argument strings (defaults to sys.argv[1:]).

    Returns:
        argparse.Namespace containing parsed CLI options.
    """
    parser = argparse.ArgumentParser(
        prog="storm-synth",
        description="AOT Procedural Thunder and Rain Soundbank Generator",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("./assets"),
        help="Target directory for generated WAV files (default: ./assets)",
    )
    parser.add_argument(
        "-v",
        "--variations",
        type=int,
        default=PROCEDURAL_VARIATIONS_PER_TIER,
        help="Number of variations per thunder tier (default: 3)",
    )
    parser.add_argument(
        "-s",
        "--sample-rate",
        type=int,
        default=AUDIO_SAMPLE_RATE,
        help="Audio sample rate in Hz (default: 44100)",
    )
    parser.add_argument(
        "--small-speakers",
        action="store_true",
        help="Tune infrasonics/sub-bass higher (48-140 Hz with saturation) for compact speakers lacking subwoofers",
    )
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point for pre-rendering soundbank WAV files to disk."""
    parsed = parse_args(args)
    synth = ThunderSynthesizer(
        sample_rate=parsed.sample_rate, small_speakers=parsed.small_speakers
    )
    synth.export_soundbank(
        output_dir=parsed.output_dir, variations_per_tier=parsed.variations
    )


if __name__ == "__main__":
    main()
