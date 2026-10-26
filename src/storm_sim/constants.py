"""constants.py - Physical, optical, acoustic, network, UI, and synthesis constants.

Central registry for all numerical constants, physics parameters, hardware constraints,
and default settings used across the storm-sim engine modules.
"""

from typing import Dict, Tuple

# ==============================================================================
# CORE SIMULATION & CLI DEFAULTS
# ==============================================================================

#: Default number of pixels in the simulated lightning array
DEFAULT_PIXELS: int = 4

#: Starting E1.31 sACN universe number (typically universe 1)
DEFAULT_START_UNIVERSE: int = 1

#: Frame rate for lighting rendering and sACN transmission (frames per second)
DEFAULT_FPS: int = 44

#: Default master storm intensity [0.0 = completely idle/off, 1.0 = severe storm]
DEFAULT_INTENSITY: float = 0.5

#: Default minimum lightning strike distance in miles (near horizon/overhead boundary)
DEFAULT_MIN_DIST_MILES: float = 0.1

#: Default maximum lightning strike distance in miles
DEFAULT_MAX_DIST_MILES: float = 8.0

#: Peak strike rate per minute when storm intensity reaches 1.0
DEFAULT_MAX_RATE_PER_MIN: float = 35.0

#: Master lighting brightness multiplier ceiling [0.0 to 1.0]
DEFAULT_MASTER_BRIGHTNESS: float = 1.0

#: Master audio output volume multiplier [0.0 to 1.0]
DEFAULT_MASTER_VOLUME: float = 1.0

#: Default directory for audio sample WAV files
DEFAULT_ASSETS_DIR: str = "./assets"

#: Default target IP address for E1.31 sACN unicast transmission
DEFAULT_E131_HOST: str = "127.0.0.1"

#: Default network interface bind address for optional sACN passthrough input
DEFAULT_PASSTHROUGH_BIND: str = "0.0.0.0"

#: Standard E1.31 UDP port for sACN transmission and reception
DEFAULT_PASSTHROUGH_PORT: int = 5568

#: Default network interface bind address for OSC UDP server
DEFAULT_OSC_HOST: str = "0.0.0.0"

#: Default UDP port for incoming Open Sound Control (OSC) messages
DEFAULT_OSC_PORT: int = 5005


# ==============================================================================
# METEOROLOGY & INTENSITY SCALING CONSTANTS
# ==============================================================================

#: Threshold below which storm intensity is treated as hard zero (killswitch)
ZERO_INTENSITY_EPSILON: float = 1e-5

#: Exponent for non-linear power-law scaling of strike rate with intensity:
#: rate = max_rate * (intensity ^ INTENSITY_RATE_EXPONENT)
INTENSITY_RATE_EXPONENT: float = 2.2

#: Exponent for non-linear power-law scaling of rain volume with intensity:
#: rain = intensity ^ INTENSITY_RAIN_EXPONENT
INTENSITY_RAIN_EXPONENT: float = 1.5

#: Weight parameter for Beta distribution: skews strike distances toward close
#: strikes during intense storms, and toward far strikes during light storms
BETA_DIST_SKEW_WEIGHT: float = 3.0

#: Maximum number of secondary return strokes added to a strike at peak intensity
MAX_EXTRA_STROKES_AT_PEAK: int = 5

#: Hard lower clamp on strike distance in miles to avoid division by zero
ABSOLUTE_MIN_DIST_MILES: float = 0.05

#: Hard upper clamp on strike distance in miles
ABSOLUTE_MAX_DIST_MILES: float = 20.0

#: Minimum separation between min_dist and max_dist to preserve valid distribution
MIN_DIST_SPAN_MILES: float = 0.05

#: Time slice (seconds) between strike scheduler polls during idle intervals
SCHEDULER_POLL_SLICE_SEC: float = 0.25


# ==============================================================================
# OPTICAL & LIGHTING PHYSICS CONSTANTS (1-Channel Monochrome White)
# ==============================================================================

#: Maximum DMX channels per universe (1 channel per white pixel = 512 pixels/univ)
MAX_PIXELS_PER_UNIVERSE: int = 512

#: Configurable ceiling on maximum addressable pixels across all universes
MAX_CONFIGURABLE_PIXELS: int = 5120

#: Maximum DMX byte value (8-bit brightness: 0 = off, 255 = full white)
DMX_MAX_VAL: int = 255

