# GEMINI.md: Architecture & Agent Guidelines for Storm-Simulator

Comprehensive repository structure, architectural patterns, concurrency model, and behavioral guidelines for AI agents modifying, debugging, or extending the Storm-Simulator codebase.

---

## 1. Project Mission & Core Philosophy

**Storm-Simulator** is a production-grade, physics-accurate E1.31/sACN lighting and spatial audio thunderstorm simulator. It drives physical theatrical AC LED luminaires, DMX dimmer racks, and spatial audio sound systems with maximum real-world believability.

### Primary Directives:
1. **Grounded in Physical Science & Empirical Truth:**
   - All physical models—including optical radiative transfer, Beer-Lambert hydrometeor extinction, acoustic speed-of-sound delays, line-source cylindrical wave spreading, tortuous channel frequency resonance, and Friedlander blast fronts—are derived strictly from empirical ground truth and peer-reviewed atmospheric physics literature.
   - **Never invent or hallucinate physical formulas.** Always verify against and reference [`MODEL_CITATIONS.md`](MODEL_CITATIONS.md).
2. **Real-World Electrical & Optical Hardware Physics:**
   - Fixtures in theatrical and architectural installations are predominantly AC LED fixtures controlled via 60 Hz phase-cut dimmers (TRIAC/reverse-phase) or solid-state relays.
   - Always honor AC mains dynamics: minimum stroke ON-time of 4 full AC cycles ($1/15\text{ s} \approx 66.7\text{ ms}$) to overcome power supply charging and LED diode forward voltage ($V_f$), followed by 3–6 AC cycle inter-stroke gaps ($50–100\text{ ms}$) for zero-crossing line commutation.
3. **Acoustic Realism & Sub-Bass Foundation:**
   - Cloud-to-ground lightning releases $>90\%$ of its acoustic energy below $100\text{ Hz}$ ($20–82\text{ Hz}$). Do not strip or roll off the infrasonic sub-bass foundation for full-range PA systems.
   - For compact desktop/bookshelf monitors lacking subwoofers, maintain the `--small-speakers` startup mode that elevates sub-bass to $48–140\text{ Hz}$ with soft-saturation harmonic generation.

---

## 2. Repository Structure

```text
storm-simulator/
├── pyproject.toml              # PEP-621 package build configuration & dependencies
├── README.md                   # User guide, OSC protocol spec, and CLI documentation
├── MODEL_CITATIONS.md          # Scientific literature citations & mathematical derivations
├── SFX_GUIDE.md                # Acoustic sound design & Freesound ground truth catalog
├── GEMINI.md                   # Agent guidelines, architecture specification, and rules
├── assets/                     # Soundbank audio assets (44.1 kHz, 16/24-bit stereo WAV)
│   ├── close/                  # Tier 1 (<1.2 mi) explosive Friedlander shock fronts
│   │   ├── synth_close_01.wav
│   │   └── synth_close_02.wav
│   ├── mid/                    # Tier 2 (1.2 - 3.2 mi) rolling tortuous claps
│   │   ├── synth_mid_01.wav
│   │   └── synth_mid_02.wav
│   ├── far/                    # Tier 3 (>3.2 mi) low-frequency infrasonic rumbles
│   │   ├── synth_far_01.wav
│   │   └── synth_far_02.wav
│   ├── rain_loop.wav           # Seamless stereo looping rain bed
│   ├── dry-thunder3.wav        # Ground truth recording (juskiddink, CC BY 4.0)
│   └── explosion-outdoors-medium.wav # Ground truth blast wave (EvanBoyerman, CC BY 4.0)
├── src/
│   └── storm_sim/              # Main Python package source code
│       ├── __init__.py         # Package exports (StormState, PhysicsEngine, StormCoordinator)
│       ├── constants.py        # Single Source of Truth (SSOT) for all physics & defaults
│       ├── models.py           # Dataclasses (StormState, StrikeEvent) & string parsers
│       ├── physics.py          # Pure mathematical models (optics, acoustics, Beta distance)
│       ├── lighting.py         # Real-time E1.31/sACN transmitter & passthrough blender
│       ├── audio.py            # Real-time low-latency PortAudio mixer & dynamic SOS filters
│       ├── synthesis.py        # Offline procedural thunder & rain synthesis DSP pipeline
│       ├── osc_control.py      # AsyncIO UDP OSC receiver & live parameter dispatcher
│       ├── engine.py           # StormCoordinator: Top-level async event conductor
│       ├── cli.py              # Argparse CLI entry point (`storm-sim`)
│       └── ui.py               # Tkinter desktop hardware visualizer & test bench
└── tests/                      # Pytest automated test suite
    ├── test_audio.py           # AudioEngine mixer, rain headroom, and voice tests
    ├── test_cli.py             # CLI argument parsing and default validations
    ├── test_lighting.py        # sACN output, passthrough overrides, and channel grouping
    ├── test_models.py          # Dataclass serialization, channel map & address parsers
    ├── test_osc.py             # OSC message dispatching and parameter manipulation
    ├── test_physics.py         # Optical Beer-Lambert, acoustic delay, and distance skew
    ├── test_synthesis.py       # DSP procedural synthesis and WAV export tests
    └── test_ui.py              # Tkinter UI widget interaction and override decoupling
```

