"""test_synthesis.py - Simple tests for procedural synthesis and AOT soundbank export."""

from pathlib import Path
import numpy as np

from storm_sim.synthesis import ThunderSynthesizer


def test_synthesize_thunder():
    synth = ThunderSynthesizer(sample_rate=22050)  # low sample rate for fast test
    audio = synth.synthesize_thunder("close")
    assert isinstance(audio, np.ndarray)
    assert audio.ndim == 1
    assert audio.dtype == np.float32
    assert len(audio) > 0


def test_synthesize_rain_loop():
    synth = ThunderSynthesizer(sample_rate=22050)
    rain = synth.synthesize_rain_loop(duration_sec=2.0)
    assert isinstance(rain, np.ndarray)
    assert rain.ndim == 2
    assert rain.shape[1] == 2  # Stereo
    assert rain.dtype == np.float32


def test_export_soundbank_to_directory(tmp_path: Path):
    synth = ThunderSynthesizer(sample_rate=22050)
    synth.export_soundbank(output_dir=tmp_path, variations_per_tier=1)

    assert (tmp_path / "close" / "synth_close_01.wav").is_file()
    assert (tmp_path / "mid" / "synth_mid_01.wav").is_file()
    assert (tmp_path / "far" / "synth_far_01.wav").is_file()
    assert (tmp_path / "rain_loop.wav").is_file()
