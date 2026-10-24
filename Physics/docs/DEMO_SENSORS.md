# Demo optical / electromagnetic models (SI)

This implementation is a deterministic system-level estimate. JSBSim supplies
the two aircraft states; `physim/demo_sensors.py` calculates sensor observations.
There is no new dependency on a commercial radar package or waveform engine.

## Monostatic radar budget

```
lambda = c / f
G = 4 pi eta A cos(az) cos(el) / lambda^2
Pr = Pt G^2 lambda^2 sigma pattern^2 / ((4 pi)^3 R^4 L)
N = k T B F
SNR = Pr / N
delta_R = c / (2 B)
beamwidth = 0.886 lambda / sqrt(4 A / pi)
pattern = exp(-4 ln(2) (pointing_error / beamwidth)^2)
```

Gain, efficiency, noise factor, system loss and SNR are linear dimensionless
ratios. Power is W; temperature K; bandwidth/frequency Hz; area/RCS m^2;
distance/wavelength m; angles rad. At half the full one-way beamwidth, the
one-way power pattern is 0.5 and the two-way power multiplier is 0.25.

Defaults: Pt=3000 W, A=0.5 m^2, eta=0.6, sigma=3 m^2, B=2e7 Hz,
T=290 K, F=3, L=4, detection threshold SNR=20 (linear). These are explicitly
chosen demo parameters, not measured aircraft or radar specifications.
The RCS is constant across angle and frequency. Receiver noise is a pre-detection
thermal-bandwidth estimate; no matched filtering, integration gain, waveform,
clutter, CFAR, detection probability or false-alarm calibration is modeled.
The far-field R^-4 equation is an approximation and is not accurate at close
encounters. Terrain occlusion, weather, gaseous absorption and multipath are
not implemented. Millimetre-wave results therefore must not be presented as
validated operational detection ranges.

References: [point-target radar equation](https://www.mathworks.com/help/radar/ref/radareqsnr.html),
[electronic array scanning](https://www.mathworks.com/help/phased/ug/scan-radar-using-a-uniform-rectangular-array.html).
The demo uses instantaneous bandwidth noise rather than that reference's
rectangular-pulse matched-filter SNR expression.

## Electronic scan and observations

The ideal array scans azimuth +/-pi/3 rad and elevation +/-0.26 rad on a raster.
Beam spacing is at most 0.7 beamwidth; dwell is 0.01 s. Scan direction depends
only on simulation time and array parameters, not hidden target coordinates.
At higher frequency, the same aperture has greater gain but a narrower beam and
more search cells, so the calculated raster revisit interval increases.

A valid EO observation may cue the beam to the observed bearing. This is marked
`EO CUE` in the UI. Both transmit and receive use the same ideal pointing pattern.
Radar tracks last at most 2 s after the last threshold crossing. Coasting reports
the last measured range/bearing/velocity rather than updated hidden truth; the
UI labels it COAST. Frequency changes discard previous tracks.

Range rate uses the relative SI velocity projected onto the line of sight;
positive means opening. Doppler is -2 range_rate / lambda. A 20000 m display
scale is a plotting choice, not a sensor range cap. UI echo power/SNR are the
deterministic modeled values at the current beam direction, not sampled noise.
The opponent-track warning is scenario feedback, not a simulated passive RWR.

## Visible electro-optical channel

Unity renders a separate forward visible-light camera, excluding its own plane
and the cockpit UI. The independent EO observation checks a +/-0.18 rad search
window in both body axes and whether a 10 m target dimension exceeds three ideal
diffraction resolution cells. lambda=5.5e-7 m, aperture=0.08 m,
angular_resolution=1.22 lambda / aperture. No thermal image, radiometry, contrast,
cloud masking or atmospheric optical extinction is claimed.

The backend owns detection. UI target marks and radar blips use observations,
and the main world remains an ordinary visible scene. Fuel mass/flow come from
JSBSim; endurance is fuel mass divided by current flow, not a planned mission
range. The airframe diagram displays measured pitch/bank, not simulated damage.
