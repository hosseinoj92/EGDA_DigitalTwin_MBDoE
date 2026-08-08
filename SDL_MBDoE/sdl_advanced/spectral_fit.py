"""
Automated spectral deconvolution: spectrum -> concentrations + Sigma_y.

Variable-projection structure:

  nonlinear nuisances  eta = (global shift offset, ln linewidth factor,
                              exchange-pool center, zero-order phase)
  linear amplitudes    a   = (C_EGDA, C_EGMA, C_EG, C_AcOH,
                              exchange-pool area, baseline b0, b1, b2)

The phase enters through basis columns  cos(phi) A_s + sin(phi) D_s  with
A/D the absorption/dispersion lineshapes, matching how a zero-order phase
error mixes the modes in the instrument.

For each eta trial the linear subproblem

    min_a || y - B(eta) a ||^2 ,  a_species >= 0, a_pool >= 0, baseline free

is solved with bounded least squares (scipy lsq_linear); the outer nonlinear
problem over eta is solved with scipy least_squares on the projected
residual.  Basis columns are the simulator's unit-concentration ideal
spectra, so the returned amplitudes ARE molar concentrations under nominal
calibration.

Sigma_y comes from the FULL Jacobian at the optimum (linear columns +
numerical eta columns), sigma^2 (J'J)^-1 restricted to the species block -
so overlapping EGDA/EGMA resonances naturally produce correlated (negative
off-diagonal) concentration errors instead of a hand-picked rho_overlap.
`bootstrap_coverage` validates that these intervals have ~nominal coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import least_squares, lsq_linear

from .spectral import (AcquisitionSettings, CARBON_BOUND_GROUPS,
                       NMRSimulator, QUANTIFIED_SPECIES, water_shift)

#: variance floor: never report a concentration variance below (1e-6 M)^2
_VAR_FLOOR = 1e-12


@dataclass
class QuantificationResult:
    species: Tuple[str, ...]
    conc_M: np.ndarray                 # estimated concentrations, mol/L
    cov: np.ndarray                    # Sigma_y for conc_M (species x species)
    fitted: np.ndarray                 # fitted spectrum on the ppm grid
    residual: np.ndarray               # y - fitted
    residual_rms: float
    noise_sigma_hat: float             # estimated per-point noise
    condition_number: float            # of the whitened species basis block
    corr: np.ndarray                   # correlation matrix of conc estimates
    eta: Dict[str, float]              # fitted nonlinear nuisances
    nuisance_amplitudes: Dict[str, float]   # pool area, baseline coefficients
    qc_flags: List[str] = field(default_factory=list)
    #: species whose non-negativity bound is ACTIVE: the local Gaussian
    #: covariance is unreliable there - treat the estimate as censored at 0
    #: (one-sided) rather than symmetric-Gaussian (see validation.py)
    censored: Tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not any(f.startswith("FAIL") for f in self.qc_flags)


class SpectralFitter:
    """Deconvolves simulated (later: real) Fourier-80 spectra.

    Knows ONLY public information: the shift database, commanded acquisition
    settings, and the spectrum handed to it.  Never sees truth parameters or
    the realized nuisance draw."""

    def __init__(self, acq: AcquisitionSettings,
                 species: Sequence[str] = QUANTIFIED_SPECIES,
                 fit_phase: bool = True,
                 phase_bound_deg: float = 15.0,
                 shift_window_ppm: float = 0.05,
                 lw_factor_bounds: Tuple[float, float] = (0.5, 2.0),
                 rms_fail_factor: float = 8.0,
                 cond_warn: float = 1e4,
                 sigma_floor_abs_M: float = 0.002,
                 sigma_floor_rel: float = 0.03,
                 gain_drift_rel: float = 0.01,
                 shift_jitter_ppm: float = 0.001):
        # sigma_floor_*: instrument REPRODUCIBILITY/ACCURACY term added in
        # quadrature to the single-spectrum fit covariance.  The fit
        # covariance captures only within-spectrum noise; acquisition-to-
        # acquisition effects and the residual COMPOSITION-DEPENDENT
        # lineshape/overlap systematic that survives response calibration
        # (~2-3%, the classic qNMR accuracy scale) do not appear in one
        # spectrum's Jacobian.  KNOWN LIMITATION (measured, reported in
        # validation.py): in the 1-4 Hz acetyl overlap cluster the residual
        # error is bias-dominated, so symmetric Gaussian intervals for AcOH
        # under-cover (~80-90% at nominal 95%) - flagged for bootstrap
        # intervals once real mixture standards exist.
        # gain_drift_rel: acquisition-to-acquisition receiver-gain drift; a
        # gain error scales EVERY species coherently, so it contributes the
        # rank-one CORRELATED covariance  g^2 * y y^T , not a diagonal term.
        # shift_jitter_ppm: 1-sigma PER-GROUP chemical-shift calibration
        # uncertainty.  In the 7 Hz EGDA/EGMA overlap a sub-0.1 Hz relative
        # shift reapportions the overlapped area, so this term is propagated
        # through the linear solve into Sigma_y (see _package) - it is what
        # makes the EGDA/EGMA covariance realistic.
        # All four are ASSUMED values; CAL: to be measured from replicate
        # standards on the real Fourier 80.
        self.sigma_floor_abs_M = float(sigma_floor_abs_M)
        self.sigma_floor_rel = float(sigma_floor_rel)
        self.gain_drift_rel = float(gain_drift_rel)
        self.shift_jitter_ppm = float(shift_jitter_ppm)
        self.acq = acq
        self.species = tuple(species)
        self.sim = NMRSimulator(acq)          # ideal basis generator
        self.shift_window_ppm = shift_window_ppm
        self.lw_factor_bounds = lw_factor_bounds
        self.rms_fail_factor = rms_fail_factor
        self.cond_warn = cond_warn
        self.fit_phase = fit_phase
        self.phase_bound = np.deg2rad(phase_bound_deg)
        #: per-species response-calibration factors (fitted amplitude per
        #: unit true concentration), measured from PREPARED standards via
        #: calibrate_responses() - the simulation analogue of real
        #: Fourier-80 response calibration.  1.0 = uncalibrated/nominal.
        self.response_correction: Dict[str, float] = {}
        self._ppm = acq.ppm_grid()
        x = (2.0 * (self._ppm - acq.ppm_min)
             / (acq.ppm_max - acq.ppm_min) - 1.0)
        self._baseline_cols = np.stack([np.ones_like(x), x, x ** 2], axis=1)

    # ------------------------------------------------------------------ #
    def _basis(self, eta: np.ndarray) -> np.ndarray:
        """B(eta): columns = phased species spectra, exchange pool, baseline."""
        d_ppm, ln_lw, pool_ppm, phi = eta
        lw = float(np.exp(ln_lw))
        cols = []
        for sp in self.species:
            a = self.sim.basis_spectrum(sp, d_ppm, lw)
            if abs(phi) > 0.0:
                d = self.sim.basis_spectrum(sp, d_ppm, lw, dispersion=True)
                a = np.cos(phi) * a + np.sin(phi) * d
            cols.append(a)
        a = self.sim.exchange_basis(pool_ppm, lw)
        if abs(phi) > 0.0:
            d = self.sim.exchange_basis(pool_ppm, lw, dispersion=True)
            a = np.cos(phi) * a + np.sin(phi) * d
        cols.append(a)
        b = np.stack(cols, axis=1)
        return np.concatenate([b, self._baseline_cols], axis=1)

    def _solve_linear(self, B: np.ndarray, y: np.ndarray
                      ) -> Tuple[np.ndarray, np.ndarray]:
        n_s = len(self.species)
        lo = np.concatenate([np.zeros(n_s + 1), -np.inf * np.ones(3)])
        hi = np.full(n_s + 4, np.inf)
        sol = lsq_linear(B, y, bounds=(lo, hi), method="bvls",
                         max_iter=3 * B.shape[1])
        return sol.x, y - B @ sol.x

    # ------------------------------------------------------------------ #
    def fit(self, ppm: np.ndarray, y: np.ndarray) -> QuantificationResult:
        if ppm.shape != self._ppm.shape or not np.allclose(ppm, self._ppm):
            y = np.interp(self._ppm, ppm, y)
        pool_guess = self._pool_center_guess()
        eta0 = np.array([0.0, 0.0, pool_guess, 0.0])
        w = self.shift_window_ppm
        phi_b = self.phase_bound if self.fit_phase else 1e-12
        lo = np.array([-w, np.log(self.lw_factor_bounds[0]),
                       pool_guess - 1.0, -phi_b])
        hi = np.array([+w, np.log(self.lw_factor_bounds[1]),
                       pool_guess + 1.0, +phi_b])

        def projected_residual(eta: np.ndarray) -> np.ndarray:
            _, r = self._solve_linear(self._basis(eta), y)
            return r

        sol = least_squares(projected_residual, eta0, bounds=(lo, hi),
                            method="trf", xtol=1e-10, ftol=1e-10,
                            diff_step=1e-4)
        eta = sol.x
        B = self._basis(eta)
        a, r = self._solve_linear(B, y)
        return self._package(B, a, r, eta, y)

    # ------------------------------------------------------------------ #
    def _pool_center_guess(self) -> float:
        """Water dominates the pool; start at the water shift at the
        commanded NMR-cell temperature (public knowledge)."""
        return water_shift(self.acq.nmr_temperature_C)

    def _package(self, B: np.ndarray, a: np.ndarray, r: np.ndarray,
                 eta: np.ndarray, y: np.ndarray) -> QuantificationResult:
        n_s = len(self.species)
        n, p_lin = B.shape
        # full Jacobian: linear columns + numerical derivatives wrt eta
        cols = [B]
        h = np.array([1e-5, 1e-4, 1e-4, 1e-4])
        for q in range(len(h)):
            ep = eta.copy()
            ep[q] += h[q]
            cols.append(((self._basis(ep) - B) @ a / h[q])[:, None])
        J = np.concatenate(cols, axis=1)
        dof = max(n - J.shape[1], 1)
        sigma2 = float(r @ r) / dof
        JtJ = J.T @ J
        # eigenvalue-floored inverse (rank-deficiency -> huge variance,
        # mirroring sdl.inference.covariance_from_fim's philosophy)
        wv, V = np.linalg.eigh(JtJ)
        floor = max(float(wv[-1]), 1e-300) * 1e-14
        cov_full = (V @ np.diag(1.0 / np.maximum(wv, floor)) @ V.T) * sigma2
        cov_raw = cov_full[:n_s, :n_s]
        # correlation from the UNfloored block: the (J'J)^-1 overlap
        # structure is scale-free and must survive even near-zero noise
        sig_raw = np.sqrt(np.maximum(np.diag(cov_raw), 1e-300))
        denom = np.outer(sig_raw, sig_raw)
        with np.errstate(divide="ignore", invalid="ignore"):
            corr = np.where(denom > 0, cov_raw / denom, 0.0)
        cov = cov_raw.copy()
        cov[np.diag_indices(n_s)] = np.maximum(np.diag(cov), _VAR_FLOOR)
        # reproducibility floor (see __init__), in quadrature on the diagonal
        floor = (self.sigma_floor_abs_M
                 + self.sigma_floor_rel * np.maximum(a[:n_s], 0.0)) ** 2
        cov[np.diag_indices(n_s)] = np.diag(cov) + floor
        # coherent gain-drift term: rank-one, correlated across species
        c_pos = np.maximum(a[:n_s], 0.0)
        cov = cov + self.gain_drift_rel ** 2 * np.outer(c_pos, c_pos)
        # per-group shift-jitter propagation: linearized effect of each
        # group's center moving by sigma_jitter on the fitted amplitudes
        if self.shift_jitter_ppm > 0.0:
            eta_ = eta
            lw = float(np.exp(eta_[1]))
            hj = 5e-4
            sp_index = {sp: i for i, sp in enumerate(self.species)}
            for g, (_l, _d, _n, _nh, sp) in enumerate(CARBON_BOUND_GROUPS):
                if sp not in sp_index:
                    continue
                amp = max(a[sp_index[sp]], 0.0)
                if amp <= 0.0:
                    continue
                v = amp * (self.sim.group_basis(g, eta_[0] + hj, lw)
                           - self.sim.group_basis(g, eta_[0], lw)) / hj
                dx, *_ = np.linalg.lstsq(B, v, rcond=None)
                jg = dx[:n_s] * self.shift_jitter_ppm
                cov = cov + np.outer(jg, jg)

        # QC ------------------------------------------------------------- #
        flags: List[str] = []
        rms = float(np.sqrt(np.mean(r ** 2)))
        # species-block conditioning after removing baseline/pool projection
        cond = float(np.linalg.cond(B[:, :n_s]))
        if cond > self.cond_warn:
            flags.append(f"WARN ill-conditioned basis (cond={cond:.2e})")
        active = [self.species[i] for i in range(n_s) if a[i] <= 0.0]
        if active:
            flags.append("WARN nonnegativity active: " + ",".join(active))
        med = float(np.median(np.abs(np.diff(y)))) / np.sqrt(2.0) or 1.0
        if rms > self.rms_fail_factor * med:
            flags.append(f"FAIL residual rms {rms:.3g} >> noise scale "
                         f"{med:.3g} - lineshape model inadequate?")

        # response calibration (measured on standards; see
        # calibrate_responses): conc = amplitude / response_factor, with the
        # covariance transformed consistently
        conc = a[:n_s].copy()
        if self.response_correction:
            rf = np.array([self.response_correction.get(sp, 1.0)
                           for sp in self.species])
            conc = conc / rf
            cov = cov / np.outer(rf, rf)

        return QuantificationResult(
            species=self.species, conc_M=conc, cov=cov,
            fitted=B @ a, residual=r, residual_rms=rms,
            noise_sigma_hat=float(np.sqrt(sigma2)),
            condition_number=cond, corr=corr,
            eta={"shift_offset_ppm": float(eta[0]),
                 "linewidth_factor": float(np.exp(eta[1])),
                 "pool_center_ppm": float(eta[2]),
                 "phase_deg": float(np.rad2deg(eta[3]))},
            nuisance_amplitudes={"pool_area": float(a[n_s]),
                                 "b0": float(a[n_s + 1]),
                                 "b1": float(a[n_s + 2]),
                                 "b2": float(a[n_s + 3])},
            qc_flags=flags, censored=tuple(active))


# --------------------------------------------------------------------------- #
class SpectralCovarianceModel:
    """DESIGN-TIME predictor of the deconvolution covariance for a CANDIDATE
    composition - the measurement-aware alternative to the NoiseSurrogate.

    For expected concentrations C at a hypothetical (u, z, theta) it
    evaluates the SAME covariance construction the fitter documents
    (spectral Fisher/Jacobian at the nominal lineshape + reproducibility
    floor + coherent-gain term + shift-jitter propagation), but with the
    ASSUMED/CALIBRATED per-point noise level instead of a realized fit
    residual.  It therefore carries the concentration-, species- and
    overlap-dependence of spectral identifiability into FIM screening,
    spatial design and EIG - without ever simulating a hypothetical
    spectrum pixel-by-pixel and without touching any truth-side nuisance
    realization.

    All inputs are public/assumed quantities (marked CAL where they must be
    replaced by instrument calibration): the shift database, the commanded
    acquisition settings, `assumed_noise_sigma` (per-point receiver noise)
    and `assumed_pool_area` (residual water-pool amplitude entering the
    eta-sensitivity columns)."""

    def __init__(self, fitter: SpectralFitter,
                 assumed_noise_sigma: float = 0.10,     # CAL
                 assumed_pool_area: float = 100.0):     # CAL (~2*[H2O]*supp)
        self.fitter = fitter
        self.species = fitter.species
        self.assumed_noise_sigma = float(assumed_noise_sigma)
        self.assumed_pool_area = float(assumed_pool_area)
        pool0 = fitter._pool_center_guess()
        self._eta0 = np.array([0.0, 0.0, pool0, 0.0])
        self._B = fitter._basis(self._eta0)             # cached linear basis
        n_lin = self._B.shape[1]
        # cached eta-derivative bases per LINEAR component (unit amplitude):
        # column q of J_eta is  sum_i a_i * dB[:, i]/d eta_q
        h = np.array([1e-5, 1e-4, 1e-4, 1e-4])
        self._dB = []                                    # (4, n_pts, n_lin)
        for q in range(4):
            ep = self._eta0.copy()
            ep[q] += h[q]
            self._dB.append((fitter._basis(ep) - self._B) / h[q])
        # cached unit-amplitude group-shift derivative vectors (jitter term)
        self._group_dv = []                              # (group, vec, sp_idx)
        sp_index = {sp: i for i, sp in enumerate(self.species)}
        hj = 5e-4
        for g, (_l, _d, _n, _nh, sp) in enumerate(CARBON_BOUND_GROUPS):
            if sp not in sp_index:
                continue
            v = (fitter.sim.group_basis(g, hj) - fitter.sim.group_basis(g)) \
                / hj
            self._group_dv.append((sp_index[sp], v))
        self._n_lin = n_lin

    # ------------------------------------------------------------------ #
    def cov_at(self, y_pos: np.ndarray) -> np.ndarray:
        """Predicted Sigma_y for ONE position's species concentrations."""
        f = self.fitter
        n_s = len(self.species)
        a = np.zeros(self._n_lin)
        a[:n_s] = np.maximum(np.asarray(y_pos, dtype=float)[:n_s], 0.0)
        a[n_s] = self.assumed_pool_area
        J_eta = np.stack([dB @ a for dB in self._dB], axis=1)
        J = np.concatenate([self._B, J_eta], axis=1)
        JtJ = J.T @ J
        wv, V = np.linalg.eigh(JtJ)
        fl = max(float(wv[-1]), 1e-300) * 1e-14
        cov_full = (V @ np.diag(1.0 / np.maximum(wv, fl)) @ V.T) \
            * self.assumed_noise_sigma ** 2
        cov = cov_full[:n_s, :n_s].copy()
        cov[np.diag_indices(n_s)] = np.maximum(np.diag(cov), _VAR_FLOOR)
        floor = (f.sigma_floor_abs_M
                 + f.sigma_floor_rel * a[:n_s]) ** 2
        cov[np.diag_indices(n_s)] = np.diag(cov) + floor
        cov = cov + f.gain_drift_rel ** 2 * np.outer(a[:n_s], a[:n_s])
        if f.shift_jitter_ppm > 0.0:
            for sp_i, v_unit in self._group_dv:
                amp = a[sp_i]
                if amp <= 0.0:
                    continue
                dx, *_ = np.linalg.lstsq(self._B, amp * v_unit, rcond=None)
                jg = dx[:n_s] * f.shift_jitter_ppm
                cov = cov + np.outer(jg, jg)
        return cov

    def cov_profile(self, y: np.ndarray, n_z: int) -> np.ndarray:
        """Species-major covariance for a whole candidate profile."""
        n_s = len(self.species)
        cov = np.zeros((n_s * n_z, n_s * n_z))
        for k in range(n_z):
            idx = [i * n_z + k for i in range(n_s)]
            cov[np.ix_(idx, idx)] = self.cov_at(y[idx])
        return cov

    def observe(self, m) -> None:
        """No-op: this model is analytic, not data-fitted (interface parity
        with NoiseSurrogate)."""