---

## 3. Subsystem Architecture & Responsibilities

The codebase strictly enforces **Separation of Concerns (SoC)** across independent subsystems:

```
                      +-------------------+
                      |   CLI / OSC / UI  |
                      +---------+---------+
                                |  (Updates StormState)
                                v
                      +-------------------+
                      |  StormCoordinator | <---+
                      +---------+---------+     | (Polls state / Scheduler)
                                |               |
             +------------------+------------------+
             | Generates deterministic StrikeEvent |
             v                                     v
   +-------------------+                 +-------------------+
   |   PhysicsEngine   |                 |   StormState      |
   +-------------------+                 +-------------------+
             | (StrikeEvent)
             +---------------------+
             |                     | (Acoustic Travel Delay)
             v                     v
   +-------------------+ +-------------------+
   | E131LightingEngine| |    AudioEngine    |
   +---------+---------+ +---------+---------+
             |                     |
     (E1.31 UDP Packets)   (PortAudio Callback)
             v                     v
     DMX / sACN Network     Stereo Speakers / PA
```

### 1. `constants.py`: Single Source of Truth (SSOT)
- Contains all physical constants, optical calibration factors, acoustic parameters, network defaults, and timing constraints.
- **Rule:** Never hardcode magic numbers inside engine or math routines. Always declare and document them with descriptive names and units in `constants.py`.

### 2. `models.py`: Data Contracts & Parsers
- `StrokePulse`: Represents a single physical return stroke with duration, ON-time plateau, and peak amplitude.
- `StrikeEvent`: Complete immutable physical plan for a deterministic lightning strike flash and its delayed acoustic arrival. Contains precomputed spatial profiles, travel delays, LPF cutoffs, and pan coordinates.
- `StormState`: Mutable runtime simulation state shared across the coordinator, lighting loop, audio mixer, UI, and OSC server.
- `parse_channel_map()`: Robust parser supporting:
  - 1:1 channels (`0:1, 1:2`)
  - Inclusive ranges (`3:88-90` or `3:88..90`)
  - Multi-channel fixture grouping (mapping multiple DMX destination channels to a single simulation index)
  - 0-based (`0..N-1`) and 1-based (`1..N`) indexing
- `parse_address_port()`: Parses network socket notation (`address:port`, `:port`, `port`, `[::1]:port`).

