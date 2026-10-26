# Scientific Model References & Citations

Theoretical foundations, mathematical formulations, and academic literature citations for the optical, meteorological, and acoustic models implemented in Storm-Sim.

---

## 1. Optical Attenuation & Atmospheric Hydrometeor Scattering

### Bouguer-Lambert-Beer Law
Models exponential absorption and extinction of optical radiation through an absorbing medium:

$$\Phi(d) = \Phi_0 \cdot e^{-\alpha_{\text{ext}} d}$$

- **Bouguer, Pierre (1729).** *Essai d'optique sur la gradation de la lumière* [*Optical Essay on the Gradation of Light*]. Claude Jombert, Paris.
  - *Contribution:* First formulation of light attenuation through a medium proportional to path length.
- **Lambert, Johann Heinrich (1760).** *Photometria, sive de mensura et gradibus luminis, colorum et umbrae* [*Photometry, or On the Measure and Gradations of Light, Colors, and Shadow*]. Eberhard Klett, Augsburg.
  - *Contribution:* Formalized the mathematical law of light absorption with distance.
- **Beer, August (1852).** *Bestimmung der Absorption des rothen Lichts in farbigen Flüssigkeiten* [*Determination of the Absorption of Red Light in Colored Liquids*]. [Annalen der Physik und Chemie, 86(5), 78–88](https://doi.org/10.1002/andp.18521620505).
  - *Contribution:* Extended the absorption law to account for solute concentration and particle scattering density.

### Atmospheric Extinction & Rainfall Scattering
- **Atlas, David (1953).** *Optical extinction by rainfall*. [Journal of Meteorology, 10(6), 486–488](https://doi.org/10.1175/1520-0469(1953)010%3C0486:OEBR%3E2.0.CO;2).
  - *Contribution:* Derived empirical relationships between optical extinction coefficients ($\alpha_{\text{ext}}$) and rainfall precipitation rates ($R$).
- **Koschmieder, Harald (1924).** *Theorie der horizontalen Sichtweite* [*Theory of Horizontal Visibility*]. Beiträge zur Physik der freien Atmosphäre, 12, 33–53, 171–181.
  - *Contribution:* Established Koschmieder's law relating atmospheric contrast extinction to visual range.
- **McCartney, Earl J. (1976).** *Optics of the Atmosphere: Scattering by Molecules and Particles*. John Wiley & Sons, New York.
  - *Contribution:* Comprehensive treatment of Rayleigh and Mie scattering through atmospheric fog, rain, and aerosols.

---

## 2. Lightning Radiative Transfer & Multi-Stroke Channel Physics

### Lightning Optical Radiative Transfer
- **Uman, Martin A. (1987).** *The Lightning Discharge*. Academic Press, San Diego (reprinted by Dover Publications).
  - *Contribution:* Standard treatise on lightning return stroke energetics, current waveforms, stepped leaders, and multi-stroke statistics.
- **Thomason, Larry W., & Krider, E. Philip (1982).** *The effects of clouds on the light produced by lightning*. [Journal of the Atmospheric Sciences, 39(9), 2051–2065](https://doi.org/10.1175/1520-0469(1982)039%3C2051:TEOCOT%3E2.0.CO;2).
  - *Contribution:* Radiative transfer modeling of lightning optical pulses scattering through dense thunderclouds, explaining the spatial broadening of distant sheet flashes and diffuse cloud base illumination.
- **Krider, E. Philip, & Guo, Chuan (1983).** *The peak radiant power and energy in lightning return strokes*. [Journal of Geophysical Research: Atmospheres, 88(C13), 8623–8634](https://doi.org/10.1029/JC088iC13p08623).
  - *Contribution:* Experimental measurements of return stroke rise times, peak optical power, and multi-stroke amplitude decay envelopes.

### Extended Channel & Cloud Scattering Optical Formulation
For an idealized point source in vacuum, geometric irradiance attenuates strictly as the inverse-square $1/d^2$. However, real lightning channels are several kilometers long, and multiple forward-scattering through cloud decks diffuses the luminous pulse across large areas (Thomason & Krider 1982). Consequently, the effective geometric attenuation behaves as $1/(d^p + d_{\text{min}}^p)$ with $p \approx 1.10$, coupled with Bouguer-Lambert-Beer exponential extinction:

$$I(d) = \min\left(1.0, \frac{(d_{\text{min}}^p + \text{offset}) \cdot e^{-\alpha_{\text{ext}} d}}{d^p + d_{\text{min}}^p}\right)$$

where:
- $p = 1.10$ is the diffuse scattering line-source exponent (`OPTICAL_DISTANCE_EXPONENT`),
- $d_{\text{min}} = 0.45\text{ mi}$ is the overhead softening distance (`OPTICAL_SOFTENING_DIST_MILES`),
- $\text{offset} = 0.65$ is the close-range normalization offset (`OPTICAL_NORM_OFFSET`) calibrated so overhead strikes ($\le 0.5\text{ mi}$) reach full 3kW tungsten saturation (DMX 255) while mid-distance strikes (1–2 mi) scale through 2kW to 1kW equivalents,
- $\alpha_{\text{ext}} = \alpha_0 + \alpha_{\text{rain}} \cdot R$ is the hydrometeor-dependent extinction coefficient (`BASE_OPTICAL_EXTINCTION`, `RAIN_OPTICAL_EXTINCTION_SCALE`),
- Clamped to a visibility floor $I_{\text{min}} = 0.08$ (`MIN_PEAK_BRIGHTNESS`; ~240W tungsten equivalent) sitting comfortably above AC LED phase-dimmer low-end drop-out thresholds.

### Temporal Optical Envelope & AC LED Electrical Dynamics
While return stroke channel breakdown occurs in microseconds, channel continuing currents (30–50% of cloud-to-ground discharges; Uman 1987) and multiple cloud scattering (Thomason & Krider 1982) stretch visible illumination across 50–250 ms.

#### 60 Hz AC LED Driver Physics & Zero-Crossing Commutation
Real-world theatrical and architectural installations predominantly drive AC LED luminaires via phase-cut (forward/reverse phase) dimmers or solid-state relays:
1. **Capacitor Charge & Forward Conduction Delay:** AC LED drivers contain bridge rectifiers and internal filter/reservoir capacitors. When an instantaneous DMX firing pulse arrives, the driver requires **$2\text{ full }60\text{ Hz AC cycles}$ ($33.3\text{ ms}$)** for the DC bus to charge and cross the LED diode array forward conduction threshold ($V_f$) before visible light is produced.
2. **Sustained Emission Plateau:** To deliver meaningful illumination after the 2-cycle turn-on lag, the control signal must sustain full output for an additional **$2\text{ full AC cycles}$ ($33.3\text{ ms}$)**. Consequently, the minimum fixture on-time is derived from fundamental AC line physics:
   $$t_{\text{on\_min}} = \frac{4\text{ cycles}}{60\text{ Hz}} = \frac{1}{15}\text{ s} \approx 66.67\text{ ms}\quad\text{(`MIN_STROKE_ON_TIME_SEC`)}$$
3. **Zero-Crossing Commutation & Multi-Stroke Inter-Stroke Clearance:** Standard TRIAC and thyristor phase dimmers cannot commutate off mid-cycle; current only ceases when the line voltage passes through the AC **zero crossing** ($T_{\text{half}} = 1/120\text{ s} \approx 8.33\text{ ms}$). Driver smoothing capacitors sustain light output across an additional $1–2$ half-cycles. To prevent consecutive multi-stroke pulses from blurring into a single continuous smear, the inter-stroke gap is calibrated to **$3\text{ to }6\text{ AC cycles}$ ($50–100\text{ ms}$; `INTER_STROKE_GAP_RANGE_SEC`)**, guaranteeing complete optical extinction across zero crossings prior to subsequent stroke restrikes.

The temporal envelope enforces this physical progression:
$$A(t) = \begin{cases} A_{\text{peak}} & \text{if } 0 \le t \le t_{\text{on}} \\ A_{\text{peak}} \cdot \exp\left(-\frac{k (t - t_{\text{on}})}{t_{\text{dur}} - t_{\text{on}}}\right) & \text{if } t > t_{\text{on}} \end{cases}$$

where:
- $t_{\text{on}} \ge 1/15\text{ s} = 4 / 60\text{ s}$ (`MIN_STROKE_ON_TIME_SEC`),
- $k = 4.5$ (`STROKE_DECAY_TIME_CONSTANT`),
- $t_{\text{dur}}$ is total stroke duration (`PRIMARY_STROKE_DURATION_RANGE_SEC`, `SECONDARY_STROKE_DURATION_RANGE_SEC`).

---

## 3. Acoustic Wave Propagation & Thunder Mechanics

### Cylindrical Shockwave Generation & Sub-Bass Spectral Power
- **Few, Arthur A. (1969).** *Power spectrum of thunder*. [Journal of Geophysical Research, 74(28), 6926–6934](https://doi.org/10.1029/JC074i028p06926).
  - *Contribution:* Measured the acoustic power spectral density of thunder, demonstrating that the dominant acoustic energy is concentrated in the sub-bass ($25–80\text{ Hz}$) band caused by the cylindrical shockwave expansion of the superheated plasma channel.
- **Holmes, C. R., Brook, M., Krehbiel, P., & McCrory, R. (1971).** *On the power spectrum and mechanism of thunder*. [Journal of Geophysical Research, 76(9), 2106–2115](https://doi.org/10.1029/JC076i009p02106).
  - *Contribution:* Confirmed that natural cloud-to-ground thunderclaps exhibit peak acoustic power between $25\text{ Hz}$ and $60\text{ Hz}$, with over $85–95\%$ of total acoustic energy residing below $100\text{ Hz}$ and steep $-12\text{ to }-18\text{ dB/octave}$ roll-off above $200\text{ Hz}$.
- **Ribner, Herbert S., & Roy, Dipankar (1982).** *Acoustics of thunder: A quasilinear model for tortuous lightning*. [The Journal of the Acoustical Society of America, 72(6), 1911–1925](https://doi.org/10.1121/1.388621).
  - *Contribution:* Demonstrated that the sharp "clap" or "peal" of close thunder is the convolution of bipolar N-wave shock pulses with a tortuous (zig-zag) lightning channel geometry, producing rapid low-midrange ($50–260\text{ Hz}$) pressure bursts rather than high-frequency white noise hiss.
- **Bass, Henry E., Sutherland, Louis C., Zuckerwar, Allan J., Blackstock, David T., & Hester, D. Michael (1995).** *Atmospheric absorption of sound: Further developments*. [The Journal of the Acoustical Society of America, 97(1), 680–683](https://doi.org/10.1121/1.412989).
  - *Contribution:* Standard ISO 9613-1 atmospheric sound absorption model demonstrating high-frequency molecular relaxation absorption across distance.
- **Hornikx, Maarten, & Forssén, Jens (2009).** *The 2.5-dimensional equivalent sources method for directly exposed and shielded urban canyons*. [The Journal of the Acoustical Society of America, 125(2), 665–676](https://doi.org/10.1121/1.3050254).
  - *Contribution:* Models discrete specular reflections off building facades, edge diffraction of low-frequency sound around structures, and diffuse late reverberation tails in urban street canyons.

### Acoustic Propagation & Attenuation Formulation

#### 1. Cylindrical Line-Source Geometric Spreading
Point-source acoustic emitters follow spherical wave spreading:
$$\Delta L_{\text{spherical}} = -20 \log_{10}\left(\frac{d}{d_{\text{ref}}}\right)\quad\text{[dB]}$$

However, natural lightning discharges are extended linear columns traversing $3\text{ to }8\text{ km}$ vertically through the troposphere and horizontally across cloud bases. At operational observer distances ($0.15\text{ to }5\text{ miles}$), the wavefront behaves as an acoustic line source with cylindrical spreading loss:
$$\Delta L_{\text{cylindrical}} = -\gamma_{\text{cyl}} \log_{10}\left(\frac{\max(d, d_{\text{ref}})}{d_{\text{ref}}}\right)\quad\text{[dB]}$$

where:
- $\gamma_{\text{cyl}} = 11.0\text{ dB/decade}$ (`ACOUSTIC_CYLINDRICAL_SPREADING_FACTOR`),
- $d_{\text{ref}} = 0.25\text{ mi}$ (`ACOUSTIC_REF_DIST_MILES`).

This formulation prevents the steep, unrealistic volume drop-off at intermediate distances ($1–3\text{ miles}$) that plagues point-source spherical approximations.

#### 2. Four-Layer Acoustic Synthesis & Environmental Reflection Model
To deliver physical accuracy matching the measured power spectrum and outdoor structural acoustics:
1. **Infrasonic & Sub-Bass Shockwave Body ($25–85\text{ Hz}$):** 4th-order Butterworth bandpass filtered noise modulated with a sub-bass plasma expansion wave ($28–60\text{ Hz}$), delivering $>95\%$ of total power below $100\text{ Hz}$.
2. **Low-Mid Tortuous Channel Resonance ($55–185\text{ Hz}$):** Multi-burst acoustic packet arrivals modeling sound emitted from tortuous channel kinks at varying altitudes.
3. **Ribner & Roy (1982) Tortuous N-Wave Shock Cluster Clap ($45–260\text{ Hz}$):** Models the close thunderclap as a rapid staccato cluster of $1/f$-tilted low-frequency pressure bursts arriving from nearby crooked channel segments over the first $15–200\text{ ms}$, driven through nonlinear shockwave compression (`tanh`) and low-pass filtered below $270–340\text{ Hz}$ to completely eliminate synthetic high-pitched hiss.
4. **Specular Building Echoes & Diffuse Urban Canyon Reverberation:** Combines $5–7$ discrete specular reflection taps ($65\text{ ms} - 4.1\text{ s}$) with finite-facade Gaussian smearing ($10–22\text{ ms}$), delay-dependent low-pass wall absorption, a velvet-noise diffuse reverberation tail ($<110\text{ Hz}$), and real-time stereo lateral building reflections ($95–420\text{ ms}$) across opposite channels.