#: Exponent modeling diffuse cloud multiple forward scattering and extended line-source attenuation
OPTICAL_DISTANCE_EXPONENT: float = 1.10

#: Base Beer-Lambert atmospheric optical extinction coefficient (per mile)
BASE_OPTICAL_EXTINCTION: float = 0.03

#: Additional optical scattering scale factor contributed by rainfall
RAIN_OPTICAL_EXTINCTION_SCALE: float = 0.05

#: Distance offset parameter (miles) softening singularity for immediate overhead strikes
OPTICAL_SOFTENING_DIST_MILES: float = 0.45

#: Normalization offset preventing total extinction at close range
OPTICAL_NORM_OFFSET: float = 1.40

#: Minimum visible peak brightness floor to preserve distant horizon sheet lightning
MIN_PEAK_BRIGHTNESS: float = 0.18

#: Minimum Gaussian flash width (sigma, normalized to strip length [0.0 - 1.0])
BASE_SPATIAL_SIGMA: float = 0.035

#: Increase in Gaussian flash width per mile of distance (distant strikes wash wide)
SPATIAL_SIGMA_PER_MILE: float = 0.065

#: Minimum duration a stroke is held in full ON state (1/15th sec ~66.7 ms) to ensure
#: physical lighting fixtures, dimmers, and LED drivers have adequate response time to strike.
MIN_STROKE_ON_TIME_SEC: float = 1.0 / 15.0

#: Range of durations (seconds) for primary return stroke pulse (on-time plateau + exponential decay)
PRIMARY_STROKE_DURATION_RANGE_SEC: Tuple[float, float] = (0.12, 0.24)

#: Range of durations (seconds) for secondary stepped return strokes (on-time plateau + exponential decay)
SECONDARY_STROKE_DURATION_RANGE_SEC: Tuple[float, float] = (0.09, 0.16)

#: Amplitude range for secondary return strokes relative to primary stroke (1.0)
SECONDARY_STROKE_AMP_RANGE: Tuple[float, float] = (0.35, 0.85)

#: Time interval (seconds) between successive return strokes in a single strike
INTER_STROKE_GAP_RANGE_SEC: Tuple[float, float] = (0.035, 0.080)

#: Exponential decay constant for return stroke luminous envelope: exp(-k * dt / dur)
STROKE_DECAY_TIME_CONSTANT: float = 4.5

#: Tail padding (seconds) added after last stroke before event is pruned
STRIKE_ENVELOPE_TAIL_PAD_SEC: float = 0.05


# ==============================================================================
# ACOUSTIC PROPAGATION & AUDIO DSP CONSTANTS
# ==============================================================================

#: Speed of sound propagation in air at ~20°C (343 m/s = 0.21312 miles/s; ~4.69 s/mile)
SPEED_OF_SOUND_MILES_PER_SEC: float = 0.21312

#: Standard audio output sample rate in Hertz
AUDIO_SAMPLE_RATE: int = 44100

#: Low-latency callback buffer block size in sample frames
AUDIO_BLOCK_SIZE: int = 1024

#: Reference distance (miles) for line-source cylindrical acoustic attenuation
ACOUSTIC_REF_DIST_MILES: float = 0.25

#: Cylindrical line-source spreading loss coefficient (dB per decade of distance)
ACOUSTIC_CYLINDRICAL_SPREADING_FACTOR: float = 11.0

#: Acoustic boost applied at full storm intensity in dB
INTENSITY_ACOUSTIC_BOOST_DB: float = 3.0

#: Floor cutoff frequency for atmospheric low-pass filter (sub-bass rumbles)
MIN_LPF_CUTOFF_HZ: float = 110.0

#: Ceiling cutoff frequency for atmospheric low-pass filter (close snaps)
MAX_LPF_CUTOFF_HZ: float = 14000.0

#: Reference numerator for distance-dependent low-pass filter cutoff calculation
LPF_REFERENCE_NUMERATOR_HZ: float = 8000.0

#: High-frequency roll-off factor per mile of distance
LPF_DISTANCE_ROLLOFF_FACTOR: float = 1.40

#: IIR Butterworth low-pass filter order (12 dB/octave attenuation)
BUTTERWORTH_FILTER_ORDER: int = 2

#: Upper distance limit (miles) for Tier 1: dry overhead thunderclaps
TIER_CLOSE_MAX_MILES: float = 1.2

