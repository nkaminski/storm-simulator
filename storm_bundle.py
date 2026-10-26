#!/usr/bin/env python3
"""storm_bundle.py - All-in-One Autonomous Thunderstorm Simulator & Agent Scaffolder

Physics-accurate E1.31 lighting and spatial audio simulator with channel mapping,
integrated desktop test UI, embedded documentation, and automated procedural synthesis fallback.

Usage:
    # Run headless CLI simulator (default 4 pixels unicast to 127.0.0.1):
    python storm_bundle.py --intensity 0.65

    # Run with custom unicast IP and channel map:
    python storm_bundle.py --pixels 4 --e131-host 192.168.1.50 --channel-map "0:1,1:2,2:3,3:4"

    # Launch desktop hardware visualizer & control UI:
    python storm_bundle.py --ui

    # Unpack into a modular, production PEP-621 Python package:
    python storm_bundle.py --unpack ./storm-sim
"""

from __future__ import annotations
import argparse
import asyncio
from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import random
import sys
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
import sacn
from scipy import signal
import sounddevice as sd
import soundfile as sf

# ==============================================================================
# CONSTANTS: Simulation, Physics, Optical, Acoustic, and UI
# ==============================================================================

# --- Core Simulation & CLI Defaults ---
DEFAULT_PIXELS: int = 4
DEFAULT_START_UNIVERSE: int = 1
DEFAULT_FPS: int = 44
DEFAULT_INTENSITY: float = 0.5
DEFAULT_MIN_DIST_MILES: float = 0.1
DEFAULT_MAX_DIST_MILES: float = 8.0
DEFAULT_MAX_RATE_PER_MIN: float = 35.0
DEFAULT_MASTER_BRIGHTNESS: float = 1.0
DEFAULT_MASTER_VOLUME: float = 1.0
DEFAULT_ASSETS_DIR: str = "./assets"
DEFAULT_E131_HOST: str = "127.0.0.1"
DEFAULT_MULTICAST: bool = False
DEFAULT_OSC_HOST: str = "0.0.0.0"
DEFAULT_OSC_PORT: int = 5005

# --- Meteorology & Intensity Scaling Constants ---
ZERO_INTENSITY_EPSILON: float = 1e-5
INTENSITY_RATE_EXPONENT: float = 2.2
INTENSITY_RAIN_EXPONENT: float = 1.5
BETA_DIST_SKEW_WEIGHT: float = 3.0
MAX_EXTRA_STROKES_AT_PEAK: int = 5
ABSOLUTE_MIN_DIST_MILES: float = 0.05
ABSOLUTE_MAX_DIST_MILES: float = 20.0
MIN_DIST_SPAN_MILES: float = 0.05
SCHEDULER_POLL_SLICE_SEC: float = 0.25

# --- Optical & Lighting Physics Constants (1-Channel Monochrome White) ---
MAX_PIXELS_PER_UNIVERSE: int = 512
MAX_CONFIGURABLE_PIXELS: int = 5120
DMX_MAX_VAL: int = 255
BASE_OPTICAL_EXTINCTION: float = 0.15
RAIN_OPTICAL_EXTINCTION_SCALE: float = 0.35
OPTICAL_SOFTENING_DIST_MILES: float = 0.12
OPTICAL_NORM_OFFSET: float = 0.25
MIN_PEAK_BRIGHTNESS: float = 0.02
BASE_SPATIAL_SIGMA: float = 0.035
SPATIAL_SIGMA_PER_MILE: float = 0.065
PRIMARY_STROKE_DURATION_RANGE_SEC: Tuple[float, float] = (0.06, 0.14)
SECONDARY_STROKE_DURATION_RANGE_SEC: Tuple[float, float] = (0.04, 0.10)
SECONDARY_STROKE_AMP_RANGE: Tuple[float, float] = (0.35, 0.85)
INTER_STROKE_GAP_RANGE_SEC: Tuple[float, float] = (0.025, 0.075)
STROKE_DECAY_TIME_CONSTANT: float = 4.5
STRIKE_ENVELOPE_TAIL_PAD_SEC: float = 0.05

# --- Acoustic & Audio DSP Constants ---
SPEED_OF_SOUND_MILES_PER_SEC: float = 0.21312  # ~343 m/s at 20°C
AUDIO_SAMPLE_RATE: int = 44100
AUDIO_BLOCK_SIZE: int = 1024
ACOUSTIC_REF_DIST_MILES: float = 0.15
ACOUSTIC_AIR_ABSORPTION_DB_PER_MILE: float = 2.8
INTENSITY_ACOUSTIC_BOOST_DB: float = 3.0
MIN_LPF_CUTOFF_HZ: float = 130.0
MAX_LPF_CUTOFF_HZ: float = 16000.0
LPF_REFERENCE_NUMERATOR_HZ: float = 12000.0
LPF_DISTANCE_ROLLOFF_FACTOR: float = 1.85
BUTTERWORTH_FILTER_ORDER: int = 2
TIER_CLOSE_MAX_MILES: float = 1.2
TIER_MID_MAX_MILES: float = 3.2
SAMPLE_PEAK_NORMALIZE_TARGET: float = 0.90
AUDIO_OUTPUT_CLIP_LIMIT: float = 0.98

