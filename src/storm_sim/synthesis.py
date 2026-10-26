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
    PROCEDURAL_VARIATIONS_PER_TIER,
    SAMPLE_PEAK_NORMALIZE_TARGET,
    SYNTH_BURST_AMP_RANGE,
    SYNTH_BURST_TIME_SPAN_FACTOR,
    SYNTH_BURST_WIDTH_RANGE_SEC,
    SYNTH_CLOSE_DECAY_TIME,
    SYNTH_CLOSE_INITIAL_SNAP_AMP,
    SYNTH_CLOSE_INITIAL_SNAP_DECAY,
    SYNTH_FAR_DECAY_TIME,
    SYNTH_RAIN_BANDPASS_HZ,
    SYNTH_RAIN_CROSSFADE_SEC,
    SYNTH_RAIN_LOOP_DURATION_SEC,
    SYNTH_RAIN_NOISE_AMPLITUDE,
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

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE):
        """Initializes the procedural synthesizer.

        Args:
            sample_rate: Target audio sample rate in Hz.
        """
        self.sample_rate = sample_rate

    def synthesize_thunder(self, tier: str) -> np.ndarray:
        """Synthesizes an authentic, floor-shaking multi-layer thunderclap for a given distance tier.

        Grounded in empirical thunder acoustics (Few 1969; Holmes et al. 1971; Ribner & Roy 1982):
        1. Infrasonic & Sub-Bass Cylindrical Shockwave Body (25 Hz - 85 Hz):
           Plasma channel expansion wave producing dominant acoustic power density (>90% of power
           below 100 Hz) in the wall-shaking sub-bass region.
        2. Low-Frequency Tortuous Channel Resonance & Echoes (55 Hz - 190 Hz):
           Multi-burst packet arrivals modeling tortuous channel kinks across kilometers with natural
           1/f^2 spectral roll-off.
        3. Tortuous N-Wave Shock Cluster Clap (Close and Mid tiers, 45 Hz - 260 Hz):
           Models the initial close thunderclap via Ribner & Roy (1982) superposition of
           band-limited bipolar N-wave pressure bursts from crooked channel segments, with
           nonlinear shock steepening (tanh) and steep low-pass filtering (<320 Hz) to eliminate
           synthetic high-pitched hiss.

        Args:
            tier: Distance tier string: 'close', 'mid', or 'far'.

        Returns:
            1D float32 numpy array containing the synthesized mono thunderclap.
        """
        dur = SYNTH_THUNDER_DURATIONS_SEC.get(tier, 8.0)
        n = int(self.sample_rate * dur)
        t = np.linspace(0.0, dur, n, dtype=np.float32)

        # ----------------------------------------------------------------------
        # Layer 1: Infrasonic & Sub-Bass Shockwave Body (25 - 85 Hz)
        # Dominates total acoustic energy (>90% of power in 20-100 Hz band).
        # ----------------------------------------------------------------------
        white_sub = np.random.normal(0.0, 1.0, n).astype(np.float32)
        sos_sub = signal.butter(
            4, [25.0, 85.0], btype="bandpass", fs=self.sample_rate, output="sos"
        )
        sub_noise = signal.sosfilt(sos_sub, white_sub)

        # Deep sub-bass plasma expansion wave (kept strictly below 65 Hz)
        attack_ramp = 1.0 - np.exp(-t / 0.008)
        if tier == "close":
            exp_env = attack_ramp * np.exp(-t / 0.65)
            exp_freq = 36.0 + 24.0 * np.exp(-t / 0.12)
            boom = (
                np.sin(2.0 * np.pi * np.cumsum(exp_freq) / self.sample_rate)
                * exp_env
                * 2.2
            )
            sub_decay = 2.4
        elif tier == "mid":
            exp_env = attack_ramp * np.exp(-t / 1.1)
            exp_freq = 33.0 + 18.0 * np.exp(-t / 0.18)
            boom = (
                np.sin(2.0 * np.pi * np.cumsum(exp_freq) / self.sample_rate)
                * exp_env
                * 1.6
            )
            sub_decay = 3.8
        else:  # far
            exp_env = attack_ramp * np.exp(-t / 1.8)
            exp_freq = 28.0 + 14.0 * np.exp(-t / 0.25)
            boom = (
                np.sin(2.0 * np.pi * np.cumsum(exp_freq) / self.sample_rate)
                * exp_env
                * 1.1
            )
            sub_decay = 5.5

        # Tortuous channel secondary bursts (interference from segments at different heights)
        sub_env = attack_ramp * np.exp(-t / sub_decay)
        min_bursts, max_bursts = SYNTH_THUNDER_BURSTS_RANGE
        n_bursts = (
            random.randint(min_bursts, max_bursts)
            if tier != "far"
            else random.randint(6, 12)
        )
        for _ in range(n_bursts):
            bt = random.uniform(0.15, dur * SYNTH_BURST_TIME_SPAN_FACTOR)
            bw = random.uniform(*SYNTH_BURST_WIDTH_RANGE_SEC)
            bamp = random.uniform(*SYNTH_BURST_AMP_RANGE)
            sub_env += bamp * np.exp(-((t - bt) ** 2) / (2.0 * (bw**2)))

        sub_layer = (sub_noise * 3.4 * sub_env) + boom

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
        mid_layer = mid_noise * 1.4 * mid_env

        # ----------------------------------------------------------------------
        # Layer 3: Ribner & Roy (1982) Tortuous N-Wave Shock Cluster Clap (45 - 260 Hz)
        # Models close thunderclaps as a ragged cluster of low-frequency N-wave
        # pressure bursts from nearby channel kinks, with zero high-pitched hiss.
        # ----------------------------------------------------------------------
        if tier in ("close", "mid"):
            white_clap = np.random.normal(0.0, 1.0, n).astype(np.float32)
            clap_band = [45.0, 250.0] if tier == "close" else [40.0, 165.0]
            sos_clap_bp = signal.butter(
                3, clap_band, btype="bandpass", fs=self.sample_rate, output="sos"
            )
            # Apply 1/f spectral tilt via additional 1st-order low-pass at 95 Hz
            sos_tilt = signal.butter(
                1, 95.0, btype="low", fs=self.sample_rate, output="sos"
            )
            clap_carrier = signal.sosfilt(
                sos_tilt, signal.sosfilt(sos_clap_bp, white_clap)
            )
            clap_carrier = clap_carrier / max(float(np.std(clap_carrier)), 1e-6)

            clap_env = np.zeros(n, dtype=np.float32)
            n_kinks = random.randint(5, 8) if tier == "close" else random.randint(3, 5)
            t_kink = 0.006
            for k_idx in range(n_kinks):
                width = random.uniform(0.008, 0.024) if tier == "close" else random.uniform(0.015, 0.040)
                amp = (1.0 if k_idx < 2 else random.uniform(0.45, 0.90)) * np.exp(-t_kink / 0.16)
                # Asymmetric pulse envelope: rapid rise (4-8 ms), slower pressure tail
                dt_k = t - t_kink
                mask = dt_k >= 0.0
                dt_pos = dt_k[mask]
                pulse = (1.0 - np.exp(-dt_pos / 0.004)) * np.exp(-dt_pos / width)
                clap_env[mask] += amp * pulse
                t_kink += random.uniform(0.012, 0.038)

            # Nonlinear shockwave compression (tanh) followed by steep LPF to strip synthetic harmonics
            raw_clap = np.tanh(clap_carrier * clap_env * (2.2 if tier == "close" else 1.4))
            sos_clap_lpf = signal.butter(
                4,
                270.0 if tier == "close" else 175.0,
                btype="low",
                fs=self.sample_rate,
                output="sos",
            )
            crack_layer = signal.sosfilt(sos_clap_lpf, raw_clap) * (
                2.4 if tier == "close" else 1.1
            )
        else:
            crack_layer = np.zeros(n, dtype=np.float32)

        # Composite multi-layer acoustic mix with master tier low-pass filter
        composite = (
            (sub_layer * 0.80) + (mid_layer * 0.35) + (crack_layer * 0.45)
        )
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
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    """CLI entry point for pre-rendering soundbank WAV files to disk."""
    parsed = parse_args(args)
    synth = ThunderSynthesizer(sample_rate=parsed.sample_rate)
    synth.export_soundbank(
        output_dir=parsed.output_dir, variations_per_tier=parsed.variations
    )


if __name__ == "__main__":
    main()