# --------------------------------------------------------------------------- #
def calibrate_responses(fitter: SpectralFitter, acquire, rng,
                        standards: Optional[List[Dict[str, float]]] = None,
                        n_rep: int = 3) -> Dict[str, float]:
    """Per-species response calibration against PREPARED standards - the
    simulation analogue of the calibration a real Fourier-80 campaign
    performs before autonomous operation.

    `acquire(conc_dict, rng) -> (ppm, spectrum)` is the measurement channel
    (in simulation, the truth-side simulator; on hardware, the real
    spectrometer).  Standard compositions are PREPARED and therefore public
    knowledge - using them does not breach the truth/inference firewall.
    The calibration absorbs systematic lineshape/response biases (e.g. the
    truth's pseudo-Voigt shape or unknown response factors) into measured
    per-species factors, exactly as real calibration would; residual
    COMPOSITION-DEPENDENT effects (overlap!) remain uncorrected and must be
    covered by the claimed covariance."""
    if standards is None:
        standards = [
            {"EGDA": 0.40, "EGMA": 0.0, "EG": 0.0, "AcOH": 0.0, "H2O": 53.0},
            {"EGDA": 0.0, "EGMA": 0.30, "EG": 0.0, "AcOH": 0.0, "H2O": 53.0},
            {"EGDA": 0.0, "EGMA": 0.0, "EG": 0.30, "AcOH": 0.0, "H2O": 53.0},
            {"EGDA": 0.0, "EGMA": 0.0, "EG": 0.0, "AcOH": 0.40, "H2O": 53.0},
            {"EGDA": 0.20, "EGMA": 0.10, "EG": 0.05, "AcOH": 0.15,
             "H2O": 52.0},
        ]
    fitter.response_correction = {}          # fit standards uncorrected
    num = {sp: 0.0 for sp in fitter.species}
    den = {sp: 0.0 for sp in fitter.species}
    for std in standards:
        for _ in range(n_rep):
            ppm, y = acquire(std, rng)
            res = fitter.fit(ppm, y)
            for i, sp in enumerate(fitter.species):
                c_true = float(std.get(sp, 0.0))
                if c_true > 0.0:             # regression through the origin
                    num[sp] += res.conc_M[i] * c_true
                    den[sp] += c_true ** 2
    factors = {sp: (num[sp] / den[sp] if den[sp] > 0 else 1.0)
               for sp in fitter.species}
    fitter.response_correction = factors
    return factors


