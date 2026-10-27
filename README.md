# Storm-Simulator: Physics-Accurate Thunderstorm Simulator

Physics-accurate E1.31/sACN lighting and spatial audio thunderstorm simulator with customizable channel mapping, integrated desktop visualizer UI, and automated procedural synthesis fallback.

> [!NOTE]
> This codebase, lighting engine, and DSP synthesis pipeline were produced in substantial capacity using generative AI. All underlying physical modeling, optical attenuation models, and acoustic calibrations are derived strictly from empirical ground truth, peer-reviewed atmospheric physics literature, real-world audio measurement and human feedback on synthesized outputs (see [MODEL_CITATIONS.md](MODEL_CITATIONS.md)).

---

## Features

- **E1.31/sACN Lighting Output with Channel Mapping:** Defaults to 4 pixels over standard unicast, with flexible `<sim_ch>:<e131_ch>` channel mapping supporting multi-universe configurations.
- **sACN Passthrough Mode with Nonzero Override:** Feed a full DMX universe from an external lighting desk through the simulator. Desk channels pass through untouched, and only channels with nonzero lightning output override the desk (remapping never shifts or alters passthrough channels).
- **Optical Attenuation Model:** Inverse-square geometric spreading combined with Beer-Lambert atmospheric scattering and rain extinction (see [Scientific Citations & Model References](#scientific-citations--model-references)).
- **Spatial Multi-Stroke Lightning:** Microsecond return stroke envelopes and distance-scaled Gaussian spread across the simulated lightning channels.
- **Real-Time Acoustic DSP:** Speed-of-sound propagation delay (\(\approx 4.69\text{ s/mi}\)), atmospheric low-pass filtering (scipy Butterworth), and constant-power stereo panning matching lighting epicenters.
- **Full OSC Control:** Live parameter manipulation, intensity ramps, and manual strike triggers over UDP.
- **Desktop Visualizer:** Tkinter test bench with live pixel strip canvas, click-to-strike support, and wave-front transit queue.

---

## Scientific Citations & Model References

The mathematical models for optical attenuation, atmospheric scattering, and acoustic propagation are grounded in established physics literature. For complete bibliographic citations, paper links, and mathematical derivations, see [MODEL_CITATIONS.md](MODEL_CITATIONS.md).

Key foundation papers include:
- **Optical Extinction & Rainfall Scattering:** [Bouguer (1729)](MODEL_CITATIONS.md#bouguer-lambert-beer-law), [Lambert (1760)](MODEL_CITATIONS.md#bouguer-lambert-beer-law), [Beer (1852)](https://doi.org/10.1002/andp.18521620505), and [Atlas (1953)](https://doi.org/10.1175/1520-0469(1953)010%3C0486:OEBR%3E2.0.CO;2).
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
| `--e131-host` | str | `127.0.0.1` | Target IP for E1.31 unicast transmission |
| `--passthrough` | str | `None` | Optional sACN passthrough listen address and port (`address:port`, e.g. `0.0.0.0:5568`) |
| `--passthrough-universe` | int | `None` | Optional input universe to listen on for passthrough (default: matches `--universe`) |
| `--channel-map` | str | `None` | Custom channel map: `<sim_ch>:<e131_ch>,...` (e.g. `0:1,1:2,2:3,3:4`) |
| `--universe` | int | `1` | Starting E1.31 DMX universe |
| `--min-dist` | float | `0.1` | Minimum strike distance (miles) |
| `--max-dist` | float | `3.0` | Maximum strike distance (miles) |
| `--rate` | float | `None` | Manual override: strikes per minute |
| `--rain` | float | `None` | Manual override: background rain level [0.0 - 1.0] |
| `--brightness` | float | `1.0` | Master lighting ceiling scalar [0.0 - 1.0] |
| `--volume` | float | `1.0` | Master audio volume scalar [0.0 - 1.0] |
| `--assets-dir` | Path | `./assets`| Directory containing audio sample folders |
| `--osc-host` | str | `0.0.0.0` | OSC listen bind address |
| `--osc-port` | int | `5005` | OSC UDP port |
| `--ui` | flag | `False` | Launch native desktop hardware visualizer UI |
| `--small-speakers` | flag | `False` | CLI-only startup flag: elevates infrasonics (48-140 Hz with saturation) for compact monitors lacking subwoofers |

### Channel Mapping & Fixture Grouping Examples

The `--channel-map` flag maps simulated lightning channels to output E1.31 DMX channels. It supports single channels, channel ranges (`start-end` or `start..end`), multi-channel grouping (mirroring a single simulated flash across multiple DMX fixtures simultaneously), and both 0-based and 1-based simulator channel indexing:

```bash
# Basic 1:1 mapping (4 simulator pixels 0-3 mapped to DMX channels 1, 2, 3, 4):
storm-sim --pixels 4 --channel-map "0:1,1:2,2:3,3:4"

# Custom fixture channels across a venue rig:
storm-sim --pixels 4 --channel-map "0:10,1:25,2:50,3:100"

# Real-world fixture grouping with individual channels and grouped ranges:
# (Sim 0-2 drive channels 45, 46, 47; Sim 3 drives channels 88-90 as a group; Sim 4 drives 93-95 as a group)
storm-sim --pixels 5 --e131-host 192.168.1.50 --channel-map "0:45,1:46,2:47,3:88-90,4:93-95"

# 1-based simulator channel indexing is also fully supported:
storm-sim --pixels 5 --e131-host 192.168.1.50 --channel-map "1:45,2:46,3:47,4:88-90,5:93-95"
```

### Compact Speaker Audio Mode (`--small-speakers`)

Thunder acoustics concentrate substantial acoustic energy in the deep infrasonic sub-bass region ($20–80\text{ Hz}$). When operating on desktop monitors, bookshelf speakers, or laptops lacking a dedicated subwoofer, standard transducers cannot reproduce sub-audible pressure waves.

Supply the `--small-speakers` CLI flag at startup to re-tune the synthesis engine:
```bash
# Run simulator with compact speaker tuning
storm-sim --small-speakers --ui

# Or pre-generate a soundbank optimized for compact monitors
storm-synth --small-speakers --out-dir ./assets
```
- **Frequency Shift:** Elevates sub-bass fundamental pulses from $20–82\text{ Hz}$ to $48–140\text{ Hz}$.
- **Soft Saturation:** Applies musical even-order harmonic distortion to create visceral, punchy low-end presence on small drivers without digital clipping.
- **CLI Startup Configuration:** Note that `--small-speakers` is configured at startup on the CLI (rather than toggled live in the GUI) because it initializes the procedural DSP voice and soundbank generation before playback begins.

### sACN Passthrough Mode

When `--passthrough <address:port>` is supplied, `storm-sim` listens for an incoming full DMX universe from an external lighting effects console or software desk:
- **Passthrough Preservation:** All 512 channels from the desk pass straight through 1:1 to the output fixtures without alterations.
- **Conditional Nonzero Override:** When a lightning flash occurs, only the specific channels mapped to active lightning fixtures are overridden, and only when their DMX value is strictly greater than 0 (`> 0`). When lightning channels decay back to 0, control of those channels immediately reverts back to the desk.
- **Remapping Independence:** Lightning channel remapping (`--channel-map`) only routes simulator pixels to their destination slots; it **never** alters, shifts, or remaps the passthrough desk channels.

```bash
# Listen on standard sACN port 5568 across all network interfaces:
storm-sim --passthrough 0.0.0.0:5568 --e131-host 192.168.1.100

# Listen on custom port with remapped lightning channels:
# (Desk channels 10, 25, 50, 100 are overridden only during active lightning;
# all other 508 channels pass through untouched directly from the desk)
storm-sim --passthrough 0.0.0.0:5568 --channel-map "0:10,1:25,2:50,3:100" --e131-host 192.168.1.100

# Feed desk universe 2 into simulator output universe 1:
storm-sim --passthrough 0.0.0.0:5568 --passthrough-universe 2 --universe 1
```

---

## Recommended Presets & Storm Profiles

The optical engine is tuned to err toward the dramatic aesthetic of being on the open waters of **Lake Michigan** during a Midwest squall, where water reflections and cloud-deck diffusion illuminate the entire horizon.

### Photometric Calibration Benchmark (3 kW Tungsten Reference)
The lighting subsystem uses a **3 kW tungsten-halogen baseline (~78,000 lumens)** as its photometric full-scale calibration benchmark:
- **Full Output ($DMX = 255$, 100%):** Equivalent to 3,000 Watts of incandescent/halogen stage illumination (~78,000 lm), representing an unattenuated strike ($d \le 1.2\text{ mi}$) saturating the visual field.
- **Mid-Distance Flashes ($DMX = 100–180$):** Equivalent to 1,200 W – 2,000 W of tungsten output (~30,000 – 50,000 lm) casting soft, broad cloud illumination.
- **Distant Sheet Horizon Floor ($DMX = 60–80$):** Equivalent to 700 W – 900 W of tungsten output (~18,000 – 24,000 lm) preserving visible sheet lightning across water.
- **AC LED Dynamics Model:** Fixture on-time is locked to 4 AC cycles ($1/15\text{ s} \approx 66.7\text{ ms}$) to overcome LED driver startup and forward diode voltage ($V_f$), followed by exponential decay ($k = 4.2$) and 3–6 AC cycle gaps ($50–100\text{ ms}$) for TRIAC zero-crossing commutation.

### 1. Typical / Moderate Illinois Thunderstorm (Default Experience)
*Realistic prairie summer storm cell passing overhead with rolling thunder and dramatic water/cloud reflections.*
- **Aesthetic:** Dramatic balance of crisp overhead bolts (saturating localized pixels to full DMX 255), prominent mid-range strikes at 2–3 miles (peaking at ~120–150 DMX), and broad diffuse sheet flashes illuminating the cloud base across all channels.
- **CLI Command:**
  ```bash
  storm-sim --intensity 0.65 --min-dist 0.2 --max-dist 6.0
  ```
- **Profile Parameters:**
  - `intensity`: `0.65` (automatic power-law strike rate \(\approx 14\text{ strikes/min}\), rain volume \(\approx 0.52\))
  - `min_dist`: `0.2` miles (\(\approx 1,000\text{ ft}\))
  - `max_dist`: `6.0` miles
  - **Acoustic / Optical Characteristics:** Beta distribution skews ~60% of strikes between 1.0 and 3.5 miles; return stroke bursts average 2–3 pulses with 30–70 ms gaps; acoustic delays span 1 to 28 seconds.

### 2. Light / Distant Storm (Summer Night Horizon Sheet Lightning)
*Soft, distant lightning rolls along the horizon with deep subterranean rumbles and zero harsh overhead snaps.*
- **Aesthetic:** Gentle ambient sheet flashes washing evenly across all 4 channels (DMX 35–50) with broad spatial dispersion (\(\sigma > 0.35\)) and long acoustic propagation delays.
- **CLI Command:**
  ```bash
  storm-sim --intensity 0.25 --min-dist 3.0 --max-dist 15.0 --rate 4.0 --rain 0.20
  ```
- **Profile Parameters:**
  - `intensity`: `0.25`
  - `min_dist`: `3.0` miles (strikes never occur close to the observer)
  - `max_dist`: `15.0` miles
  - `rate`: `4.0` strikes/min (one lazy flash every ~15 seconds)
  - `rain`: `0.20` (light patter)
  - **Acoustic / Optical Characteristics:** Severe atmospheric low-pass filtering (\(f_c \approx 130 - 300\text{ Hz}\)) attenuates all high frequencies into warm sub-bass rumbles; acoustic transit delays span 14 to 70 seconds.

### 3. Severe Thunderstorm
*Violent, relentless convective squall line with deafening overhead claps, torrential rain, and rapid-fire multi-stroke strobing.*
- **Aesthetic:** Blinding multi-stroke lightning barrages occurring every 1–2 seconds, instantaneous unattenuated acoustic shockwaves (\(<0.25\text{ s}\) delay, \(f_c > 14\text{ kHz}\)), and dense hydrometeor optical extinction from torrential rainfall.
- **CLI Command:**
  ```bash
  storm-sim --intensity 0.95 --min-dist 0.05 --max-dist 3.5 --rate 36.0 --rain 0.95
  ```
- **Profile Parameters:**
  - `intensity`: `0.95`
  - `min_dist`: `0.05` miles (\(\approx 260\text{ ft}\), immediate overhead lightning)
  - `max_dist`: `3.5` miles (tight squall core)
  - `rate`: `36.0` strikes/min (intense barrage)
  - `rain`: `0.95` (torrential downpour)
  - **Acoustic / Optical Characteristics:** Up to 5 violent secondary return strokes per flash (`MAX_EXTRA_STROKES_AT_PEAK = 5`) causing rapid optical strobing; heavy rainfall extinction (\(\alpha_{\text{ext}} \approx 0.08/\text{mi}\)); raw full-frequency treble crackle.

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

For Freesound.org catalog IDs, acoustic requirements, and asset normalization guidelines, see [SFX_GUIDE.md](SFX_GUIDE.md).

---

## Audio Asset Attributions & Acknowledgments

The following Creative Commons Attribution 4.0 recordings from Freesound.org provide ground truth acoustic calibration and references:

- **Explosion Outdoors (Medium)** by **EvanBoyerman** -- <https://freesound.org/s/753843/> -- License: Attribution 4.0
- **Dry Thunder3.wav** by **juskiddink** -- <https://freesound.org/s/101948/> -- License: Attribution 4.0

---

## Running Tests

To run the test suite:
```bash
pytest
```
