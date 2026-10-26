"""test_physics.py - Simple tests for physical equations and strike generation."""

from storm_sim.constants import MIN_STROKE_ON_TIME_SEC
from storm_sim.models import StormState
from storm_sim.physics import PhysicsEngine


def test_generate_strike_forced_parameters():
    state = StormState(intensity=0.5)
    strike = PhysicsEngine.generate_strike(
        state, now=100.0, forced_dist=2.5, forced_epicenter=0.75
    )
    assert strike.timestamp == 100.0
    assert strike.distance_miles == 2.5
    assert strike.epicenter == 0.75
    assert strike.stereo_pan == 0.75
    assert len(strike.strokes) >= 1
    assert strike.strokes[0].peak_amplitude == 1.0
    for s in strike.strokes:
        assert s.on_time_sec >= (1.0 / 15.0)
        assert s.duration_sec > s.on_time_sec


def test_audio_delay_increases_with_distance():
    state = StormState(intensity=0.5)
    close_strike = PhysicsEngine.generate_strike(state, now=0.0, forced_dist=1.0)
    far_strike = PhysicsEngine.generate_strike(state, now=0.0, forced_dist=5.0)

    assert far_strike.audio_delay_sec > close_strike.audio_delay_sec
    # Speed of sound is ~4.69 sec/mile
    assert 4.5 < close_strike.audio_delay_sec < 4.9
    assert 22.0 < far_strike.audio_delay_sec < 25.0


def test_optical_attenuation():
    state = StormState(intensity=0.5)
    close_strike = PhysicsEngine.generate_strike(state, now=0.0, forced_dist=0.2)
    far_strike = PhysicsEngine.generate_strike(state, now=0.0, forced_dist=6.0)

    # Close strike should be significantly brighter
    assert close_strike.peak_brightness > far_strike.peak_brightness
    # Distance spreads optical sigma wider
    assert far_strike.spatial_sigma > close_strike.spatial_sigma


def test_atmospheric_lpf():
    state = StormState(intensity=0.5)
    close_strike = PhysicsEngine.generate_strike(state, now=0.0, forced_dist=0.3)
    far_strike = PhysicsEngine.generate_strike(state, now=0.0, forced_dist=4.0)

    # Distant strike high frequencies are attenuated (lower cutoff Hz)
    assert close_strike.audio_lpf_hz > far_strike.audio_lpf_hz


def test_distance_distribution_skews_closer_with_intensity():
    import random
    random.seed(42)

    light_state = StormState(intensity=0.15, min_dist_miles=0.1, max_dist_miles=3.0)
    severe_state = StormState(intensity=0.90, min_dist_miles=0.1, max_dist_miles=3.0)

    n_samples = 1000
    light_distances = [
        PhysicsEngine.generate_strike(light_state, now=0.0).distance_miles
        for _ in range(n_samples)
    ]
    severe_distances = [
        PhysicsEngine.generate_strike(severe_state, now=0.0).distance_miles
        for _ in range(n_samples)
    ]

    # Verify all distances remain within bounds
    for d in light_distances:
        assert 0.1 <= d <= 3.0
    for d in severe_distances:
        assert 0.1 <= d <= 3.0

    mean_light = sum(light_distances) / n_samples
    mean_severe = sum(severe_distances) / n_samples

    sorted_light = sorted(light_distances)
    sorted_severe = sorted(severe_distances)
    median_light = sorted_light[n_samples // 2]
    median_severe = sorted_severe[n_samples // 2]

    # Light storm distances should stay predominantly distant
    assert mean_light > 1.8
    assert median_light > 1.8

    # Severe storm distances must nonlinearly err close to the observer (< 0.5 mi mean)
    assert mean_severe < 0.5
    assert median_severe < 0.35

    # Over 85% of severe strikes should be under 0.85 miles
    close_severe_count = sum(1 for d in severe_distances if d < 0.85)
    assert close_severe_count / n_samples > 0.85

