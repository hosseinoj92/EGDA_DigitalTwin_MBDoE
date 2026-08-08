"""
Reusable 1H NMR forward model of the EGDA hydrolysis mixture at 80 MHz.

Refactored from EGDA_NMR_sim/sim_nmr(2).py.  What is preserved from there:

  * the 80.168 MHz field and the 1 ppm = 80.168 Hz conversion;
  * the aqueous-literature chemical-shift database (CARBON_BOUND_GROUPS) with
    the EGDA/EG symmetry -> singlets, EGMA desymmetrisation -> J-coupled
    1:2:1 triplet pair;
  * proton-count scaling of intensities;
  * the fast-exchange pooling of H2O / EGMA-OH / EG-OH / AcOH-COOH into one
    broad line at the population-weighted average shift;
  * the empirical temperature dependence of the water shift
    (delta = 5.051 - 0.0111 * T_C).

What is CHANGED relative to sim_nmr(2).py:

  * INPUT API: `simulate(concentrations, ...)` takes actual molar
    concentrations (Layer 1 names EGDA/EGMA/EG/AcOH/H2O).  The old
    assumed-conversion -> A->B->C speciation logic is NOT used here; inside
    the integrated virtual laboratory all compositions come from Layer 1.
  * The catalyst is H2SO4 (homogeneous); the original file mentioned
    Amberlyst 15 in places.  The spectral physics is catalyst-independent.
  * TEMPERATURES are separated: the water shift and lineshapes follow the
    NMR-CELL temperature (AcquisitionSettings.nmr_temperature_C), never the
    reactor temperature.  Post-sampling kinetics are handled in transfer.py
    at the transfer-line temperature.
  * Lines carry unit-AREA Lorentzians (area = protons x concentration x
    response), so quantification is area-based and linewidth-independent.
  * Two engines: "analytic" frequency-domain summation (fast, for Monte
    Carlo campaigns) and "fid" (complex time-domain FID -> T2* decay ->
    receiver noise -> phase/frequency error -> FFT), which is the honest
    model of the instrument.

PROVENANCE / CALIBRATION STATUS: every number in the databases below is an
AQUEOUS-LITERATURE or plainly ASSUMED simulation value inherited from
sim_nmr(2).py - none is a validated Bruker Fourier 80 parameter.  Fields
whose values must be refit against pure-component standards on the real
instrument are marked "CAL:" in comments.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import comb
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Species-name mapping: Layer 1 <-> the D/M/G/aa/w keys of sim_nmr(2).py.
# The single place where the two naming schemes meet.
# ---------------------------------------------------------------------------
LAYER1_TO_NMR = {"EGDA": "D", "EGMA": "M", "EG": "G", "AcOH": "aa", "H2O": "w"}
NMR_TO_LAYER1 = {v: k for k, v in LAYER1_TO_NMR.items()}

#: species quantified from carbon-bound resonances (exchangeables coalesce
#: with water and carry no species-specific signal at 80 MHz)
QUANTIFIED_SPECIES = ("EGDA", "EGMA", "EG", "AcOH")


def water_shift(temperature_C: float) -> float:
    """delta(H2O)/ppm ~ 5.051 - 0.0111*T(degC).  Empirical aqueous relation
    inherited from sim_nmr(2).py.  CAL: refit on the Fourier 80.
    T is the NMR-CELL temperature, not the reactor temperature."""
    return 5.051 - 0.0111 * float(temperature_C)


# Carbon-bound proton groups: (label, delta_ppm, n_coupling_partners,
# n_protons, layer1_species).  Aqueous literature shifts from sim_nmr(2).py.
# CAL: shifts and the EGMA 3J must be refit from pure-component standards.
CARBON_BOUND_GROUPS: List[Tuple[str, float, int, int, str]] = [
    ("EGDA O-CH2 (s)",     4.335, 0, 4, "EGDA"),
    ("EGDA CH3 (s)",       2.140, 0, 6, "EGDA"),
    ("EGMA CH2-OC(O) (t)", 4.245, 2, 2, "EGMA"),
    ("EGMA CH2-OH (t)",    3.780, 2, 2, "EGMA"),
    ("EGMA CH3 (s)",       2.125, 0, 3, "EGMA"),
    ("EG O-CH2 (s)",       3.660, 0, 4, "EG"),
    ("AcOH CH3 (s)",       2.080, 0, 3, "AcOH"),
]

# Exchangeable protons pooled into ONE fast-exchange line:
# (layer1_species, n_protons, intrinsic_shift_ppm; None -> water_shift(T_nmr))
EXCHANGEABLE: List[Tuple[str, int, Optional[float]]] = [
    ("H2O",  2, None),
    ("EGMA", 1, 5.00),
    ("EG",   2, 5.00),
    ("AcOH", 1, 11.40),
]


@dataclass(frozen=True)
class AcquisitionSettings:
    """Fourier-80 acquisition/processing settings (known to BOTH the truth
    instrument and the fitting side - they are commanded, not hidden)."""
    spectrometer_MHz: float = 80.168     # from sim_nmr(2).py
    nmr_temperature_C: float = 25.0      # NMR-CELL temperature (independent
                                         # of reactor/transfer temperatures)
    ppm_min: float = 0.0
    ppm_max: float = 12.0
    n_points: int = 4096                 # spectrum grid / complex FID points
    acquisition_time_s: float = 4.096    # FID mode only; dwell = at/n_points
    repetition_time_s: float = 15.0      # recycle time (flow/T1 model)
    n_scans: int = 1
    engine: str = "analytic"             # "analytic" | "fid"
    fwhm_sharp_hz: float = 1.5           # CAL: carbon-bound linewidth
    fwhm_broad_hz: float = 30.0          # CAL: exchange-pool linewidth
    j_hz: float = 4.7                    # CAL: EGMA vicinal 3J(H,H)
    # residual factor applied to the exchange-pool amplitude: 1.0 = no
    # suppression, 0.01 = 99% suppressed (imperfect residual water remains)
    water_suppression_factor: float = 1.0
    # phenomenological flow/relaxation response (Section: flow_response):
    flow_response_enabled: bool = False
    analytical_flow_mL_min: float = 0.5  # flow through the NMR cell
    premag_volume_mL: float = 0.4        # CAL: premagnetization volume

    @property
    def hz_per_ppm(self) -> float:
        return self.spectrometer_MHz

    def ppm_grid(self) -> np.ndarray:
        return np.linspace(self.ppm_min, self.ppm_max, self.n_points)


# ASSUMED T1 values, s.  Plausible order-of-magnitude for small molecules in
# H2O at low field.  CAL: must be measured (inversion recovery) per resonance
# on the Fourier 80 - these are simulation assumptions, NOT literature data.
DEFAULT_T1_S: Dict[str, float] = {
    "EGDA": 2.5, "EGMA": 2.8, "EG": 3.5, "AcOH": 4.5, "H2O": 3.0,
}


@dataclass(frozen=True)
class SpectralNuisance:
    """TRUE instrument imperfections (owned by the virtual instrument only).

    All values are SIMULATION ASSUMPTIONS chosen to be plausible for a 80 MHz
    benchtop instrument; none is a measured Fourier 80 property.  Each maps
    onto a quantity that will be calibrated from standards (CAL) once the
    real instrument is available.  With `enabled=False` every effect is off
    and the spectrum is the ideal deterministic one (nmr_mode='ideal')."""
    enabled: bool = True
    noise_sigma: float = 0.10            # additive spectral noise, area/ppm
                                         # units per sqrt(scan).  For scale: a
                                         # 0.3 M EGDA backbone peak tops near
                                         # ~40 in these units -> per-point
                                         # SNR ~400, a plausible single-scan
                                         # benchtop figure (ASSUMED)
    shift_drift_ppm: float = 0.005       # global reference drift, 1 sigma
    shift_jitter_ppm: float = 0.001      # per-group shift error, 1 sigma
    linewidth_rel_sigma: float = 0.10    # lognormal linewidth variation
    baseline_offset: float = 0.01        # constant baseline, area/ppm units
    baseline_curve: float = 0.02         # quadratic baseline amplitude
    phase_error_deg: float = 2.0         # zero-order phase error, 1 sigma
    gain_drift_rel_sigma: float = 0.01   # acquisition-to-acquisition gain
    response_factors: Dict[str, float] = field(default_factory=dict)
    # per-species response (calibration) error, e.g. {"EGMA": 1.03}
    t1_s: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_T1_S))

    def ideal(self) -> "SpectralNuisance":
        return replace(self, enabled=False)


@dataclass
class RealizedNuisance:
    """One acquisition's random draw of the nuisance parameters."""
    shift_offset_ppm: float = 0.0
    group_jitter_ppm: Optional[np.ndarray] = None    # per carbon-bound group
    linewidth_factor: float = 1.0
    baseline: Tuple[float, float] = (0.0, 0.0)       # (offset, curvature)
    phase_rad: float = 0.0
    gain: float = 1.0