### 3. `physics.py`: Pure Functional Mathematics
- Static, pure mathematical physics engine (`@classmethod generate_strike`). Has **no network, audio, or UI dependencies**.
- Responsibilities:
  - **Distance Sampling:** Intensity-skewed asymmetric Beta distribution with nonlinear power-law compression ($u_{\text{norm}} = u^{\lambda(s)}$) clustering strikes closer as storm severity increases.
  - **Optical Attenuation:** Extended line-source geometric falloff coupled with Bouguer-Lambert-Beer atmospheric extinction and rain scattering.
  - **Spatial Sigma:** Distance-scaled Gaussian flash broadening across the normalized coordinate span $[0.0, 1.0]$.
  - **Temporal Stroke Sequence:** Enforces AC line minimum ON-times and inter-stroke zero-crossing commutation gaps.
  - **Acoustic Wave Delay & Attenuation:** Line-source cylindrical wave spreading ($-11\text{ dB/decade}$) and atmospheric molecular relaxation low-pass filtering.

### 4. `lighting.py`: Real-Time sACN Transmitter & Passthrough Blender
- Runs a dedicated rendering thread at 44 FPS (`DEFAULT_FPS`).
- **Optimization:** Precomputes Gaussian profiles in `trigger_flash()` ahead of time, ensuring the 44 FPS hot rendering loop performs zero `np.exp()` calls.
- **sACN Passthrough:** Receives incoming desk universes via `sacn.sACNreceiver`. If lightning is active, only overrides channels with nonzero lightning output (`> 0`). When lightning fades to 0, desk control restores seamlessly.
- **Channel Routing:** Dispatches DMX values to mapped offsets across one or multiple universes.

### 5. `audio.py`: Low-Latency Real-Time Audio Mixer
- Drives audio output via `sounddevice.OutputStream` with a low-latency 1024-sample callback block size at 44.1 kHz.
- **Polyphonic Mixer:** Mixes continuous looping rain beds and multiple concurrent thunderclap voices with constant-power stereo panning.
- **Dynamic DSP Filtering:** Implements distance-dependent atmospheric low-pass filtering using cached Second-Order Sections (SOS) Butterworth filter coefficients.
- **AOT Fallback:** If soundbank files are missing, automatically generates procedural acoustic models at initialization.

### 6. `synthesis.py`: Procedural Acoustic Synthesis DSP
- Offline/CLI audio generator producing calibrated WAV assets.
- **Four-Layer Synthesis Model:**
  1. Infrasonic plasma shockwave core ($20–82\text{ Hz}$).
  2. Low-mid tortuous channel resonance bursts ($55–185\text{ Hz}$).
  3. Sharp dry shockwave crack with EvanBoyerman outdoor Friedlander blast attack ($<1\text{ mi}$).
  4. Specular facade reflection taps with Gaussian smearing and lateral stereo canyon reverberation.

### 7. `osc_control.py`: AsyncIO OSC Server
- Async UDP server listening on `DEFAULT_OSC_PORT` (`5005`).
- Dispatches `/storm/*` address patterns to modify `StormState` parameters, trigger manual strikes, and execute timed intensity ramps.

### 8. `engine.py`: StormCoordinator (Event Orchestrator)
- Top-level lifecycle manager binding all subsystems together.
- Manages the asynchronous strike scheduler, dynamic intensity ramps, and coordinated dispatch of `StrikeEvent`s to lighting (immediate) and audio (speed-of-sound delayed).

### 9. `ui.py`: Desktop Visualizer & Control Bench
- Built with Tkinter / ttk.
- Visualizes real-time DMX channel output levels across the horizontal LED strip, displays wavefront transit queues, and provides interactive control sliders.

---

## 4. Concurrency & Threading Architecture

Storm-Simulator runs a multi-threaded, asynchronous architecture:

1. **Main AsyncIO Thread:**
   - Runs `StormCoordinator` lifecycle tasks.
   - Runs `OSCController` async UDP datagram receiver.
   - Evaluates the strike scheduler and launches background tasks.
2. **Lighting Engine Thread:**
   - Managed by `E131LightingEngine`.
   - Runs a 44 FPS periodic timer loop rendering frames and broadcasting sACN UDP packets.
   - Synchronizes passthrough buffers with incoming desk data using `threading.Lock`.