#: Upper distance limit (miles) for Tier 2: rolling mid-distance thunder
TIER_MID_MAX_MILES: float = 3.2

#: Target peak normalized amplitude for audio sample banks
SAMPLE_PEAK_NORMALIZE_TARGET: float = 0.90

#: Base volume gain scalar for continuous background rain bed relative to thunder
RAIN_BED_BASE_GAIN: float = 0.06

#: Safety ceiling clipping limit preventing DAC distortion or digital wrap-around
AUDIO_OUTPUT_CLIP_LIMIT: float = 0.98


# ==============================================================================
# PROCEDURAL SYNTHESIS & AOT AUDIO GENERATION CONSTANTS
# ==============================================================================

#: Number of unique procedural variations generated per distance tier
PROCEDURAL_VARIATIONS_PER_TIER: int = 3

#: Synthetic thunder audio durations in seconds for each distance tier
SYNTH_THUNDER_DURATIONS_SEC: Dict[str, float] = {
    "close": 6.0,
    "mid": 11.0,
    "far": 16.0,
}

#: Fixed low-pass filter cutoff frequencies in Hz for procedural thunder synthesis
SYNTH_THUNDER_LPF_HZ: Dict[str, float] = {
    "close": 4500.0,
    "mid": 1200.0,
    "far": 280.0,
}

#: Total duration in seconds of the procedural seamless rain loop
SYNTH_RAIN_LOOP_DURATION_SEC: float = 12.0

#: Duration of equal-power crossfade window (seconds) to create seamless rain loop
SYNTH_RAIN_CROSSFADE_SEC: float = 1.5

#: Bandpass filter frequency range (Hz) shaping white noise into realistic rain
SYNTH_RAIN_BANDPASS_HZ: Tuple[float, float] = (280.0, 4800.0)

#: Standard deviation of Gaussian white noise for procedural rain generation
SYNTH_RAIN_NOISE_AMPLITUDE: float = 0.08

#: Range [min, max] of secondary acoustic bursts in procedural thunderclaps
SYNTH_THUNDER_BURSTS_RANGE: Tuple[int, int] = (3, 7)

#: Exponential decay time constant (seconds) for close-range synthetic thunder
SYNTH_CLOSE_DECAY_TIME: float = 0.8

#: Exponential decay time constant (seconds) for far-range synthetic thunder
SYNTH_FAR_DECAY_TIME: float = 2.8

#: Exponential decay duration (seconds) for initial sharp crack of close thunder
SYNTH_CLOSE_INITIAL_SNAP_DECAY: float = 0.025

#: Initial amplitude boost scalar for instantaneous close thunder transient
SYNTH_CLOSE_INITIAL_SNAP_AMP: float = 2.5

#: Width range (seconds) for secondary acoustic pulse bursts in thunderclap
SYNTH_BURST_WIDTH_RANGE_SEC: Tuple[float, float] = (0.15, 0.8)

#: Relative amplitude range for secondary acoustic pulse bursts
SYNTH_BURST_AMP_RANGE: Tuple[float, float] = (0.3, 0.9)

#: Portion of total duration over which secondary pulse bursts may occur
SYNTH_BURST_TIME_SPAN_FACTOR: float = 0.6


# ==============================================================================
# UI & TEST BENCH CONSTANTS
# ==============================================================================

#: Default width in pixels of desktop visualizer test bench window
UI_WINDOW_WIDTH: int = 1040

#: Default height in pixels of desktop visualizer test bench window
UI_WINDOW_HEIGHT: int = 680

#: Dark theme background hex color
UI_BG_DARK: str = "#111318"

#: Panel / card background hex color
UI_PANEL_BG: str = "#1B1F27"

#: Canvas background hex color
UI_CANVAS_BG: str = "#07080A"

#: Visualizer accent blue hex color
UI_ACCENT_BLUE: str = "#38BDF8"

#: Primary text hex color
UI_TEXT_MAIN: str = "#E2E8F0"

#: Secondary / muted telemetry text hex color
UI_TEXT_MUTED: str = "#94A3B8"

#: Height in pixels of top simulated LED array canvas
LED_CANVAS_HEIGHT: int = 150

#: Maximum visual segments drawn across screen to prevent Canvas rendering lag
MAX_DISPLAY_SEGMENTS: int = 256

#: Default distance in miles assigned when manually clicking LED strip in UI
CLICK_STRIKE_DEFAULT_DIST_MILES: float = 0.75