# --- Procedural Fallback Synthesis Constants ---
PROCEDURAL_VARIATIONS_PER_TIER: int = 3
SYNTH_THUNDER_DURATIONS_SEC: Dict[str, float] = {
    "close": 6.0,
    "mid": 11.0,
    "far": 16.0,
}
SYNTH_THUNDER_LPF_HZ: Dict[str, float] = {
    "close": 4500.0,
    "mid": 1200.0,
    "far": 280.0,
}
SYNTH_RAIN_LOOP_DURATION_SEC: float = 12.0
SYNTH_RAIN_CROSSFADE_SEC: float = 1.5
SYNTH_RAIN_BANDPASS_HZ: Tuple[float, float] = (400.0, 6500.0)

# --- UI & Test Bench Constants ---
UI_WINDOW_WIDTH: int = 1040
UI_WINDOW_HEIGHT: int = 680
UI_BG_DARK: str = "#111318"
UI_PANEL_BG: str = "#1B1F27"
UI_CANVAS_BG: str = "#07080A"
UI_ACCENT_BLUE: str = "#38BDF8"
UI_TEXT_MAIN: str = "#E2E8F0"
UI_TEXT_MUTED: str = "#94A3B8"
LED_CANVAS_HEIGHT: int = 150
MAX_DISPLAY_SEGMENTS: int = 256
CLICK_STRIKE_DEFAULT_DIST_MILES: float = 0.75

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("storm_sim")


# ==============================================================================
# DATA MODELS
# ==============================================================================
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
    strokes: List[StrokePulse]
    audio_delay_sec: float
    audio_gain_linear: float
    audio_lpf_hz: float
    stereo_pan: float  # Normalized [0.0 = Left, 1.0 = Right]


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


# ==============================================================================
# PHYSICS ENGINE
# ==============================================================================
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


# ==============================================================================
# LIGHTING ENGINE (E1.31 sACN MONOCHROME WHITE)
# ==============================================================================
class E131LightingEngine:
    """Renders 1D monochrome white lightning envelopes to E1.31 DMX universes."""

    def __init__(self, state: StormState):
        self.state = state
        self.active_strikes: List[StrikeEvent] = []
        self.sender = sacn.sACNsender(fps=state.fps)
        self.universes: List[int] = []
        self.pixel_coords = np.linspace(0.0, 1.0, state.pixels, dtype=np.float32)
        self.last_frame_dmx: np.ndarray = np.zeros(state.pixels, dtype=np.uint8)

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

    def trigger_flash(self, strike: StrikeEvent) -> None:
        if not self.state.is_zero_intensity:
            self.active_strikes.append(strike)

    def clear_all(self) -> None:
        """Immediately extinguishes all active lightning flashes and zeros DMX output."""
        self.active_strikes.clear()
        self.last_frame_dmx = np.zeros(self.state.pixels, dtype=np.uint8)
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
        frame_white = np.zeros(num_pixels, dtype=np.float32)
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

            spatial_curve = np.exp(
                -((self.pixel_coords - strike.epicenter) ** 2)
                / (2.0 * (strike.spatial_sigma**2))
            )
            frame_white += (
                spatial_curve
                * temporal_amp
                * strike.peak_brightness
                * self.state.master_brightness
                * DMX_MAX_VAL
            )

        self.active_strikes = remaining_strikes

        dmx_bytes = np.clip(frame_white, 0, DMX_MAX_VAL).astype(np.uint8)
        self.last_frame_dmx = dmx_bytes

        for idx, univ in enumerate(self.universes):
            start_px = idx * MAX_PIXELS_PER_UNIVERSE
            end_px = min(num_pixels, (idx + 1) * MAX_PIXELS_PER_UNIVERSE)
            self.sender[univ].dmx_data = tuple(dmx_bytes[start_px:end_px].tolist())

    def stop(self) -> None:
        self.clear_all()
        time.sleep(0.05)
        self.sender.stop()