@dataclass
class Line:
    """One transition: unit-area Lorentzian x area."""
    ppm: float
    area: float          # proton-molarity units (nH x C x response x ...)
    fwhm_hz: float
    species: str         # Layer-1 name, or "exchange"


def first_order_multiplet(center_ppm: float, n_partners: int, j_hz: float,
                          hz_per_ppm: float) -> List[Tuple[float, float]]:
    """[(ppm, relative_area), ...]; binomial first-order multiplet
    (unchanged physics from sim_nmr(2).py)."""
    weights = [comb(n_partners, k) for k in range(n_partners + 1)]
    norm = float(sum(weights))
    j_ppm = j_hz / hz_per_ppm
    return [(center_ppm + (n_partners / 2.0 - k) * j_ppm, w / norm)
            for k, w in enumerate(weights)]


def flow_response(acq: AcquisitionSettings, t1_s: float) -> float:
    """Phenomenological incomplete-relaxation / flow response factor in [0,1].

    E = 1 - exp(-t_pol / T1) with polarization time
        t_pol = premag_volume / Q_analytical + repetition_time.

    This is NOT a rigorous flowing-spin Bloch model; it is a documented
    surrogate that (i) decreases when the analytical flow is raised or the
    recycle time shortened, and (ii) is EXACTLY 1 when
    flow_response_enabled=False.  CAL: replace with factors measured from
    standards under the actual flow protocol."""
    if not acq.flow_response_enabled:
        return 1.0
    q_mL_s = max(acq.analytical_flow_mL_min, 1e-9) / 60.0
    t_pol = acq.premag_volume_mL / q_mL_s + acq.repetition_time_s
    return 1.0 - float(np.exp(-t_pol / max(t1_s, 1e-9)))


