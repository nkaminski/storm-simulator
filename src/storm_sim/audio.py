"""audio.py - High-performance polyphonic audio mixer with Butterworth LPF, spatial stereo panning, and AOT asset loading."""

from __future__ import annotations
import functools
import logging
import math
from pathlib import Path
import random
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import signal
import sounddevice as sd
import soundfile as sf

from .constants import (
    AUDIO_BLOCK_SIZE,
    AUDIO_OUTPUT_CLIP_LIMIT,
    AUDIO_SAMPLE_RATE,
    BUTTERWORTH_FILTER_ORDER,
    PROCEDURAL_VARIATIONS_PER_TIER,
    SAMPLE_PEAK_NORMALIZE_TARGET,
    SYNTH_RAIN_LOOP_DURATION_SEC,
    TIER_CLOSE_MAX_MILES,
    TIER_MID_MAX_MILES,
)
from .models import StormState, StrikeEvent
from .synthesis import ThunderSynthesizer

logger = logging.getLogger("storm_sim.audio")


@functools.lru_cache(maxsize=128)
def _get_cached_butterworth_sos(cutoff_hz_quantized: int, sample_rate: int) -> np.ndarray:
    """Caches Butterworth SOS filter coefficients ahead-of-time to avoid real-time filter design."""
    return signal.butter(
        BUTTERWORTH_FILTER_ORDER,
        cutoff_hz_quantized,
        btype="low",
        fs=sample_rate,
        output="sos",
    )