# ==============================================================================
# AUDIO ENGINE & PROCEDURAL SYNTHESIS
# ==============================================================================
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
        """Loads WAV files from disk or synthesizes realistic acoustic models."""
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

        for tier in ("close", "mid", "far"):
            if not self.thunder_bank[tier]:
                logger.info(
                    "No WAVs found for '%s' tier; generating procedural thunder models.",
                    tier,
                )
                for _ in range(PROCEDURAL_VARIATIONS_PER_TIER):
                    self.thunder_bank[tier].append(self._synthesize_thunder(tier))

        if len(self.rain_loop) <= 1:
            logger.info(
                "No rain WAV found; generating seamless procedural stereo rain bed."
            )
            self.rain_loop = self._synthesize_rain_loop(SYNTH_RAIN_LOOP_DURATION_SEC)

    def _synthesize_thunder(self, tier: str) -> np.ndarray:
        """Synthesizes multi-burst filtered noise with sub-bass resonance."""
        dur = SYNTH_THUNDER_DURATIONS_SEC[tier]
        n = int(AUDIO_SAMPLE_RATE * dur)
        t = np.linspace(0.0, dur, n, dtype=np.float32)

        noise = np.random.normal(0.0, 1.0, n).astype(np.float32)
        env = np.exp(-t / (0.8 if tier == "close" else 2.8))
        for _ in range(random.randint(3, 7)):
            burst_t = random.uniform(0.1, dur * 0.6)
            burst_w = random.uniform(0.15, 0.8)
            burst_amp = random.uniform(0.3, 0.9)
            env += burst_amp * np.exp(-((t - burst_t) ** 2) / (2 * burst_w**2))

        if tier == "close":
            env += 2.5 * np.exp(-t / 0.025)

        raw = noise * env
        sos = signal.butter(
            BUTTERWORTH_FILTER_ORDER,
            SYNTH_THUNDER_LPF_HZ[tier],
            btype="low",
            fs=AUDIO_SAMPLE_RATE,
            output="sos",
        )
        filtered = signal.sosfilt(sos, raw).astype(np.float32)
        peak = np.max(np.abs(filtered))
        return (filtered / max(peak, 1e-6)) * SAMPLE_PEAK_NORMALIZE_TARGET

    def _synthesize_rain_loop(self, duration_sec: float) -> np.ndarray:
        """Generates a crossfaded stereo filtered noise rain bed."""
        n = int(AUDIO_SAMPLE_RATE * duration_sec)
        white = np.random.normal(0.0, 0.15, (n, 2)).astype(np.float32)
        sos = signal.butter(
            BUTTERWORTH_FILTER_ORDER,
            list(SYNTH_RAIN_BANDPASS_HZ),
            btype="bandpass",
            fs=AUDIO_SAMPLE_RATE,
            output="sos",
        )
        rain = signal.sosfilt(sos, white, axis=0).astype(np.float32)
        fade_len = int(AUDIO_SAMPLE_RATE * SYNTH_RAIN_CROSSFADE_SEC)
        fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)[:, np.newaxis]
        fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)[:, np.newaxis]
        rain[:fade_len] = rain[:fade_len] * fade_in + rain[-fade_len:] * fade_out
        return rain[:-fade_len]

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

        sos = signal.butter(
            BUTTERWORTH_FILTER_ORDER,
            strike.audio_lpf_hz,
            btype="low",
            fs=AUDIO_SAMPLE_RATE,
            output="sos",
        )
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

        # 1. Continuous Background Rain Bed
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