class NMRSimulator:
    """Forward model: molar concentrations -> 80 MHz 1H spectrum.

    `simulate` is the instrument-side entry point (draws nuisances from rng);
    `basis_spectrum` is the fitting-side entry point (deterministic, ideal
    lineshape at commanded conditions) used by spectral_fit.py."""

    def __init__(self, acq: AcquisitionSettings,
                 nuisance: Optional[SpectralNuisance] = None):
        self.acq = acq
        self.nuisance = nuisance or SpectralNuisance()

    # ------------------------------------------------------------------ #
    def lines(self, conc_M: Dict[str, float],
              realized: Optional[RealizedNuisance] = None) -> List[Line]:
        """Transition list for a composition (Layer-1 names, mol/L)."""
        acq, nu = self.acq, self.nuisance
        rl = realized or RealizedNuisance()
        jitter = (rl.group_jitter_ppm if rl.group_jitter_ppm is not None
                  else np.zeros(len(CARBON_BOUND_GROUPS)))
        out: List[Line] = []
        for g, (label, delta, n_part, n_h, sp) in enumerate(
                CARBON_BOUND_GROUPS):
            c = max(float(conc_M.get(sp, 0.0)), 0.0)
            if c <= 0.0:
                continue
            resp = (nu.response_factors.get(sp, 1.0) if nu.enabled else 1.0)
            relax = flow_response(acq, nu.t1_s.get(sp, 3.0))
            area_g = n_h * c * resp * relax * rl.gain
            center = delta + rl.shift_offset_ppm + float(jitter[g])
            fwhm = acq.fwhm_sharp_hz * rl.linewidth_factor
            for p, w in first_order_multiplet(center, n_part, acq.j_hz,
                                              acq.hz_per_ppm):
                out.append(Line(ppm=p, area=w * area_g, fwhm_hz=fwhm,
                                species=sp))
        ex = self.exchange_line(conc_M, rl)
        if ex is not None:
            out.append(ex)
        return out

    def exchange_line(self, conc_M: Dict[str, float],
                      rl: RealizedNuisance) -> Optional[Line]:
        """Pooled fast-exchange H2O/OH/COOH line at the population-weighted
        average shift, at the NMR-CELL temperature (physics unchanged from
        sim_nmr(2).py), scaled by the water-suppression residual factor."""
        acq = self.acq
        num = tot = 0.0
        for sp, n_h, shift in EXCHANGEABLE:
            if shift is None:
                shift = water_shift(acq.nmr_temperature_C)
            p = n_h * max(float(conc_M.get(sp, 0.0)), 0.0)
            num += p * shift
            tot += p
        if tot <= 1e-12:
            return None
        relax = flow_response(acq, self.nuisance.t1_s.get("H2O", 3.0))
        return Line(ppm=num / tot + rl.shift_offset_ppm,
                    area=tot * acq.water_suppression_factor * relax * rl.gain,
                    fwhm_hz=acq.fwhm_broad_hz * rl.linewidth_factor,
                    species="exchange")

    # ------------------------------------------------------------------ #
    @staticmethod
    def _lorentz(ppm: np.ndarray, line: Line, hz_per_ppm: float,
                 dispersion: bool = False) -> np.ndarray:
        hw = 0.5 * line.fwhm_hz / hz_per_ppm          # HWHM in ppm
        dx = ppm - line.ppm
        if dispersion:
            return line.area / np.pi * dx / (dx ** 2 + hw ** 2)
        return line.area * hw / np.pi / (dx ** 2 + hw ** 2)

    def _spectrum_analytic(self, lines: Sequence[Line]) -> np.ndarray:
        ppm = self.acq.ppm_grid()
        y = np.zeros_like(ppm)
        for ln in lines:
            y += self._lorentz(ppm, ln, self.acq.hz_per_ppm)
        return y

    def _spectrum_fid(self, lines: Sequence[Line], phase_rad: float,
                      rng: Optional[np.random.Generator],
                      noise_sigma: float) -> np.ndarray:
        """FID engine: known transitions -> complex FID -> T2* decay ->
        receiver noise -> zero-order phase -> FFT -> real spectrum on the
        SAME ppm grid and amplitude convention as the analytic engine."""
        acq = self.acq
        n = acq.n_points
        sw_hz = (acq.ppm_max - acq.ppm_min) * acq.hz_per_ppm
        dt = 1.0 / sw_hz                                    # complex dwell
        t = np.arange(n) * dt
        center_ppm = 0.5 * (acq.ppm_min + acq.ppm_max)
        fid = np.zeros(n, dtype=complex)
        for ln in lines:
            f = (ln.ppm - center_ppm) * acq.hz_per_ppm      # offset, Hz
            r2 = np.pi * ln.fwhm_hz                          # 1/T2*
            fid += ln.area * np.exp((2j * np.pi * f - r2) * t)
        fid[0] *= 0.5                                        # half first point
        if rng is not None and noise_sigma > 0.0:
            # equivalent frequency-domain sigma = noise_sigma (area/ppm units)
            sig_t = noise_sigma * np.sqrt(n / 2.0) / (acq.hz_per_ppm * dt * n)
            fid += sig_t * (rng.standard_normal(n)
                            + 1j * rng.standard_normal(n))
        fid *= np.exp(1j * phase_rad)
        # x2: the one-sided FID transform carries half the two-sided
        # Lorentzian area; the half-first-point correction fixes the DC bias
        spec = np.fft.fftshift(np.fft.fft(fid)) * dt * 2.0   # -> per-Hz units
        freq = np.fft.fftshift(np.fft.fftfreq(n, d=dt))
        ppm_axis = center_ppm + freq / acq.hz_per_ppm
        y = np.interp(self.acq.ppm_grid(), ppm_axis,
                      spec.real * acq.hz_per_ppm)            # per-ppm units
        return y

    # ------------------------------------------------------------------ #
    def draw_realization(self, rng: np.random.Generator) -> RealizedNuisance:
        nu = self.nuisance
        if not nu.enabled:
            return RealizedNuisance()
        return RealizedNuisance(
            shift_offset_ppm=rng.normal(0.0, nu.shift_drift_ppm),
            group_jitter_ppm=rng.normal(0.0, nu.shift_jitter_ppm,
                                        len(CARBON_BOUND_GROUPS)),
            linewidth_factor=float(np.exp(rng.normal(
                0.0, nu.linewidth_rel_sigma))),
            baseline=(rng.normal(0.0, nu.baseline_offset),
                      rng.normal(0.0, nu.baseline_curve)),
            phase_rad=np.deg2rad(rng.normal(0.0, nu.phase_error_deg)),
            gain=float(np.exp(rng.normal(0.0, nu.gain_drift_rel_sigma))),
        )

    def simulate(self, conc_M: Dict[str, float],
                 rng: Optional[np.random.Generator] = None
                 ) -> Tuple[np.ndarray, np.ndarray, RealizedNuisance]:
        """One acquisition.  Returns (ppm_grid, spectrum, realized_nuisance).
        With nuisance.enabled=False (nmr_mode='ideal') the output is
        deterministic and rng is unused."""
        acq, nu = self.acq, self.nuisance
        rl = (self.draw_realization(rng) if (nu.enabled and rng is not None)
              else RealizedNuisance())
        lines = self.lines(conc_M, rl)
        noise_per_scan = nu.noise_sigma if nu.enabled else 0.0
        sigma = noise_per_scan / np.sqrt(max(acq.n_scans, 1))
        if acq.engine == "fid":
            y = self._spectrum_fid(lines, rl.phase_rad, rng, sigma)
        else:
            y = self._spectrum_analytic(lines)
            if nu.enabled and abs(rl.phase_rad) > 0.0:
                # zero-order phase error mixes in the dispersion lineshape
                yd = np.zeros_like(y)
                ppm = acq.ppm_grid()
                for ln in lines:
                    hw = 0.5 * ln.fwhm_hz / acq.hz_per_ppm
                    dx = ppm - ln.ppm
                    yd += ln.area / np.pi * dx / (dx ** 2 + hw ** 2)
                y = np.cos(rl.phase_rad) * y + np.sin(rl.phase_rad) * yd
            if nu.enabled and rng is not None and sigma > 0.0:
                y = y + rng.normal(0.0, sigma, y.shape)
        if nu.enabled:
            ppm = acq.ppm_grid()
            x = (2.0 * (ppm - acq.ppm_min) / (acq.ppm_max - acq.ppm_min)
                 - 1.0)
            y = y + rl.baseline[0] + rl.baseline[1] * x ** 2
        return acq.ppm_grid(), y, rl

    # ------------------------------------------------------------------ #
    def basis_spectrum(self, species: str,
                       shift_offset_ppm: float = 0.0,
                       linewidth_factor: float = 1.0,
                       dispersion: bool = False) -> np.ndarray:
        """Unit-concentration (1 mol/L) ideal spectrum of one species'
        carbon-bound groups - the fitting basis.  Deliberately EXCLUDES
        response/relaxation factors: the fitter assumes nominal calibration
        unless it has been explicitly calibrated for those effects.
        dispersion=True returns the dispersion-mode lineshape, used by the
        fitter to model a zero-order phase error."""
        ppm = self.acq.ppm_grid()
        y = np.zeros_like(ppm)
        for label, delta, n_part, n_h, sp in CARBON_BOUND_GROUPS:
            if sp != species:
                continue
            for p, w in first_order_multiplet(
                    delta + shift_offset_ppm, n_part, self.acq.j_hz,
                    self.acq.hz_per_ppm):
                y += self._lorentz(
                    ppm, Line(ppm=p, area=w * n_h,
                              fwhm_hz=self.acq.fwhm_sharp_hz
                              * linewidth_factor, species=sp),
                    self.acq.hz_per_ppm, dispersion=dispersion)
        return y

    def group_basis(self, group_index: int, shift_offset_ppm: float = 0.0,
                    linewidth_factor: float = 1.0) -> np.ndarray:
        """Unit-concentration lineshape of ONE carbon-bound group (used by
        the fitter to propagate per-group shift-calibration uncertainty)."""
        label, delta, n_part, n_h, sp = CARBON_BOUND_GROUPS[group_index]
        ppm = self.acq.ppm_grid()
        y = np.zeros_like(ppm)
        for p, w in first_order_multiplet(
                delta + shift_offset_ppm, n_part, self.acq.j_hz,
                self.acq.hz_per_ppm):
            y += self._lorentz(
                ppm, Line(ppm=p, area=w * n_h,
                          fwhm_hz=self.acq.fwhm_sharp_hz * linewidth_factor,
                          species=sp), self.acq.hz_per_ppm)
        return y

    def exchange_basis(self, center_ppm: float,
                       linewidth_factor: float = 1.0,
                       dispersion: bool = False) -> np.ndarray:
        """Unit-area broad exchange-pool basis at a free center (nuisance)."""
        ppm = self.acq.ppm_grid()
        return self._lorentz(
            ppm, Line(ppm=center_ppm, area=1.0,
                      fwhm_hz=self.acq.fwhm_broad_hz * linewidth_factor,
                      species="exchange"), self.acq.hz_per_ppm,
            dispersion=dispersion)
