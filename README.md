# Storm-Sim: Physics-Accurate Thunderstorm Simulator

Physics-accurate E1.31 (Monochrome White) lighting and spatial audio simulator with integrated desktop test UI, embedded documentation, Freesound.org soundbank curation guides, and automated procedural synthesis fallback.

---

## Features

- **1-Channel Monochrome White E1.31 Output:** Full 512 pixels per universe over standard sACN multicast or unicast.
- **Physical Optical Attenuation:** Inverse-square falloff combined with Beer-Lambert atmospheric scattering and rain extinction.
- **Spatial Multi-Stroke Lightning:** Microsecond return stroke envelopes and distance-scaled Gaussian spread across the LED strip.
- **Real-Time Acoustic DSP:** Speed-of-sound propagation delay (\(\approx 4.69\text{ s/mi}\)), atmospheric low-pass filtering (scipy Butterworth), and constant-power stereo panning matching LED epicenters.
- **Zero-Intensity Killswitch:** Instantly silences background rain and cancels all pending thunderclaps and flashes when intensity reaches `0.0`.
- **Procedural Synthesis Fallback:** Generates realistic synthetic multi-burst thunder models and seamless stereo rain beds when no audio WAV assets are present.
- **Full OSC Control:** Live parameter manipulation, intensity ramps, and manual strike triggers over UDP.
- **Desktop Visualizer:** Tkinter test bench with live pixel strip canvas, click-to-strike support, and wave-front transit queue.

---

## Package Architecture

```text
storm-sim/
├── pyproject.toml          # PEP-621 build configuration with optional [ui, test]
├── README.md               # User guide, OSC table, and SFX curation instructions
├── assets/                 # Audio sample directories
│   ├── close/              # Tier 1 (<1.2 mi) dry, violent thunderclaps
│   ├── mid/                # Tier 2 (1.2 - 3.2 mi) rolling thunderclaps
│   ├── far/                # Tier 3 (>3.2 mi) low-frequency rumbles
│   └── rain_loop.wav       # Optional seamless stereo rain loop
├── src/
│   └── storm_sim/
│       ├── __init__.py     # Re-exports StormState, PhysicsEngine, StormCoordinator
│       ├── constants.py    # Physical, audio, optical, and UI constants
│       ├── models.py       # Dataclasses: StrokePulse, StrikeEvent, StormState
│       ├── physics.py      # PhysicsEngine: Beer-Lambert optics, Beta distance, LPF math
│       ├── lighting.py     # E131LightingEngine: sACN transmitter & last_frame_dmx
│       ├── audio.py        # AudioEngine: sounddevice polyphonic mixer & procedural synth
│       ├── osc_control.py  # OSCController: AsyncIO OSC server & dispatcher
│       ├── engine.py       # StormCoordinator: Asyncio task loop orchestration
│       ├── cli.py          # argparse CLI entry point & headless runner
│       └── ui.py           # Tkinter desktop visualizer & control bench
└── tests/                  # Simple test suite
```

---

## Installation & Quick Start

### 1. Install package in editable mode
```bash
pip install -e .
```

### 2. Run headless CLI simulator
```bash
# Basic run with 512 pixels at 65% intensity
storm-sim --pixels 512 --intensity 0.65 --e131-host 192.168.1.50
```

### 3. Launch desktop hardware visualizer & control UI
```bash
storm-sim --ui
# or directly via gui-script:
storm-sim-ui
```

---

## CLI Options

| Flag | Type | Default | Description |
|---|---|---|---|
| `-i`, `--intensity` | float | `0.5` | Master storm intensity (`0.0` = off, `1.0` = max) |
| `--pixels` | int | `512` | Single-channel white pixel count across LED array |
| `--e131-host` | str | `None` | Unicast target IP (omit to use standard multicast) |
| `--multicast` | flag | `False` | Force E1.31 multicast mode |
| `--universe` | int | `1` | Starting E1.31 DMX universe |
| `--min-dist` | float | `0.1` | Minimum strike distance (miles) |
| `--max-dist` | float | `8.0` | Maximum strike distance (miles) |
| `--rate` | float | `None` | Manual override: strikes per minute |
| `--rain` | float | `None` | Manual override: background rain level [0.0 - 1.0] |
| `--brightness` | float | `1.0` | Master lighting ceiling scalar [0.0 - 1.0] |
| `--volume` | float | `1.0` | Master audio volume scalar [0.0 - 1.0] |
| `--assets-dir` | Path | `./assets`| Directory containing audio sample folders |
| `--osc-host` | str | `0.0.0.0` | OSC listen bind address |
| `--osc-port` | int | `5005` | OSC UDP port |
| `--ui` | flag | `False` | Launch native desktop hardware visualizer UI |