3. **Audio DSP Thread:**
   - Managed by PortAudio / `sounddevice`.
   - Runs high-priority 1024-sample block callbacks at 44.1 kHz.
   - Non-blocking lock-free active voice mixing.
4. **UI GUI Thread (Optional):**
   - Runs Tkinter's `mainloop()` when `--ui` is specified.
   - Polls `StormState` and lighting engine meters at 30 FPS without blocking the async coordinator.

---

## 5. Mandatory Coding & Behavioral Rules for Agents

### Rule 1: Empirical Ground Truth Over Heuristics
- When adjusting lightning flashes or thunder acoustics, do not guess arbitrary exponential curves or filter cutoffs.
- Consult [`MODEL_CITATIONS.md`](MODEL_CITATIONS.md) and calibrated reference assets in [`assets/`](assets/):
  - *Dry Thunder3.wav* by juskiddink (CC BY 4.0): dry tortuous lightning channel acoustics.
  - *Explosion Outdoors (Medium)* by EvanBoyerman (CC BY 4.0): positive Friedlander shock front attack ($<1\text{ mi}$).

### Rule 2: Strict Privacy, Security & Git Hygiene
- **Never commit production or internal network IPs** (e.g. specific node IPs like `192.168.1.196`). Always use generalized documentation examples (`192.168.1.50`, `0.0.0.0:5568`).
- **Never commit personal or local filesystem paths** (e.g. `file:///Users/...`). Always use relative markdown links (`MODEL_CITATIONS.md`).
- **Do not commit temporary test files** or raw audio scratch files to the repository root. Keep generated soundbanks in `assets/` or temporary test directories.

### Rule 3: Lighting Passthrough Integrity
- When sACN passthrough mode is enabled (`--passthrough <addr:port>`), incoming desk channels must pass through 1:1 unaltered.
- Only override channels with nonzero lightning output (`> 0`). When lightning fades to 0, control must revert immediately to the incoming desk frame.
- Channel remapping (`--channel-map`) only dictates where simulator channels are sent; it must **never** shift, filter, or alter passthrough desk channels.

### Rule 4: Channel Map Versatility
- Channel mapping must support:
  1. Single 1:1 channels (`0:1, 1:2`).
  2. Inclusive channel ranges (`3:88-90` or `3:88..90`).
  3. Multi-channel fixture grouping (mapping multiple DMX channels to a single simulation channel so grouped lights ignite simultaneously).
  4. Both 0-based (`0..N-1`) and 1-based (`1..N`) simulator channel indexing.

### Rule 5: Fast, Snappy Optical Envelopes
- Flashes must feel explosive and dramatic:
  - Full 255 DMX white saturation for close and mid-distance strikes ($d \le 1.2\text{ mi}$).
  - Diffuse cloud forward scattering floor (`DIFFUSE_SCATTERING_FLOOR = 0.20`) ensuring all fixtures across the rig illuminate together.
  - Snappy decay ($k = 4.2$) so pulses strike aggressively and decay within $150–200\text{ ms}$ before secondary return restrikes ignite.

### Rule 6: Test Suite Discipline
- Every pull request or commit must pass 100% of tests:
  ```bash
  pytest
  ```
- If adding new features or adjusting formulas, add corresponding regression test coverage in [`tests/`](tests/).

---

## 6. Useful Development Commands

```bash
# Run full test suite:
pytest -v

# Run targeted subsystem tests:
pytest tests/test_lighting.py tests/test_physics.py -v
pytest tests/test_audio.py tests/test_synthesis.py -v
pytest tests/test_models.py tests/test_cli.py tests/test_ui.py -v

# Run simulator locally in visualizer UI mode:
storm-sim --ui

# Test sACN output with fixture grouping:
storm-sim --pixels 5 --e131-host 192.168.1.50 --channel-map "0:45,1:46,2:47,3:88-90,4:93-95"

# Synthesize standalone procedural soundbank:
storm-synth --out-dir ./assets --small-speakers
```