# ==============================================================================
# OPEN SOUND CONTROL (OSC) INTERFACE
# ==============================================================================
class OSCController:
    """Exposes runtime parameters and manual strike triggers over UDP OSC."""

    def __init__(
        self,
        state: StormState,
        trigger_callback,
        halt_callback,
        host: str = DEFAULT_OSC_HOST,
        port: int = DEFAULT_OSC_PORT,
    ):
        self.state = state
        self.trigger_callback = trigger_callback
        self.halt_callback = halt_callback
        self.host = host
        self.port = port
        self.dispatcher = Dispatcher()
        self._bind_routes()

    def _bind_routes(self) -> None:
        self.dispatcher.map("/storm/intensity", self._on_intensity)
        self.dispatcher.map("/storm/intensity/ramp", self._on_intensity_ramp)
        self.dispatcher.map("/storm/intensity/couple", self._on_couple)
        self.dispatcher.map("/storm/distance/min", self._on_min_dist)
        self.dispatcher.map("/storm/distance/max", self._on_max_dist)
        self.dispatcher.map("/storm/rate", self._on_rate)
        self.dispatcher.map("/storm/rain/level", self._on_rain)
        self.dispatcher.map("/storm/light/gain", self._on_brightness)
        self.dispatcher.map("/storm/audio/gain", self._on_volume)
        self.dispatcher.map("/storm/config/pixels", self._on_pixels)
        self.dispatcher.map("/storm/strike/trigger", self._on_manual_strike)

    def _on_intensity(self, addr: str, val: float) -> None:
        self.state.ramp_duration = 0.0
        self.state.intensity = max(0.0, min(1.0, float(val)))
        if self.state.is_zero_intensity:
            self.halt_callback()
            logger.info(
                "OSC: Intensity set to 0.0 -> Halted all rain, thunder, and lightning."
            )
        else:
            logger.info("OSC: Intensity set to %.2f", self.state.intensity)

    def _on_intensity_ramp(
        self, addr: str, target: float, duration_sec: float
    ) -> None:
        self.state.ramp_start_val = self.state.intensity
        self.state.ramp_target_val = max(0.0, min(1.0, float(target)))
        self.state.ramp_start_time = time.monotonic()
        self.state.ramp_duration = max(0.1, float(duration_sec))
        logger.info(
            "OSC: Ramping intensity from %.2f -> %.2f over %.1fs",
            self.state.ramp_start_val,
            self.state.ramp_target_val,
            self.state.ramp_duration,
        )

    def _on_couple(self, addr: str, *args) -> None:
        self.state.override_rate = None
        self.state.override_rain = None
        logger.info("OSC: Re-coupled rate and rain to master intensity.")

    def _on_min_dist(self, addr: str, val: float) -> None:
        self.state.min_dist_miles = max(
            ABSOLUTE_MIN_DIST_MILES,
            min(self.state.max_dist_miles - MIN_DIST_SPAN_MILES, float(val)),
        )

    def _on_max_dist(self, addr: str, val: float) -> None:
        self.state.max_dist_miles = max(
            self.state.min_dist_miles + MIN_DIST_SPAN_MILES,
            min(ABSOLUTE_MAX_DIST_MILES, float(val)),
        )

    def _on_rate(self, addr: str, val: float) -> None:
        self.state.override_rate = max(0.0, float(val))

    def _on_rain(self, addr: str, val: float) -> None:
        self.state.override_rain = max(0.0, min(1.0, float(val)))

    def _on_brightness(self, addr: str, val: float) -> None:
        self.state.master_brightness = max(0.0, min(1.0, float(val)))

    def _on_volume(self, addr: str, val: float) -> None:
        self.state.master_volume = max(0.0, min(1.0, float(val)))

    def _on_pixels(self, addr: str, val: int) -> None:
        self.state.pixels = max(1, min(MAX_CONFIGURABLE_PIXELS, int(val)))

    def _on_manual_strike(self, addr: str, *args) -> None:
        dist = float(args[0]) if len(args) >= 1 else None
        epi = float(args[1]) if len(args) >= 2 else None
        self.trigger_callback(dist, epi)

    async def start_server(self) -> AsyncIOOSCUDPServer:
        loop = asyncio.get_running_loop()
        server = AsyncIOOSCUDPServer((self.host, self.port), self.dispatcher, loop)
        transport, _ = await server.create_serve_endpoint()
        logger.info("OSC UDP Server listening on %s:%d", self.host, self.port)
        return transport


# ==============================================================================
# COORDINATOR ENGINE
# ==============================================================================
class StormCoordinator:
    """Main async orchestrator tying together scheduling, lighting, audio, and OSC."""

    def __init__(
        self,
        state: StormState,
        assets_dir: Optional[Path],
        osc_host: str,
        osc_port: int,
    ):
        self.state = state
        self.lighting = E131LightingEngine(state)
        self.audio = AudioEngine(state, assets_dir)
        self.osc = OSCController(
            state,
            self.trigger_strike_now,
            self.halt_all_activity,
            host=osc_host,
            port=osc_port,
        )
        self._background_tasks: Set[asyncio.Task] = set()

    def halt_all_activity(self) -> None:
        """Cancels pending delayed thunderclaps and clears active audio/lighting."""
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        self.lighting.clear_all()
        self.audio.clear_voices()

    def trigger_strike_now(
        self,
        forced_dist: Optional[float] = None,
        forced_epicenter: Optional[float] = None,
    ) -> None:
        if self.state.is_zero_intensity:
            return

        now = time.monotonic()
        strike = PhysicsEngine.generate_strike(
            self.state, now, forced_dist, forced_epicenter
        )
        logger.info(
            "STRIKE | Dist: %.2f mi | Epicenter: %.2f | Bri: %.2f | Strokes: %d | "
            "Thunder Delay: %.2fs | LPF: %.0f Hz",
            strike.distance_miles,
            strike.epicenter,
            strike.peak_brightness,
            len(strike.strokes),
            strike.audio_delay_sec,
            strike.audio_lpf_hz,
        )
        self.lighting.trigger_flash(strike)
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._delayed_thunder(strike))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            pass

    async def _delayed_thunder(self, strike: StrikeEvent) -> None:
        try:
            await asyncio.sleep(strike.audio_delay_sec)
            if self.state.running and not self.state.is_zero_intensity:
                self.audio.schedule_thunder(strike)
        except asyncio.CancelledError:
            pass

    async def _render_loop(self) -> None:
        frame_interval = 1.0 / self.state.fps
        was_zero = self.state.is_zero_intensity
        while self.state.running:
            t0 = time.monotonic()
            self.state.update_ramp(t0)

            is_zero = self.state.is_zero_intensity
            if is_zero and not was_zero:
                self.halt_all_activity()
            was_zero = is_zero

            self.lighting.render_frame(t0)
            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0.001, frame_interval - elapsed))

    async def _scheduler_loop(self) -> None:
        """Poisson process strike generator that adapts dynamically to intensity changes."""
        while self.state.running:
            rate = self.state.effective_rate_per_sec
            if rate <= ZERO_INTENSITY_EPSILON:
                await asyncio.sleep(SCHEDULER_POLL_SLICE_SEC)
                continue

            wait_time = random.expovariate(rate)
            slept = 0.0
            while slept < wait_time and self.state.running:
                step = min(SCHEDULER_POLL_SLICE_SEC, wait_time - slept)
                await asyncio.sleep(step)
                slept += step
                new_rate = self.state.effective_rate_per_sec
                if new_rate <= ZERO_INTENSITY_EPSILON or new_rate > rate * 2.0:
                    break

            if (
                self.state.running
                and self.state.effective_rate_per_sec > ZERO_INTENSITY_EPSILON
            ):
                self.trigger_strike_now()

    async def run(self) -> None:
        self.lighting.start()
        self.audio.start()
        osc_transport = await self.osc.start_server()
        try:
            await asyncio.gather(self._render_loop(), self._scheduler_loop())
        except asyncio.CancelledError:
            pass
        finally:
            self.state.running = False
            self.halt_all_activity()
            osc_transport.close()
            self.lighting.stop()
            self.audio.stop()
            logger.info("Storm Engine shut down cleanly.")


