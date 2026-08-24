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
from functools import lru_cache

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
    #: size of the FINAL returned ppm grid.  This is a DISPLAY/processing
    #: choice only - it is NOT the number of physically acquired FID points
    #: and it is NOT the FFT length.  Conflating the three is what let a
    #: configuration claim 4.096 s while simulating 2.129 s.
    n_points: int = 4096
    #: REQUESTED physical FID duration (FID engine only - see below).
    acquisition_time_s: float = 4.096
    #: optional explicit override of the acquired complex-point count; None
    #: derives it from acquisition_time_s x spectral_width_hz
    n_acquired_complex: Optional[int] = None
    #: optional explicit FFT length (zero filling); None picks the next
    #: power of two at or above the acquired count
    fft_points: Optional[int] = None
    repetition_time_s: float = 15.0      # recycle delay between scans
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

    # ---- physical acquisition contract (FID engine) ------------------- #
    # COMPLEX-SAMPLING CONVENTION, stated once so no hidden factor of two
    # can creep in: the receiver samples a COMPLEX point every dwell time,
    # quadrature detection gives a spectral width SW = 1/dwell covering the
    # full ppm window, and N_acquired complex points occupy
    # N_acquired x dwell seconds of real instrument time.  Zero filling
    # lengthens the FFT only - it adds no time, no signal and no noise.
    #
    # The ANALYTIC engine builds the frequency-domain lineshape directly
    # and therefore has no acquisition time at all: none of these
    # quantities affect it, and it must NOT be described as simulating a
    # finite acquisition.  They are physical FID settings.

    #: relative tolerance when an explicit n_acquired_complex is checked
    #: against the requested acquisition time (one dwell period, i.e. the
    #: rounding you cannot avoid when the product is not an integer)
    ACQUISITION_ROUNDING_TOL: float = 1.0

    @property
    def spectral_width_hz(self) -> float:
        """SW = (ppm window) x (spectrometer frequency)."""
        return (self.ppm_max - self.ppm_min) * self.spectrometer_MHz

    @property
    def dwell_time_s(self) -> float:
        """Complex dwell = 1 / SW."""
        return 1.0 / self.spectral_width_hz

    @property
    def resolved_n_acquired_complex(self) -> int:
        """Number of COMPLEX FID points actually sampled."""
        if self.n_acquired_complex is not None:
            return int(self.n_acquired_complex)
        return max(1, int(round(self.acquisition_time_s
                                * self.spectral_width_hz)))

    @property
    def actual_acquisition_time_s(self) -> float:
        """What the instrument really spends: N_acquired x dwell.  Differs
        from `acquisition_time_s` by at most one dwell period, because the
        point count is an integer."""
        return self.resolved_n_acquired_complex * self.dwell_time_s

    @property
    def resolved_fft_points(self) -> int:
        """FFT length >= acquired points; default is the next power of two
        (zero filling, which interpolates the spectrum but adds no
        information)."""
        n_acq = self.resolved_n_acquired_complex
        if self.fft_points is not None:
            return int(self.fft_points)
        return int(2 ** int(np.ceil(np.log2(max(n_acq, 2)))))

    @property
    def frequency_resolution_hz(self) -> float:
        """Digital bin spacing of the zero-filled spectrum, SW / N_fft.
        The TRUE resolution is 1/actual_acquisition_time_s; zero filling
        makes the grid finer without resolving anything new."""
        return self.spectral_width_hz / self.resolved_fft_points

    def acquisition_report(self) -> Dict[str, float]:
        """Requested AND actual acquisition quantities, for the run record.

        Serializing both is what makes it impossible for an archive to
        claim one acquisition time while having simulated another."""
        return {
            "engine": self.engine,
            "requested_acquisition_time_s": float(self.acquisition_time_s),
            "actual_acquisition_time_s": float(self.actual_acquisition_time_s),
            "spectral_width_hz": float(self.spectral_width_hz),
            "dwell_time_s": float(self.dwell_time_s),
            "resolved_n_acquired_complex": int(
                self.resolved_n_acquired_complex),
            "resolved_fft_points": int(self.resolved_fft_points),
            "final_spectrum_points": int(self.n_points),
            "frequency_resolution_hz": float(self.frequency_resolution_hz),
            "true_resolution_hz": float(1.0 / self.actual_acquisition_time_s),
            "n_scans": int(self.n_scans),
            "repetition_time_s": float(self.repetition_time_s),
            "acquisition_time_affects_spectrum": self.engine == "fid",
        }

    def __post_init__(self) -> None:
        if self.spectrometer_MHz <= 0.0:
            raise ValueError("spectrometer_MHz must be positive.")
        if self.ppm_max <= self.ppm_min:
            raise ValueError("ppm_max must exceed ppm_min.")
        if int(self.n_points) < 2:
            raise ValueError("n_points (final ppm grid) must be at least 2.")
        if self.acquisition_time_s <= 0.0:
            raise ValueError("acquisition_time_s must be positive.")
        if int(self.n_scans) < 1:
            raise ValueError("n_scans must be at least 1.")
        if self.repetition_time_s < 0.0:
            raise ValueError("repetition_time_s must be non-negative.")
        if self.engine not in ("analytic", "fid"):
            raise ValueError(f"Unknown NMR engine '{self.engine}'.")
        if self.n_acquired_complex is not None:
            if int(self.n_acquired_complex) < 1:
                raise ValueError("n_acquired_complex must be at least 1.")
            implied = int(self.n_acquired_complex) * self.dwell_time_s
            n_dwells = abs(implied - self.acquisition_time_s) \
                / self.dwell_time_s
            if n_dwells > self.ACQUISITION_ROUNDING_TOL:
                raise ValueError(
                    f"n_acquired_complex={self.n_acquired_complex} implies an "
                    f"acquisition time of {implied:.6g} s, but "
                    f"acquisition_time_s={self.acquisition_time_s:.6g} s was "
                    f"requested ({n_dwells:.1f} dwell periods apart; the "
                    f"documented tolerance is "
                    f"{self.ACQUISITION_ROUNDING_TOL:g}).  Set one or the "
                    f"other, or make them consistent: "
                    f"{self.acquisition_time_s:.6g} s x "
                    f"{self.spectral_width_hz:.6g} Hz = "
                    f"{self.acquisition_time_s * self.spectral_width_hz:.2f} "
                    f"complex points.")
        if self.fft_points is not None:
            if int(self.fft_points) < self.resolved_n_acquired_complex:
                raise ValueError(
                    f"fft_points={self.fft_points} is smaller than the "
                    f"{self.resolved_n_acquired_complex} acquired complex "
                    f"points - that would TRUNCATE acquired data, which is "
                    f"not zero filling.  Use fft_points >= "
                    f"{self.resolved_n_acquired_complex}.")