class AudioEngine:
    """Real-time polyphonic audio mixer with Butterworth LPF, stereo panning,
    and automatic procedural synthesis fallback if WAV files are absent.
    """

    def __init__(self, state: StormState, assets_dir: Optional[Path] = None):
        self.state = state
        self.assets_dir = assets_dir
        self.lock = threading.Lock()
        self.active_voices: List[Tuple[np.ndarray, int]] = []

        self.thunder_bank: Dict[str, List[np.ndarray]] = {
            "close": [],
            "mid": [],
            "far": [],
        }
        self.rain_loop: np.ndarray = np.zeros((1, 2), dtype=np.float32)
        self.rain_cursor: int = 0

        self._load_or_synthesize_assets()
        try:
            self.stream: Optional[sd.OutputStream] = sd.OutputStream(
                samplerate=AUDIO_SAMPLE_RATE,
                blocksize=AUDIO_BLOCK_SIZE,
                channels=2,
                dtype="float32",
                callback=self._audio_callback,
            )
        except Exception as e:
            logger.warning(
                "Could not initialize audio output stream: %s. Audio playback disabled.", e
            )
            self.stream = None

    def _load_or_synthesize_assets(self) -> None:
        """Loads WAV files from disk or synthesizes acoustic models on startup."""
        if self.assets_dir and self.assets_dir.exists():
            for tier in ("close", "mid", "far"):
                tier_dir = self.assets_dir / tier
                if tier_dir.exists():
                    for wav_path in sorted(tier_dir.glob("*.wav")):
                        data, sr = sf.read(wav_path, dtype="float32", always_2d=True)
                        mono = np.mean(data, axis=1)
                        if sr != AUDIO_SAMPLE_RATE:
                            num_samples = int(len(mono) * AUDIO_SAMPLE_RATE / sr)
                            mono = signal.resample(mono, num_samples)
                        peak = np.max(np.abs(mono))
                        if peak > 0:
                            mono = (mono / peak) * SAMPLE_PEAK_NORMALIZE_TARGET
                        self.thunder_bank[tier].append(mono.astype(np.float32))

            rain_files = list(self.assets_dir.glob("*rain*.wav"))
            if rain_files:
                data, _ = sf.read(rain_files[0], dtype="float32", always_2d=True)
                if data.shape[1] == 1:
                    data = np.repeat(data, 2, axis=1)
                self.rain_loop = data[:, :2].astype(np.float32)

        # Procedural fallback synthesis via dedicated ThunderSynthesizer
        synth = ThunderSynthesizer(sample_rate=AUDIO_SAMPLE_RATE)
        for tier in ("close", "mid", "far"):
            if not self.thunder_bank[tier]:
                logger.info(
                    "No WAVs found for '%s' tier; generating procedural models.",
                    tier,
                )
                for _ in range(PROCEDURAL_VARIATIONS_PER_TIER):
                    self.thunder_bank[tier].append(synth.synthesize_thunder(tier))

        if len(self.rain_loop) <= 1:
            logger.info("No rain WAV found; generating procedural stereo rain bed.")
            self.rain_loop = synth.synthesize_rain_loop(SYNTH_RAIN_LOOP_DURATION_SEC)

    def start(self) -> None:
        if self.stream is not None:
            self.stream.start()
            logger.info("Audio Engine started at %d Hz.", AUDIO_SAMPLE_RATE)
        else:
            logger.info("Audio Engine started (stream inactive).")

    def stop(self) -> None:
        self.clear_voices()
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()

    def clear_voices(self) -> None:
        """Immediately silences all playing thunder voices."""
        with self.lock:
            self.active_voices.clear()

    def schedule_thunder(self, strike: StrikeEvent) -> None:
        """Processes DSP (LPF + Gain + Constant-Power Pan) and queues playback."""
        if self.state.is_zero_intensity:
            return

        if strike.distance_miles < TIER_CLOSE_MAX_MILES:
            tier = "close"
        elif strike.distance_miles < TIER_MID_MAX_MILES:
            tier = "mid"
        else:
            tier = "far"

        base_mono = random.choice(self.thunder_bank[tier])

        # Reuse pre-calculated SOS filter coefficients to keep scheduling fast
        quantized_cutoff = int(round(strike.audio_lpf_hz / 10.0) * 10)
        sos = _get_cached_butterworth_sos(quantized_cutoff, AUDIO_SAMPLE_RATE)

        scaled = (
            signal.sosfilt(sos, base_mono).astype(np.float32)
            * strike.audio_gain_linear
        )

        theta = strike.stereo_pan * (math.pi / 2.0)
        stereo_buf = np.column_stack(
            (scaled * math.cos(theta), scaled * math.sin(theta))
        ).astype(np.float32)

        with self.lock:
            self.active_voices.append((stereo_buf, 0))

    def _audio_callback(
        self, outdata: np.ndarray, frames: int, time_info, status
    ) -> None:
        outdata.fill(0.0)

        if self.state.is_zero_intensity:
            with self.lock:
                if self.active_voices:
                    self.active_voices.clear()
            return

        # 1. Continuous Background Rain Bed (zero allocation slice addition)
        rain_lvl = self.state.effective_rain_level * self.state.master_volume
        if rain_lvl > 0.001:
            loop_len = len(self.rain_loop)
            idx = self.rain_cursor
            if idx + frames <= loop_len:
                outdata[:] += self.rain_loop[idx : idx + frames] * rain_lvl
                self.rain_cursor = (idx + frames) % loop_len
            else:
                part1 = loop_len - idx
                part2 = frames - part1
                outdata[:part1] += self.rain_loop[idx:] * rain_lvl
                outdata[part1:] += self.rain_loop[:part2] * rain_lvl
                self.rain_cursor = part2

        # 2. Active Polyphonic Thunder Voices
        with self.lock:
            remaining_voices: List[Tuple[np.ndarray, int]] = []
            for buf, cursor in self.active_voices:
                chunk = min(frames, len(buf) - cursor)
                outdata[:chunk] += (
                    buf[cursor : cursor + chunk] * self.state.master_volume
                )
                if cursor + chunk < len(buf):
                    remaining_voices.append((buf, cursor + chunk))
            self.active_voices = remaining_voices

        np.clip(
            outdata, -AUDIO_OUTPUT_CLIP_LIMIT, AUDIO_OUTPUT_CLIP_LIMIT, out=outdata
        )