---

## Open Sound Control (OSC) Specification

All simulation parameters can be modified dynamically over UDP OSC:

| OSC Address | Arguments | Description |
|---|---|---|
| `/storm/intensity` | `[float 0.0 - 1.0]` | Master intensity (`0.0` = immediate hard killswitch) |
| `/storm/intensity/ramp` | `[float target, float duration_sec]` | Interpolate intensity smoothly over time |
| `/storm/intensity/couple`| `[int 1]` | Re-couple strike rate & rain level to master intensity |
| `/storm/distance/min` | `[float]` | Minimum strike distance (miles) |
| `/storm/distance/max` | `[float]` | Maximum strike distance (miles) |
| `/storm/rate` | `[float]` | Manual override: strikes per minute |
| `/storm/rain/level` | `[float 0.0 - 1.0]` | Manual override: background rain level |
| `/storm/light/gain` | `[float 0.0 - 1.0]` | Master lighting ceiling scalar |
| `/storm/audio/gain` | `[float 0.0 - 1.0]` | Master audio output scalar |
| `/storm/config/pixels` | `[int]` | Horizontal monochrome white pixel count |
| `/storm/strike/trigger` | `[float dist_mi, float epicenter]` | Manual trigger: distance in miles, epicenter `[0.0 - 1.0]` |

---

## Sound Effects (SFX) Asset Curation Guide

> [!IMPORTANT]
> **Audio Design Rule:** ONLY use "dry" thunder recordings (recorded before rainfall begins or cleanly isolated). If thunder samples have baked-in rain noise, the engine's real-time low-pass filter and stereo panner will cause unnatural swelling and abrupt cuts of rain ambience during thunderclaps.

### Recommended Freesound.org Catalog IDs

- **Tier 1: Close / Overhead Strikes (< 1.2 miles)**
  - *Acoustics:* Instantaneous high-frequency 'snap/crack', zero pre-rumble, wide bandwidth.
  - **ID 670692:** "Thunder / Lightning - I - Without Rain" by GregorQuendel
  - **ID 536903:** "thunder dry crack rumble.wav" by cognito perceptu
  - **ID 446753:** "Heavy Thunder Strike - no Rain - QUADRO.wav" by BlueDelta

- **Tier 2: Mid-Range Strikes (1.2 to 3.2 miles)**
  - *Acoustics:* Attenuated highs (>6 kHz absorbed), body echoes, rolling tail.
  - **IDs 469612 & 521096:** "Thunder Clap And Rumble #2 & #3" by Kinoton
  - **ID 194364:** "Thunder Clap OWB KY 441x16.wav" by Dave Welsh

- **Tier 3: Distant / Horizon Rumbles (> 3.2 miles)**
  - *Acoustics:* Heavy air absorption, low-frequency pressure wave (40-300 Hz dominant).
  - **ID 24952:** "thunder-long-distance.wav" by Erdie
  - **Pack 43490:** "Distant_Thunder_Denoised_01" by loganzsound

- **Background Rain Bed:**
  - **ID 624645:** "Heavy_Rain_Loop.wav" by Rubaoliva (Seamlessly looping stereo rain bed)

### Asset Ingestion Checklist
1. **Trim leading silence:** Strip audio before first sample > -45 dBFS so the calculated speed-of-sound delay (\(\Delta t = 4.69 \cdot d\)) matches precisely.
2. **Peak normalize:** Normalize all files to -1.0 dBFS (or equal LUFS) so distance attenuation curves operate from a calibrated baseline.
3. **Sum to mono:** Convert thunder samples to mono so the engine's constant-power panner can place the acoustic origin at the exact LED epicenter. Keep rain stereo.

---

## Running Tests

To run the test suite:
```bash
pytest
```