def bootstrap_coverage(fitter: SpectralFitter, simulator: NMRSimulator,
                       conc_true_M: Dict[str, float], n_boot: int,
                       seed: int = 0, level: float = 0.95
                       ) -> Dict[str, np.ndarray]:
    """Parametric bootstrap: simulate n_boot noisy spectra of a KNOWN
    composition, deconvolve each, and report per-species empirical coverage
    of the nominal `level` intervals plus the error/claimed-sigma ratio.
    Validation utility only (never inside the campaign loop)."""
    rng = np.random.default_rng(seed)
    zc = {0.95: 1.959964, 0.90: 1.644854}.get(level, 1.959964)
    truth = np.array([conc_true_M.get(sp, 0.0) for sp in fitter.species])
    hits = np.zeros(len(fitter.species))
    errs, sigs = [], []
    for _ in range(n_boot):
        ppm, y, _ = simulator.simulate(conc_true_M, rng)
        res = fitter.fit(ppm, y)
        sig = np.sqrt(np.diag(res.cov))
        hits += (np.abs(res.conc_M - truth) <= zc * sig)
        errs.append(res.conc_M - truth)
        sigs.append(sig)
    errs = np.array(errs)
    return {"coverage": hits / n_boot,
            "rmse": np.sqrt(np.mean(errs ** 2, axis=0)),
            "mean_claimed_sigma": np.mean(np.array(sigs), axis=0),
            "bias": np.mean(errs, axis=0)}
