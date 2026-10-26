"""constants.py - Physical, optical, acoustic, network, UI, and synthesis constants."""

from typing import Dict, Tuple

# ==============================================================================
# CORE SIMULATION & CLI DEFAULTS
# ==============================================================================
DEFAULT_PIXELS: int = 512
DEFAULT_START_UNIVERSE: int = 1
DEFAULT_FPS: int = 44
DEFAULT_INTENSITY: float = 0.5
DEFAULT_MIN_DIST_MILES: float = 0.1
DEFAULT_MAX_DIST_MILES: float = 8.0
DEFAULT_MAX_RATE_PER_MIN: float = 35.0
DEFAULT_MASTER_BRIGHTNESS: float = 1.0
DEFAULT_MASTER_VOLUME: float = 1.0
DEFAULT_ASSETS_DIR: str = "./assets"
DEFAULT_OSC_HOST: str = "0.0.0.0"
DEFAULT_OSC_PORT: int = 5005

# ==============================================================================
# METEOROLOGY & INTENSITY SCALING CONSTANTS
# ==============================================================================
ZERO_INTENSITY_EPSILON: float = 1e-5
INTENSITY_RATE_EXPONENT: float = 2.2
INTENSITY_RAIN_EXPONENT: float = 1.5
BETA_DIST_SKEW_WEIGHT: float = 3.0
MAX_EXTRA_STROKES_AT_PEAK: int = 5
ABSOLUTE_MIN_DIST_MILES: float = 0.05
ABSOLUTE_MAX_DIST_MILES: float = 20.0
MIN_DIST_SPAN_MILES: float = 0.05
SCHEDULER_POLL_SLICE_SEC: float = 0.25

# ==============================================================================
# OPTICAL & LIGHTING PHYSICS CONSTANTS (1-Channel Monochrome White)
# ==============================================================================
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

# ==============================================================================
# ACOUSTIC PROPAGATION & AUDIO DSP CONSTANTS
# ==============================================================================
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

# ==============================================================================
# PROCEDURAL SYNTHESIS & AOT AUDIO GENERATION CONSTANTS
# ==============================================================================
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
SYNTH_RAIN_NOISE_AMPLITUDE: float = 0.15
SYNTH_THUNDER_BURSTS_RANGE: Tuple[int, int] = (3, 7)
SYNTH_CLOSE_DECAY_TIME: float = 0.8
SYNTH_FAR_DECAY_TIME: float = 2.8
SYNTH_CLOSE_INITIAL_SNAP_DECAY: float = 0.025
SYNTH_CLOSE_INITIAL_SNAP_AMP: float = 2.5
SYNTH_BURST_WIDTH_RANGE_SEC: Tuple[float, float] = (0.15, 0.8)
SYNTH_BURST_AMP_RANGE: Tuple[float, float] = (0.3, 0.9)
SYNTH_BURST_TIME_SPAN_FACTOR: float = 0.6

# ==============================================================================
# UI & TEST BENCH CONSTANTS
# ==============================================================================
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
