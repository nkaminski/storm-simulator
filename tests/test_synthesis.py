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


def test_synthesize_thunder_small_speakers():
    synth = ThunderSynthesizer(sample_rate=22050, small_speakers=True)
    audio = synth.synthesize_thunder("close")
    assert isinstance(audio, np.ndarray)
    assert audio.ndim == 1
    assert audio.dtype == np.float32
    assert len(audio) > 0
    assert np.max(np.abs(audio)) <= 1.0


def test_synthesize_thunder_explosion_attack():
    synth = ThunderSynthesizer(sample_rate=22050)
    att = synth._get_explosion_attack()
    assert att is not None
    assert isinstance(att, np.ndarray)
    assert len(att) > 0
    audio_close = synth.synthesize_thunder("close")
    assert np.max(np.abs(audio_close)) <= 1.0


def test_storm_synth_cli_parsing():
    from storm_sim.synthesis import parse_args as parse_synth_args

    args = parse_synth_args(["--small-speakers", "-v", "2", "-s", "22050"])
    assert args.small_speakers is True
    assert args.variations == 2
    assert args.sample_rate == 22050