# ==============================================================================
# DESKTOP TEST BENCH UI (TKINTER)
# ==============================================================================
class StormDesktopUI:
    """Native desktop hardware visualizer and control panel."""

    def __init__(self, coordinator: StormCoordinator):
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError as e:
            raise RuntimeError(
                "Tkinter is required to run the desktop visualizer. "
                "Install python3-tk or run headless without --ui."
            ) from e

        self.tk = tk
        self.ttk = ttk
        self.coordinator = coordinator
        self.state = coordinator.state
        self.lighting = coordinator.lighting

        self.root = tk.Tk()
        self.root.title("Storm-Sim | E1.31 Monochrome & Spatial Audio Test Bench")
        self.root.geometry(f"{UI_WINDOW_WIDTH}x{UI_WINDOW_HEIGHT}")
        self.root.configure(bg=UI_BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._tracked_strikes: List[StrikeEvent] = []
        self._patch_strike_tracker()

        self._configure_styles()
        self._build_layout()

    def _patch_strike_tracker(self) -> None:
        orig_trigger = self.lighting.trigger_flash

        def hooked_trigger(strike: StrikeEvent) -> None:
            orig_trigger(strike)
            self._tracked_strikes.append(strike)

        self.lighting.trigger_flash = hooked_trigger

    def _configure_styles(self) -> None:
        style = self.ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass
        style.configure("TFrame", background=UI_BG_DARK)
        style.configure("Panel.TFrame", background=UI_PANEL_BG)
        style.configure(
            "TLabel",
            background=UI_PANEL_BG,
            foreground=UI_TEXT_MAIN,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Header.TLabel",
            background=UI_BG_DARK,
            foreground=UI_ACCENT_BLUE,
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=UI_PANEL_BG,
            foreground=UI_TEXT_MUTED,
            font=("Consolas", 9),
        )
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)

    def _build_layout(self) -> None:
        # 1. Top LED Array Visualizer Section
        top_frame = self.ttk.Frame(self.root, padding=(16, 12, 16, 6))
        top_frame.pack(fill=self.tk.X)

        header_row = self.ttk.Frame(top_frame)
        header_row.pack(fill=self.tk.X, pady=(0, 6))
        self.ttk.Label(
            header_row,
            text="E1.31 MONOCHROME WHITE PIXEL ARRAY (CLICK STRIP TO TRIGGER STRIKE AT EPICENTER)",
            style="Header.TLabel",
        ).pack(side=self.tk.LEFT)
        self.lbl_fps_status = self.ttk.Label(
            header_row,
            text=f"Pixels: {self.state.pixels} | Universes: {len(self.lighting.universes)}",
            style="Muted.TLabel",
        )
        self.lbl_fps_status.configure(background=UI_BG_DARK)
        self.lbl_fps_status.pack(side=self.tk.RIGHT)

        self.canvas = self.tk.Canvas(
            top_frame,
            height=LED_CANVAS_HEIGHT,
            bg=UI_CANVAS_BG,
            highlightthickness=1,
            highlightbackground="#334155",
            cursor="crosshair",
        )
        self.canvas.pack(fill=self.tk.X)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # 2. Main Controls & Telemetry Split
        mid_frame = self.ttk.Frame(self.root, padding=(16, 8, 16, 12))
        mid_frame.pack(fill=self.tk.BOTH, expand=True)

        # Left Column: Parameter Sliders
        ctrl_panel = self.ttk.Frame(mid_frame, style="Panel.TFrame", padding=14)
        ctrl_panel.pack(side=self.tk.LEFT, fill=self.tk.BOTH, expand=True, padx=(0, 8))

        self.var_intensity = self.tk.DoubleVar(value=self.state.intensity)
        self._add_slider(
            ctrl_panel,
            "Master Storm Intensity (0 = Killswitch)",
            self.var_intensity,
            0.0,
            1.0,
            self._on_intensity_change,
        )

        self.var_min_dist = self.tk.DoubleVar(value=self.state.min_dist_miles)
        self._add_slider(
            ctrl_panel,
            "Min Strike Distance (miles)",
            self.var_min_dist,
            ABSOLUTE_MIN_DIST_MILES,
            10.0,
            self._on_min_dist_change,
        )

        self.var_max_dist = self.tk.DoubleVar(value=self.state.max_dist_miles)
        self._add_slider(
            ctrl_panel,
            "Max Strike Distance (miles)",
            self.var_max_dist,
            0.5,
            ABSOLUTE_MAX_DIST_MILES,
            self._on_max_dist_change,
        )

        self.var_brightness = self.tk.DoubleVar(value=self.state.master_brightness)
        self._add_slider(
            ctrl_panel,
            "Master Lighting Ceiling",
            self.var_brightness,
            0.0,
            1.0,
            lambda v: setattr(self.state, "master_brightness", float(v)),
        )

        self.var_volume = self.tk.DoubleVar(value=self.state.master_volume)
        self._add_slider(
            ctrl_panel,
            "Master Audio Volume",
            self.var_volume,
            0.0,
            1.0,
            lambda v: setattr(self.state, "master_volume", float(v)),
        )

        sep = self.ttk.Separator(ctrl_panel, orient="horizontal")
        sep.pack(fill=self.tk.X, pady=10)

        self.var_override_enable = self.tk.BooleanVar(value=False)
        chk = self.ttk.Checkbutton(
            ctrl_panel,
            text="Enable Manual Micro Overrides (Decouple Rate & Rain from Intensity)",
            variable=self.var_override_enable,
            command=self._on_toggle_overrides,
        )
        chk.pack(anchor=self.tk.W, pady=(0, 6))

        self.var_rate_override = self.tk.DoubleVar(value=12.0)
        self._add_slider(
            ctrl_panel,
            "Manual Strike Rate (strikes / min)",
            self.var_rate_override,
            0.0,
            60.0,
            self._on_rate_override_change,
        )

        self.var_rain_override = self.tk.DoubleVar(value=0.5)
        self._add_slider(
            ctrl_panel,
            "Manual Rain Level [0.0 - 1.0]",
            self.var_rain_override,
            0.0,
            1.0,
            self._on_rain_override_change,
        )

        # Right Column: Live Telemetry & Action Triggers
        right_panel = self.ttk.Frame(
            mid_frame, style="Panel.TFrame", padding=14, width=360
        )
        right_panel.pack(side=self.tk.RIGHT, fill=self.tk.BOTH, padx=(8, 0))
        right_panel.pack_propagate(False)

        self.ttk.Label(
            right_panel,
            text="MANUAL TRIGGERS & TELEMETRY",
            font=("Segoe UI", 11, "bold"),
            foreground=UI_ACCENT_BLUE,
        ).pack(anchor=self.tk.W, pady=(0, 10))

        btn_grid = self.ttk.Frame(right_panel, style="Panel.TFrame")
        btn_grid.pack(fill=self.tk.X, pady=(0, 12))

        self.ttk.Button(
            btn_grid,
            text="⚡ Random Strike",
            command=lambda: self.coordinator.trigger_strike_now(),
        ).pack(fill=self.tk.X, pady=3)
        self.ttk.Button(
            btn_grid,
            text="💥 Overhead Bolt (0.15 mi, Center)",
            command=lambda: self.coordinator.trigger_strike_now(0.15, 0.5),
        ).pack(fill=self.tk.X, pady=3)
        self.ttk.Button(
            btn_grid,
            text="🌩️ Distant Sheet Flash (5.5 mi)",
            command=lambda: self.coordinator.trigger_strike_now(5.5, None),
        ).pack(fill=self.tk.X, pady=3)
        self.ttk.Button(
            btn_grid, text="🛑 Kill Storm (Intensity = 0)", command=self._kill_storm
        ).pack(fill=self.tk.X, pady=3)

        self.lbl_telemetry = self.ttk.Label(
            right_panel, text="", style="Muted.TLabel", justify=self.tk.LEFT
        )
        self.lbl_telemetry.pack(fill=self.tk.X, pady=(8, 8))

        self.ttk.Label(
            right_panel,
            text="PENDING THUNDER QUEUE (SPEED OF SOUND):",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=self.tk.W, pady=(6, 4))
        self.txt_queue = self.tk.Text(
            right_panel,
            height=10,
            bg=UI_CANVAS_BG,
            fg="#38BDF8",
            font=("Consolas", 9),
            relief=self.tk.FLAT,
            padx=8,
            pady=6,
        )
        self.txt_queue.pack(fill=self.tk.BOTH, expand=True)

    def _add_slider(
        self,
        parent,
        label_text: str,
        var,
        min_v: float,
        max_v: float,
        callback,
    ) -> None:
        row = self.ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=self.tk.X, pady=4)
        top = self.ttk.Frame(row, style="Panel.TFrame")
        top.pack(fill=self.tk.X)
        self.ttk.Label(top, text=label_text).pack(side=self.tk.LEFT)
        val_lbl = self.ttk.Label(top, text=f"{var.get():.2f}", style="Muted.TLabel")
        val_lbl.pack(side=self.tk.RIGHT)

        def on_slide(val_str: str) -> None:
            v = float(val_str)
            val_lbl.configure(text=f"{v:.2f}")
            callback(v)

        scale = self.ttk.Scale(
            row,
            from_=min_v,
            to=max_v,
            variable=var,
            orient=self.tk.HORIZONTAL,
            command=on_slide,
        )
        scale.pack(fill=self.tk.X, pady=(2, 0))

    def _on_canvas_click(self, event) -> None:
        width = max(1, self.canvas.winfo_width())
        epicenter = max(0.0, min(1.0, event.x / width))
        if self.state.is_zero_intensity:
            self.var_intensity.set(0.25)
            self.state.intensity = 0.25
        self.coordinator.trigger_strike_now(
            forced_dist=CLICK_STRIKE_DEFAULT_DIST_MILES, forced_epicenter=epicenter
        )

    def _on_intensity_change(self, val: float) -> None:
        self.state.ramp_duration = 0.0
        self.state.intensity = val
        if self.state.is_zero_intensity:
            self.coordinator.halt_all_activity()

    def _on_min_dist_change(self, val: float) -> None:
        self.state.min_dist_miles = min(val, self.state.max_dist_miles - 0.05)

    def _on_max_dist_change(self, val: float) -> None:
        self.state.max_dist_miles = max(val, self.state.min_dist_miles + 0.05)

    def _on_toggle_overrides(self) -> None:
        if self.var_override_enable.get():
            self.state.override_rate = self.var_rate_override.get()
            self.state.override_rain = self.var_rain_override.get()
        else:
            self.state.override_rate = None
            self.state.override_rain = None

    def _on_rate_override_change(self, val: float) -> None:
        if self.var_override_enable.get():
            self.state.override_rate = val

    def _on_rain_override_change(self, val: float) -> None:
        if self.var_override_enable.get():
            self.state.override_rain = val

    def _kill_storm(self) -> None:
        self.var_intensity.set(0.0)
        self.state.intensity = 0.0
        self.coordinator.halt_all_activity()

    def _update_ui_tick(self) -> None:
        if not self.state.running:
            return

        if abs(self.var_intensity.get() - self.state.intensity) > 0.005:
            self.var_intensity.set(self.state.intensity)

        self.canvas.delete("all")
        w = max(1, self.canvas.winfo_width())
        h = LED_CANVAS_HEIGHT
        dmx = self.lighting.last_frame_dmx
        n_px = len(dmx)

        n_seg = min(n_px, MAX_DISPLAY_SEGMENTS)
        seg_w = w / n_seg

        for i in range(n_seg):
            start_idx = int(i * n_px / n_seg)
            end_idx = max(start_idx + 1, int((i + 1) * n_px / n_seg))
            val = int(np.max(dmx[start_idx:end_idx]))
            disp_v = max(12, val)
            hex_col = f"#{disp_v:02x}{disp_v:02x}{disp_v:02x}"
            x0 = i * seg_w
            self.canvas.create_rectangle(
                x0, 15, x0 + seg_w + 1, h - 15, fill=hex_col, outline=""
            )

        eff_cpm = self.state.effective_rate_per_sec * 60.0
        eff_rain = self.state.effective_rain_level * 100.0
        peak_dmx = int(np.max(dmx)) if len(dmx) else 0
        self.lbl_telemetry.configure(
            text=(
                f"Effective Strike Rate : {eff_cpm:5.1f} / min\n"
                f"Effective Rain Level  : {eff_rain:5.1f} %\n"
                f"Current Peak DMX Byte : {peak_dmx:3d} / 255\n"
                f"Active Thunder Voices : {len(self.coordinator.audio.active_voices)}"
            )
        )

        now = time.monotonic()
        active_lines: List[str] = []
        surviving_strikes: List[StrikeEvent] = []
        for st in self._tracked_strikes:
            rem = (st.timestamp + st.audio_delay_sec) - now
            if rem > 0.0 and not self.state.is_zero_intensity:
                surviving_strikes.append(st)
                active_lines.append(
                    f"Dist: {st.distance_miles:4.2f}mi | X: {st.epicenter:4.2f} | "
                    f"LPF: {st.audio_lpf_hz:4.0f}Hz | Impact: {rem:4.1f}s"
                )
        self._tracked_strikes = surviving_strikes

        self.txt_queue.delete("1.0", self.tk.END)
        if active_lines:
            self.txt_queue.insert(self.tk.END, "\n".join(active_lines))
        else:
            self.txt_queue.insert(self.tk.END, "No thunder wave fronts in transit...")

        self.root.after(int(1000 / DEFAULT_FPS), self._update_ui_tick)

    def _on_close(self) -> None:
        self.state.running = False
        self.coordinator.halt_all_activity()
        self.root.destroy()

    def run(self) -> None:
        self.root.after(50, self._update_ui_tick)
        self.root.mainloop()


