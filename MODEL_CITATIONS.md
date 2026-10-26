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
- $\text{offset} = 1.40$ is the close-range normalization offset (`OPTICAL_NORM_OFFSET`),
- $\alpha_{\text{ext}} = \alpha_0 + \alpha_{\text{rain}} \cdot R$ is the hydrometeor-dependent extinction coefficient (`BASE_OPTICAL_EXTINCTION`, `RAIN_OPTICAL_EXTINCTION_SCALE`),
- Clamped to a visibility floor $I_{\text{min}} = 0.18$ (`MIN_PEAK_BRIGHTNESS`) to preserve distant horizon sheet lightning.

---

## 3. Acoustic Wave Propagation & Atmospheric Absorption

### Speed of Sound & Atmospheric Low-Pass Filtering
- **Bass, Henry E., Sutherland, Louis C., Zuckerwar, Allan J., Blackstock, David T., & Hester, D. Michael (1995).** *Atmospheric absorption of sound: Further developments*. [The Journal of the Acoustical Society of America, 97(1), 680–683](https://doi.org/10.1121/1.412989).
  - *Contribution:* Standard ISO 9613-1 atmospheric sound absorption model demonstrating high-frequency molecular relaxation absorption across distance.
- **Few, Arthur A. (1969).** *Power spectrum of thunder*. [Journal of Geophysical Research, 74(28), 6926–6934](https://doi.org/10.1029/JC074i028p06926).
  - *Contribution:* Acoustic power spectral density of thunderclaps, showing sub-bass dominance (<200 Hz) at distance due to atmospheric filtering.