# --------------------------------------------------------------------------- #
# Receiver-noise bookkeeping for the FID engine
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=32)
def _noise_grid_factor(n_acq: int, n_fft: int, n_points: int,
                       ppm_min: float, ppm_max: float,
                       hz_per_ppm: float) -> float:
    """Std-dev change caused by RESAMPLING the FFT-bin noise onto the display
    grid, computed exactly (no Monte Carlo, no fitted constant).

    Zero filling makes neighbouring FFT bins correlated, and `np.interp`
    then mixes two of them per output point, so the noise standard
    deviation on the returned grid is not the per-bin one.  Both pieces are
    known in closed form.

    With per-component time-domain variance sigma_t^2 on N_acq acquired
    points, zero-filled to N_fft:

        Cov(Re S_j, Re S_k) = sigma_t^2 * sum_{m < N_acq} cos(2 pi (j-k) m / N_fft)

    a Dirichlet kernel.  Writing rho = Cov(adjacent) / Var(bin), an output
    point that lands a fraction w between two adjacent bins has variance

        Var(bin) * [ (1-w)^2 + w^2 + 2 w (1-w) rho ].

    Averaging that over the display grid gives the squared factor returned
    here.  It equals 1 when the display grid coincides with the FFT grid,
    and is < 1 whenever the display grid is coarser (the usual case).

    Dividing the injected time-domain noise by this factor makes the
    RETURNED spectrum carry exactly the requested `noise_sigma` - the same
    contract the analytic engine satisfies trivially by adding noise
    directly to its output grid.  Without it the two engines disagree on
    what `noise_sigma` means, and the FID-truth validation suite would be
    comparing spectra at different effective SNR.
    """
    m = np.arange(n_acq)
    var_bin = float(n_acq)                       # sum cos(0) = N_acq
    cov_adj = float(np.sum(np.cos(2.0 * np.pi * m / n_fft)))
    rho = cov_adj / var_bin if var_bin > 0 else 0.0

    center = 0.5 * (ppm_min + ppm_max)
    freq = np.fft.fftshift(np.fft.fftfreq(n_fft, d=1.0 /
                                          ((ppm_max - ppm_min) * hz_per_ppm)))
    ppm_axis = center + freq / hz_per_ppm
    grid = np.linspace(ppm_min, ppm_max, n_points)
    idx = np.clip(np.searchsorted(ppm_axis, grid) - 1, 0, len(ppm_axis) - 2)
    span = ppm_axis[idx + 1] - ppm_axis[idx]
    w = np.clip((grid - ppm_axis[idx]) / span, 0.0, 1.0)
    var_rel = (1.0 - w) ** 2 + w ** 2 + 2.0 * w * (1.0 - w) * rho
    return float(np.sqrt(np.mean(var_rel)))


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

    # ---- TRUTH-MODEL MISMATCH (anti-"inverse-crime") ------------------- #
    # The fitting model is pure-Lorentzian with the nominal shift/J database;
    # the TRUTH deliberately deviates in ways the fitter does NOT know, so
    # synthetic validation is not the trivial exercise of fitting a model to
    # itself.  All values are ASSUMED plausible magnitudes (CAL: replace by
    # measured lineshape studies on the real instrument); every effect is
    # off when enabled=False.
    gaussian_fraction: float = 0.15      # pseudo-Voigt truth lineshape
    j_mismatch_hz: float = 0.15          # true 3J differs from the database
    static_shift_ppm: float = 0.0008     # per-group STATIC calibration error
                                         # (drawn once per campaign, 1 sigma)
    noise_ar1: float = 0.3               # AR(1) coefficient: colored noise
    baseline_cubic: float = 0.01         # cubic baseline term the fitter's
                                         # quadratic model cannot represent

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
        #: static per-group shift-calibration error of THIS instrument
        #: realization - drawn once on first use (truth-side state the
        #: fitter never sees)
        self._static_shift: Optional[np.ndarray] = None

    def _static_shifts(self, rng: Optional[np.random.Generator]
                       ) -> np.ndarray:
        nu = self.nuisance
        if not nu.enabled or nu.static_shift_ppm <= 0.0 or rng is None:
            return np.zeros(len(CARBON_BOUND_GROUPS))
        if self._static_shift is None:
            self._static_shift = rng.normal(0.0, nu.static_shift_ppm,
                                            len(CARBON_BOUND_GROUPS))
        return self._static_shift

    # ------------------------------------------------------------------ #
    def lines(self, conc_M: Dict[str, float],
              realized: Optional[RealizedNuisance] = None,
              static_shift: Optional[np.ndarray] = None) -> List[Line]:
        """Transition list for a composition (Layer-1 names, mol/L).
        static_shift: the per-group STATIC calibration error of the truth
        instrument (mismatch effect; zero for the fitting basis)."""
        acq, nu = self.acq, self.nuisance
        rl = realized or RealizedNuisance()
        jitter = (rl.group_jitter_ppm if rl.group_jitter_ppm is not None
                  else np.zeros(len(CARBON_BOUND_GROUPS)))
        static = (static_shift if static_shift is not None
                  else np.zeros(len(CARBON_BOUND_GROUPS)))
        j_true = acq.j_hz + (nu.j_mismatch_hz if nu.enabled else 0.0)
        out: List[Line] = []
        for g, (label, delta, n_part, n_h, sp) in enumerate(
                CARBON_BOUND_GROUPS):
            c = max(float(conc_M.get(sp, 0.0)), 0.0)
            if c <= 0.0:
                continue
            resp = (nu.response_factors.get(sp, 1.0) if nu.enabled else 1.0)
            relax = flow_response(acq, nu.t1_s.get(sp, 3.0))
            area_g = n_h * c * resp * relax * rl.gain
            center = (delta + rl.shift_offset_ppm + float(jitter[g])
                      + float(static[g]))
            fwhm = acq.fwhm_sharp_hz * rl.linewidth_factor
            for p, w in first_order_multiplet(center, n_part, j_true,
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

    @staticmethod
    def _gauss(ppm: np.ndarray, line: Line, hz_per_ppm: float) -> np.ndarray:
        """Unit-area Gaussian with the same FWHM (pseudo-Voigt component)."""
        w = line.fwhm_hz / hz_per_ppm
        c = 4.0 * np.log(2.0) / w ** 2
        return line.area * np.sqrt(c / np.pi) * np.exp(
            -c * (ppm - line.ppm) ** 2)

    def _truth_lineshape(self, ppm: np.ndarray, ln: Line) -> np.ndarray:
        """TRUTH-side lineshape: pseudo-Voigt mixture the pure-Lorentzian
        fitting basis does not know about (mismatch effect; pure Lorentzian
        when nuisances are disabled).  The broad exchange pool stays
        Lorentzian."""
        nu = self.nuisance
        f = (nu.gaussian_fraction
             if (nu.enabled and ln.species != "exchange") else 0.0)
        yl = self._lorentz(ppm, ln, self.acq.hz_per_ppm)
        if f <= 0.0:
            return yl
        return (1.0 - f) * yl + f * self._gauss(ppm, ln, self.acq.hz_per_ppm)

    def _spectrum_analytic(self, lines: Sequence[Line]) -> np.ndarray:
        ppm = self.acq.ppm_grid()
        y = np.zeros_like(ppm)
        for ln in lines:
            y += self._truth_lineshape(ppm, ln)
        return y

    def _spectrum_fid(self, lines: Sequence[Line], phase_rad: float,
                      rng: Optional[np.random.Generator],
                      noise_sigma: float) -> np.ndarray:
        """FID engine: known transitions -> complex FID -> T2* decay ->
        receiver noise -> zero-order phase -> FFT -> real spectrum on the
        SAME ppm grid and amplitude convention as the analytic engine."""
        acq = self.acq
        # PHYSICAL acquisition: N_acq complex points, one per dwell period.
        # n_points (the display grid) and the FFT length are deliberately
        # NOT used here - see AcquisitionSettings for the convention.
        n_acq = acq.resolved_n_acquired_complex
        n_fft = acq.resolved_fft_points
        dt = acq.dwell_time_s
        t = np.arange(n_acq) * dt
        center_ppm = 0.5 * (acq.ppm_min + acq.ppm_max)
        nu = self.nuisance
        g_frac = nu.gaussian_fraction if nu.enabled else 0.0
        fid = np.zeros(n_acq, dtype=complex)
        for ln in lines:
            f = (ln.ppm - center_ppm) * acq.hz_per_ppm      # offset, Hz
            r2 = np.pi * ln.fwhm_hz                          # 1/T2*
            env = np.exp(-r2 * t)
            if g_frac > 0.0 and ln.species != "exchange":
                # Gaussian FID envelope with the same frequency-domain FWHM:
                # FT[exp(-a t^2)] has FWHM w when a = (pi w)^2 / (4 ln 2)
                a_g = (np.pi * ln.fwhm_hz) ** 2 / (4.0 * np.log(2.0))
                env = (1.0 - g_frac) * env + g_frac * np.exp(-a_g * t ** 2)
            fid += ln.area * env * np.exp(2j * np.pi * f * t)
        if rng is not None and noise_sigma > 0.0:
            # RECEIVER NOISE, generated ONLY on acquired samples.
            #
            # Derivation (complex convention, per-component time-domain std
            # sigma_t).  The FFT of the zero-filled record is
            #     S_j = sum_{k < N_acq} fid_k exp(-2 pi i j k / N_fft),
            # so Var[Re S_j] = N_acq sigma_t^2: the ZERO-FILLED points
            # contribute nothing, which is exactly why enlarging fft_points
            # cannot improve SNR.  The spectrum is scaled by
            # (dt * 2 * hz_per_ppm), giving
            #     sigma_bin = 2 dt hz_per_ppm sqrt(N_acq) sigma_t.
            # `_NOISE_GRID_FACTOR` then corrects for the variance reduction
            # of resampling that (bin-correlated) noise onto the coarser
            # display grid, so the RETURNED spectrum carries exactly
            # `noise_sigma` - the same contract the analytic engine honours
            # by construction.  Both factors are verified numerically in
            # tests/test_acquisition.py.
            grid_factor = _noise_grid_factor(
                n_acq, n_fft, acq.n_points, acq.ppm_min, acq.ppm_max,
                acq.hz_per_ppm)
            sig_t = (noise_sigma / grid_factor
                     / (2.0 * dt * acq.hz_per_ppm * np.sqrt(n_acq)))
            eps = (rng.standard_normal(n_acq)
                   + 1j * rng.standard_normal(n_acq))
            phi_ar = nu.noise_ar1 if nu.enabled else 0.0
            if phi_ar > 0.0:                 # colored (AR1) receiver noise
                for k in range(1, n_acq):
                    eps[k] += phi_ar * eps[k - 1]
                eps *= np.sqrt(1.0 - phi_ar ** 2)   # unit marginal variance
            fid += sig_t * eps
        # Half-first-point: the standard correction for a one-sided
        # transform, applied to the COMPLETE record (signal + noise) as a
        # spectrometer does - still appropriate, since the DC bias it
        # removes is a property of sampling from t = 0 and is independent of
        # how many points follow.
        fid[0] *= 0.5
        fid *= np.exp(1j * phase_rad)
        # ZERO FILLING to n_fft >= n_acq interpolates the spectrum; it adds
        # no acquisition time, no signal and no noise.
        # x2: the one-sided FID transform carries half the two-sided
        # Lorentzian area; the half-first-point correction fixes the DC bias
        spec = np.fft.fftshift(np.fft.fft(fid, n=n_fft)) * dt * 2.0
        freq = np.fft.fftshift(np.fft.fftfreq(n_fft, d=dt))
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
        lines = self.lines(conc_M, rl, static_shift=self._static_shifts(rng))
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
                eps = rng.standard_normal(y.shape)
                if nu.noise_ar1 > 0.0:       # colored noise (mismatch)
                    phi_ar = nu.noise_ar1
                    for k in range(1, len(eps)):
                        eps[k] += phi_ar * eps[k - 1]
                    eps *= np.sqrt(1.0 - phi_ar ** 2)
                y = y + sigma * eps
        if nu.enabled:
            ppm = acq.ppm_grid()
            x = (2.0 * (ppm - acq.ppm_min) / (acq.ppm_max - acq.ppm_min)
                 - 1.0)
            y = (y + rl.baseline[0] + rl.baseline[1] * x ** 2
                 + nu.baseline_cubic * x ** 3)   # cubic: outside the fitter's
        return acq.ppm_grid(), y, rl             # quadratic baseline model

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