# ==============================================================================
# CLI PARSER & MAIN
# ==============================================================================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Physics-Based E1.31 (Monochrome White) & Spatial Audio Thunderstorm Simulator"
    )
    parser.add_argument(
        "-i",
        "--intensity",
        type=float,
        default=DEFAULT_INTENSITY,
        help="Master storm intensity [0.0 = off, 1.0 = max]",
    )
    parser.add_argument(
        "--pixels",
        type=int,
        default=DEFAULT_PIXELS,
        help="Number of single-channel white pixels",
    )
    parser.add_argument(
        "--e131-host",
        type=str,
        default=DEFAULT_E131_HOST,
        help="Unicast target IP (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--multicast",
        action="store_true",
        default=DEFAULT_MULTICAST,
        help="Enable E1.31 multicast mode (default: unicast)",
    )
    parser.add_argument(
        "--channel-map",
        type=str,
        default=None,
        metavar="MAP",
        help="Channel map in format '<sim_ch>:<e131_ch>,...' (e.g. '0:1,1:2,2:3,3:4')",
    )
    parser.add_argument(
        "--universe",
        type=int,
        default=DEFAULT_START_UNIVERSE,
        help="Starting E1.31 DMX universe",
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        default=DEFAULT_MIN_DIST_MILES,
        help="Minimum strike distance in miles",
    )
    parser.add_argument(
        "--max-dist",
        type=float,
        default=DEFAULT_MAX_DIST_MILES,
        help="Maximum strike distance in miles",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Override average strikes per minute",
    )
    parser.add_argument(
        "--rain",
        type=float,
        default=None,
        help="Override background rain level [0.0 - 1.0]",
    )
    parser.add_argument(
        "--brightness",
        type=float,
        default=DEFAULT_MASTER_BRIGHTNESS,
        help="Master lighting ceiling [0.0 - 1.0]",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=DEFAULT_MASTER_VOLUME,
        help="Master audio volume [0.0 - 1.0]",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path(DEFAULT_ASSETS_DIR),
        help="Directory for WAV assets",
    )
    parser.add_argument(
        "--osc-host",
        type=str,
        default=DEFAULT_OSC_HOST,
        help="OSC listen bind address",
    )
    parser.add_argument(
        "--osc-port",
        type=int,
        default=DEFAULT_OSC_PORT,
        help="OSC listen UDP port",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the desktop hardware visualizer and control UI",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    use_multicast = args.multicast
    min_d = max(ABSOLUTE_MIN_DIST_MILES, args.min_dist)
    max_d = max(min_d + MIN_DIST_SPAN_MILES, args.max_dist)

    state = StormState(
        pixels=args.pixels,
        e131_host=args.e131_host,
        multicast=use_multicast,
        start_universe=args.universe,
        intensity=max(0.0, min(1.0, args.intensity)),
        min_dist_miles=min_d,
        max_dist_miles=max_d,
        override_rate=args.rate,
        override_rain=args.rain,
        master_brightness=max(0.0, min(1.0, args.brightness)),
        master_volume=max(0.0, min(1.0, args.volume)),
    )

    coordinator = StormCoordinator(
        state, args.assets_dir, args.osc_host, args.osc_port
    )

    if args.ui:
        def start_async_loop() -> None:
            asyncio.run(coordinator.run())

        engine_thread = threading.Thread(target=start_async_loop, daemon=True)
        engine_thread.start()
        ui = StormDesktopUI(coordinator)
        ui.run()
    else:
        try:
            asyncio.run(coordinator.run())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
