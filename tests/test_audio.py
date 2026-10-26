"""test_audio.py - Simple tests for audio synthesis and mixer callbacks."""

import numpy as np

from storm_sim.audio import AudioEngine
from storm_sim.models import StormState
from storm_sim.physics import PhysicsEngine


def test_audio_procedural_generation():
    state = StormState(intensity=0.5)
    audio = AudioEngine(state)
    try:
        assert len(audio.thunder_bank["close"]) > 0
        assert len(audio.thunder_bank["mid"]) > 0
        assert len(audio.thunder_bank["far"]) > 0
        assert len(audio.rain_loop) > 0
    finally:
        audio.stop()


def test_audio_callback_rain_and_killswitch():
    state = StormState(intensity=0.5)
    audio = AudioEngine(state)
    try:
        out = np.zeros((1024, 2), dtype=np.float32)

        # At intensity 0.5, rain generates audible non-zero output
        audio._audio_callback(out, 1024, None, None)
        assert np.any(out != 0.0)

        # At zero intensity, callback outputs silence (all 0.0)
        state.intensity = 0.0
        out.fill(99.0)
        audio._audio_callback(out, 1024, None, None)
        assert np.all(out == 0.0)
    finally:
        audio.stop()


def test_audio_rain_level_scaling_and_headroom():
    state = StormState(intensity=0.5)
    audio = AudioEngine(state)
    try:
        out_mid = np.zeros((2048, 2), dtype=np.float32)
        state.override_rain = 0.5
        audio._audio_callback(out_mid, 2048, None, None)
        peak_mid = np.max(np.abs(out_mid))

        out_high = np.zeros((2048, 2), dtype=np.float32)
        state.override_rain = 1.0
        audio._audio_callback(out_high, 2048, None, None)
        peak_high = np.max(np.abs(out_high))

        out_zero = np.zeros((2048, 2), dtype=np.float32)
        state.override_rain = 0.0
        audio._audio_callback(out_zero, 2048, None, None)

        # Rain volume scales monotonically with override_rain
        assert peak_high > peak_mid > 0.0
        assert np.all(out_zero == 0.0)

        # Rain bed must remain comfortable ambient level (< 0.10 peak) leaving headroom for thunder (0.90)
        assert peak_high < 0.10
    finally:
        audio.stop()


def test_audio_schedule_thunder_voice():
    state = StormState(intensity=0.7)
    audio = AudioEngine(state)
    try:
        strike = PhysicsEngine.generate_strike(
            state, now=0.0, forced_dist=0.5, forced_epicenter=0.25
        )
        assert len(audio.active_voices) == 0
        audio.schedule_thunder(strike)
        assert len(audio.active_voices) == 1
        audio.clear_voices()
        assert len(audio.active_voices) == 0
    finally:
        audio.stop()
