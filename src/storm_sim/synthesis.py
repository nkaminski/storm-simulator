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
    """Dedicated procedural acoustic synthesizer for lightning thunder and rain."""

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE):
        self.sample_rate = sample_rate

    def synthesize_thunder(self, tier: str) -> np.ndarray:
        """Synthesizes a realistic multi-burst thunderclap for a given distance tier ('close', 'mid', 'far')."""
        dur = SYNTH_THUNDER_DURATIONS_SEC[tier]
        n = int(self.sample_rate * dur)
        t = np.linspace(0.0, dur, n, dtype=np.float32)

        noise = np.random.normal(0.0, 1.0, n).astype(np.float32)
        decay = SYNTH_CLOSE_DECAY_TIME if tier == "close" else SYNTH_FAR_DECAY_TIME
        env = np.exp(-t / decay)

        min_bursts, max_bursts = SYNTH_THUNDER_BURSTS_RANGE
        for _ in range(random.randint(min_bursts, max_bursts)):
            burst_t = random.uniform(0.1, dur * SYNTH_BURST_TIME_SPAN_FACTOR)
            burst_w = random.uniform(*SYNTH_BURST_WIDTH_RANGE_SEC)
            burst_amp = random.uniform(*SYNTH_BURST_AMP_RANGE)
            env += burst_amp * np.exp(-((t - burst_t) ** 2) / (2.0 * (burst_w**2)))

        if tier == "close":
            env += SYNTH_CLOSE_INITIAL_SNAP_AMP * np.exp(-t / SYNTH_CLOSE_INITIAL_SNAP_DECAY)

        raw = noise * env
        sos = signal.butter(
            BUTTERWORTH_FILTER_ORDER,
            SYNTH_THUNDER_LPF_HZ[tier],
            btype="low",
            fs=self.sample_rate,
            output="sos",
        )
        filtered = signal.sosfilt(sos, raw).astype(np.float32)
        peak = np.max(np.abs(filtered))
        return (filtered / max(peak, 1e-6)) * SAMPLE_PEAK_NORMALIZE_TARGET

    def synthesize_rain_loop(
        self, duration_sec: float = SYNTH_RAIN_LOOP_DURATION_SEC
    ) -> np.ndarray:
        """Generates a seamlessly looping stereo rain bed using crossfaded filtered noise."""
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
        fade_len = int(self.sample_rate * SYNTH_RAIN_CROSSFADE_SEC)
        fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)[:, np.newaxis]
        fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)[:, np.newaxis]
        rain[:fade_len] = rain[:fade_len] * fade_in + rain[-fade_len:] * fade_out
        return rain[:-fade_len]

    def build_soundbank(
        self, variations_per_tier: int = PROCEDURAL_VARIATIONS_PER_TIER
    ) -> Tuple[Dict[str, List[np.ndarray]], np.ndarray]:
        """Generates a complete in-memory soundbank for immediate engine consumption."""
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
        """Pre-renders and exports all WAV assets to disk ahead-of-time."""
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
    parsed = parse_args(args)
    synth = ThunderSynthesizer(sample_rate=parsed.sample_rate)
    synth.export_soundbank(
        output_dir=parsed.output_dir, variations_per_tier=parsed.variations
    )


if __name__ == "__main__":
    main()
