# Storm-Sim: Physics-Accurate Thunderstorm Simulator

Physics-accurate E1.31 sACN lighting and spatial audio thunderstorm simulator with customizable channel mapping, integrated desktop visualizer UI, and automated procedural synthesis fallback.

---

## Features

- **E1.31 sACN Lighting Output with Channel Mapping:** Defaults to 4 pixels over standard unicast (or multicast), with flexible `<sim_ch>:<e131_ch>` channel mapping supporting multi-universe configurations.
- **Physical Optical Attenuation:** Inverse-square geometric spreading combined with Beer-Lambert atmospheric scattering and rain extinction (see [Scientific Citations & Model References](#scientific-citations--model-references)).
- **Spatial Multi-Stroke Lightning:** Microsecond return stroke envelopes and distance-scaled Gaussian spread across the simulated lightning channels.
- **Real-Time Acoustic DSP:** Speed-of-sound propagation delay (\(\approx 4.69\text{ s/mi}\)), atmospheric low-pass filtering (scipy Butterworth), and constant-power stereo panning matching lighting epicenters.
- **Zero-Intensity Killswitch:** Instantly silences background rain and cancels all pending thunderclaps and flashes when intensity reaches `0.0`.
- **Procedural Synthesis Fallback:** Generates realistic synthetic multi-burst thunder models and seamless stereo rain beds when no audio WAV assets are present.
- **Full OSC Control:** Live parameter manipulation, intensity ramps, and manual strike triggers over UDP.
- **Desktop Visualizer:** Tkinter test bench with live pixel strip canvas, click-to-strike support, and wave-front transit queue.

---

## Scientific Citations & Model References

The mathematical models for optical attenuation, atmospheric extinction, and acoustic propagation are grounded in established atmospheric physics literature. For complete bibliographic citations, paper links, and mathematical derivations, see [MODEL_CITATIONS.md](file:///Users/nashkaminski/Developer/storm-simulator/MODEL_CITATIONS.md).

Key foundation papers include:
- **Optical Extinction & Rainfall Scattering:** [Bouguer (1729)](file:///Users/nashkaminski/Developer/storm-simulator/MODEL_CITATIONS.md#bouguer-lambert-beer-law), [Lambert (1760)](file:///Users/nashkaminski/Developer/storm-simulator/MODEL_CITATIONS.md#bouguer-lambert-beer-law), [Beer (1852)](https://doi.org/10.1002/andp.18521620505), and [Atlas (1953)](https://doi.org/10.1175/1520-0469(1953)010%3C0486:OEBR%3E2.0.CO;2).
- **Lightning Radiative Transfer & Multi-Stroke Physics:** Uman (1987), [Thomason & Krider (1982)](https://doi.org/10.1175/1520-0469(1982)039%3C2051:TEOCOT%3E2.0.CO;2), and [Krider & Guo (1983)](https://doi.org/10.1029/JC088iC13p08623).
- **Acoustic Wave Propagation & Atmospheric Absorption:** [Bass et al. (1995)](https://doi.org/10.1121/1.412989) (ISO 9613-1) and [Few (1969)](https://doi.org/10.1029/JC074i028p06926).

---

## Package Architecture

```text
storm-sim/
├── pyproject.toml          # PEP-621 build configuration with optional [ui, test]
├── README.md               # User guide, OSC table, and quick start
├── MODEL_CITATIONS.md      # Scientific literature citations & derivations
├── SFX_GUIDE.md            # Sound Effects (SFX) asset curation & Freesound catalog
├── assets/                 # Audio sample directories
│   ├── close/              # Tier 1 (<1.2 mi) dry, violent thunderclaps
│   ├── mid/                # Tier 2 (1.2 - 3.2 mi) rolling thunderclaps
│   ├── far/                # Tier 3 (>3.2 mi) low-frequency rumbles
│   └── rain_loop.wav       # Optional seamless stereo rain loop
├── src/
│   └── storm_sim/
│       ├── __init__.py     # Re-exports StormState, PhysicsEngine, StormCoordinator
│       ├── constants.py    # Physical, audio, optical, and UI constants
│       ├── models.py       # Dataclasses: StrokePulse, StrikeEvent, StormState, channel map
│       ├── physics.py      # PhysicsEngine: Beer-Lambert optics, Beta distance, LPF math
│       ├── lighting.py     # E131LightingEngine: sACN transmitter & channel mapper
│       ├── audio.py        # AudioEngine: sounddevice polyphonic mixer & cached LPF SOS
│       ├── synthesis.py    # ThunderSynthesizer: Dedicated procedural generator & CLI
│       ├── osc_control.py  # OSCController: AsyncIO OSC server & dispatcher
│       ├── engine.py       # StormCoordinator: Asyncio task loop orchestration
│       ├── cli.py          # argparse CLI entry point & headless runner
│       └── ui.py           # Tkinter desktop visualizer & control bench
└── tests/                  # Fast unit test suite
```

---

## Installation & Quick Start

### 1. Install package in editable mode
```bash
pip install -e .
```

### 2. Run headless CLI simulator
```bash
# Basic run with default 4 pixels unicast to 127.0.0.1:
storm-sim --intensity 0.65

# Custom unicast target IP and channel map:
storm-sim --pixels 4 --e131-host 192.168.1.50 --channel-map "0:1,1:2,2:3,3:4"
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
| `--pixels` | int | `4` | Number of simulated lightning channels (default: `4`) |
| `--e131-host` | str | `127.0.0.1` | Target IP for E1.31 unicast transmission (default: unicast) |
| `--multicast` | flag | `False` | Enable E1.31 multicast mode (default: unicast) |
| `--channel-map` | str | `None` | Custom channel map: `<sim_ch>:<e131_ch>,...` (e.g. `0:1,1:2,2:3,3:4`) |
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

### Channel Mapping Examples

The `--channel-map` flag maps simulated lightning channels to output E1.31 DMX channels:

```bash
# Map 4 simulator pixels (0-3) to DMX channels 1, 2, 3, 4:
storm-sim --pixels 4 --channel-map "0:1,1:2,2:3,3:4"

# Map 4 simulator pixels to custom lighting fixture channels:
storm-sim --pixels 4 --channel-map "0:10,1:25,2:50,3:100"

# 1-based simulator channel indexing is also supported:
storm-sim --pixels 4 --channel-map "1:10,2:25,3:50,4:100"
```

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
| `/storm/config/pixels` | `[int]` | Horizontal simulated pixel count |
| `/storm/strike/trigger` | `[float dist_mi, float epicenter]` | Manual trigger: distance in miles, epicenter `[0.0 - 1.0]` |

---

## Sound Effects (SFX) Asset Curation Guide

For Freesound.org catalog IDs, acoustic requirements, and asset normalization guidelines, see [SFX_GUIDE.md](file:///Users/nashkaminski/Developer/storm-simulator/SFX_GUIDE.md).

---

## Running Tests

To run the test suite:
```bash
pytest
```
