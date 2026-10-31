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

        # By default (override_rain is None), rain is 0.0 (silence)
        audio._audio_callback(out, 1024, None, None)
        assert np.all(out == 0.0)

        # When rain override is enabled (> 0), rain generates audible non-zero output
        state.override_rain = 0.5
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
    from scipy import signal
    from storm_sim.audio import _get_cached_butterworth_sos
    from storm_sim.constants import AUDIO_SAMPLE_RATE

    state = StormState(intensity=0.7)
    audio = AudioEngine(state)
    sos_infra = _get_cached_butterworth_sos(100, AUDIO_SAMPLE_RATE)
    try:
        strike = PhysicsEngine.generate_strike(
            state, now=0.0, forced_dist=0.5, forced_epicenter=0.0
        )
        assert len(audio.active_voices) == 0
        audio.schedule_thunder(strike)
        assert len(audio.active_voices) == 1
        stereo_buf, _ = audio.active_voices[0]
        # Thunderclaps within 1.0 mile must have their infrasonic (<100 Hz) peak at/near 0 dBFS
        infra_buf = signal.sosfilt(sos_infra, stereo_buf, axis=0)
        assert np.max(np.abs(infra_buf)) >= 0.94  # within ~0.5 dB of 0 dBFS
        assert np.max(np.abs(stereo_buf)) <= 1.0
        # Hard-left strike (epicenter=0.0): initial 50ms has 0 energy on right channel,
        # but lateral building reflections (>190ms) bounce energy into the right channel
        assert np.allclose(stereo_buf[:2000, 1], 0.0)
        assert np.max(np.abs(stereo_buf[9000:, 1])) > 0.0
        audio.clear_voices()
        assert len(audio.active_voices) == 0

        # Verify infrasonic (<100 Hz) peak is at/near 0 dBFS across distances <= 1.0 mi and center pan (0.5)
        for dist in (0.1, 0.5, 1.0):
            s_close = PhysicsEngine.generate_strike(
                state, now=0.0, forced_dist=dist, forced_epicenter=0.5
            )
            assert s_close.audio_gain_linear == 1.0
            audio.schedule_thunder(s_close)
            buf, _ = audio.active_voices[-1]
            infra_c = signal.sosfilt(sos_infra, buf, axis=0)
            assert np.max(np.abs(infra_c)) >= 0.94  # within ~0.5 dB of 0 dBFS
            assert np.max(np.abs(buf)) <= 1.0
        audio.clear_voices()
    finally:
        audio.stop()
