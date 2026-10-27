# GEMINI.md: Agent Guidelines for Storm-Simulator

Instructions, architectural guidelines, and behavioral expectations for AI agents modifying, debugging, or extending the Storm-Simulator codebase.

---

## 1. Project Mission & Core Philosophy

**Storm-Simulator** is a production-grade, physics-accurate E1.31/sACN lighting and spatial audio thunderstorm simulator. It is designed to drive physical theatrical AC LED luminaires, DMX dimmer racks, and spatial audio sound systems with maximum real-world believability.

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

## 2. Codebase Architecture

```text
src/storm_sim/
├── constants.py    # Single source of truth for physical, optical, acoustic, and network defaults
├── models.py       # Data models: StormState, StrikeEvent, StrokePulse, channel map & address parsers
├── physics.py      # PhysicsEngine: Beer-Lambert optics, nonlinear Beta distance, atmospheric LPF
├── lighting.py     # E131LightingEngine: sACN transmitter, channel routing, and passthrough overrides
├── audio.py        # AudioEngine: Low-latency sounddevice mixer, cached SOS Butterworth filters
├── synthesis.py    # ThunderSynthesizer: Procedural acoustic thunderclaps, rain loop synthesis, CLI
├── osc_control.py  # OSCController: AsyncIO UDP OSC receiver and live parameter dispatcher
├── engine.py       # StormCoordinator: Top-level async lifecycle manager
├── cli.py          # Command-line entry point (storm-sim)
└── ui.py           # Tkinter desktop hardware visualizer and interactive test bench
```

---

## 3. Mandatory Behavioral Rules for Agents

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

## 4. Useful Development Commands

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
