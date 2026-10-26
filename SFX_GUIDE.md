# Sound Effects (SFX) Asset Curation Guide

Guide for sourcing, curating, and ingesting high-fidelity acoustic recordings of thunderclaps and rain beds for Storm-Sim.

---

## Audio Design Rule: "Dry" Thunder Only

> [!IMPORTANT]
> **Audio Design Rule:** ONLY use "dry" thunder recordings (recorded before rainfall begins or cleanly isolated in post-production). If thunder samples have baked-in rain noise, the engine's real-time low-pass filter and stereo panner will cause unnatural swelling and abrupt cuts of rain ambience during thunderclaps.

---

## Recommended Freesound.org Catalog IDs

### Tier 1: Close / Overhead Strikes (< 1.2 miles)
- **Acoustics:** Instantaneous high-frequency 'snap/crack', zero pre-rumble, wide bandwidth.
- **ID 670692:** *"Thunder / Lightning - I - Without Rain"* by GregorQuendel
  - Pristine transients recorded with Sound Devices 702 + Sennheiser MKH 406 RF condenser microphones.
- **ID 536903:** *"thunder dry crack rumble.wav"* by cognito perceptu
  - Approaching storm front, sharp crack, 10s tight decay (CC0).
- **ID 446753:** *"Heavy Thunder Strike - no Rain - QUADRO.wav"* by BlueDelta
  - 4-channel uncompressed dry afternoon bolt.

### Tier 2: Mid-Range Strikes (1.2 to 3.2 miles)
- **Acoustics:** Attenuated highs (>6 kHz absorbed), body echoes, rolling tail.
- **IDs 469612 & 521096:** *"Thunder Clap And Rumble #2 & #3"* by Kinoton
  - 48kHz/24-bit matched studio isolation from Ambiences Pack 20130.
- **ID 194364:** *"Thunder Clap OWB KY 441x16.wav"* by Dave Welsh
  - Sony PCM-D50 / ECM-MS957 mid-side stereo capture.

### Tier 3: Distant / Horizon Rumbles (> 3.2 miles)
- **Acoustics:** Heavy air absorption, low-frequency pressure wave (40-300 Hz dominant).
- **ID 24952:** *"thunder-long-distance.wav"* by Erdie
  - Classic clean horizon roll, zero close transient artifacts.
- **Pack 43490:** *"Distant_Thunder_Denoised_01"* by loganzsound
  - Pre-denoised sub-bass rumble (CC0).

### Background Rain Bed
- **ID 624645:** *"Heavy_Rain_Loop.wav"* by Rubaoliva
  - Seamlessly looping stereo rain bed without metallic gutter resonances.

---

## Asset Ingestion Checklist

1. **Trim leading silence:**
   - Strip all audio before the first sample > -45 dBFS so the calculated speed-of-sound delay (\(\Delta t = 4.69 \cdot d\)) aligns precisely with the visual flash.
2. **Peak normalize:**
   - Normalize all thunder files to -1.0 dBFS (or equal LUFS) so distance attenuation curves operate from a calibrated baseline.
3. **Sum to mono:**
   - Convert thunder samples to mono so the engine's constant-power panner (\(L = \cos\theta, R = \sin\theta\)) can dynamically place the acoustic origin at the exact LED epicenter. Keep the background rain bed in stereo.
4. **File Placement:**
   - Place files into the corresponding asset tier directories:
     ```text
     assets/
     ├── close/         # Tier 1 WAV files (< 1.2 miles)
     ├── mid/           # Tier 2 WAV files (1.2 - 3.2 miles)
     ├── far/           # Tier 3 WAV files (> 3.2 miles)
     └── rain_loop.wav  # Seamless stereo rain loop
     ```
