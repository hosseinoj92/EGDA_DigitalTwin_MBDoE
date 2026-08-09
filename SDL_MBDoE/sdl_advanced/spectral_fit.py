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


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class NMRCalibration:
    """PUBLIC calibration artifact: everything a real Fourier-80 campaign
    would obtain from PREPARED STANDARD MIXTURES, and nothing else.

    It contains only measurable/public quantities - response factors, the
    empirical bias vector, the residual correlation and variance model, and
    the interval-scale factors.  It deliberately contains NO hidden kinetic
    truth and NO realized instrument-nuisance draw, so handing it to the
    design layer cannot breach the truth/inference firewall.

    ONE artifact is consumed by BOTH the measurement pathway
    (SpectralFitter) and the design-time expected covariance
    (SpectralCovarianceModel), so Sigma_actual and Sigma_expected are two
    evaluations of the SAME measurement model rather than two independently
    invented ones.

    Residual model (per species i, concentration c_i):

        sigma_emp,i(c) = scale_i * sqrt( var_const_i + (rel_i * c_i)^2 )
        Sigma_emp(c)   = corr * outer(sigma_emp, sigma_emp)

    fitted on DATASET 1 (calibration-fit standards); `scale` is estimated on
    DATASET 2 (independent calibration-check standards) and never on the
    final held-out validation set."""
    species: Tuple[str, ...]
    response_factors: Dict[str, float]
    bias_M: np.ndarray                    # additive bias, mol/L
    corr: np.ndarray                      # inter-species residual correlation
    var_const_M2: np.ndarray              # constant variance component
    rel: np.ndarray                       # concentration-proportional part
    scale: np.ndarray                     # interval scale from DATASET 2
    meta: Dict = field(default_factory=dict)

    def sigma_emp(self, conc: np.ndarray) -> np.ndarray:
        c = np.maximum(np.asarray(conc, dtype=float), 0.0)
        return self.scale * np.sqrt(self.var_const_M2 + (self.rel * c) ** 2)

    def cov_emp(self, conc: np.ndarray) -> np.ndarray:
        s = self.sigma_emp(conc)
        return self.corr * np.outer(s, s)

    def rf_vector(self) -> np.ndarray:
        return np.array([self.response_factors.get(sp, 1.0)
                         for sp in self.species])

    def contains_only_public_fields(self) -> bool:
        """Guard used by the firewall test: the artifact must expose only
        calibration quantities (no theta, no realized nuisance)."""
        allowed = {"species", "response_factors", "bias_M", "corr",
                   "var_const_M2", "rel", "scale", "meta"}
        return set(self.__dataclass_fields__) == allowed


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
        #: empirical error model measured on CALIBRATION standards
        #: (calibrate_empirical): additive bias and residual covariance that
        #: the single-spectrum Jacobian cannot see.  None = uncalibrated.
        self.empirical_bias: Optional[np.ndarray] = None
        self.empirical_cov: Optional[np.ndarray] = None
        self.empirical_corr: Optional[np.ndarray] = None
        self.empirical_var_const: Optional[np.ndarray] = None
        self.empirical_rel: Optional[np.ndarray] = None
        self.empirical_scale: Optional[np.ndarray] = None
        #: the PUBLIC calibration artifact this fitter is running with
        self.calibration: Optional["NMRCalibration"] = None
        self._ppm = acq.ppm_grid()
        x = (2.0 * (self._ppm - acq.ppm_min)
             / (acq.ppm_max - acq.ppm_min) - 1.0)
        self._baseline_cols = np.stack([np.ones_like(x), x, x ** 2], axis=1)

    # ------------------------------------------------------------------ #
    def apply_calibration(self, cal: "NMRCalibration") -> None:
        """Adopt a PUBLIC calibration artifact.  The design-time
        SpectralCovarianceModel adopts the SAME object, so the measurement
        covariance and the expected covariance are one model."""
        if tuple(cal.species) != tuple(self.species):
            raise ValueError(
                f"calibration species {cal.species} do not match fitter "
                f"species {self.species}.")
        self.calibration = cal
        self.response_correction = dict(cal.response_factors)
        self.empirical_bias = np.asarray(cal.bias_M, dtype=float)
        self.empirical_corr = np.asarray(cal.corr, dtype=float)
        self.empirical_var_const = np.asarray(cal.var_const_M2, dtype=float)
        self.empirical_rel = np.asarray(cal.rel, dtype=float)
        self.empirical_scale = np.asarray(cal.scale, dtype=float)
        self.empirical_cov = cal.cov_emp(np.zeros(len(self.species)))

    def component_spectra(self, res: "QuantificationResult"
                          ) -> Dict[str, np.ndarray]:
        """REPORTING ONLY: the per-species (and pool/baseline) contributions
        to an already-computed fit, rebuilt from the result's own stored
        nuisance parameters and amplitudes.

        It refits nothing and returns the decomposition whose sum is
        `res.fitted`; used by nmr_examples.py to draw the component traces
        under an observed/fitted/residual figure.  The species amplitude is
        recovered by inverting the two reported corrections in order:
        conc = amplitude / response_factor - bias, hence
        amplitude = (conc + bias) * response_factor."""
        eta = np.array([res.eta["shift_offset_ppm"],
                        np.log(res.eta["linewidth_factor"]),
                        res.eta["pool_center_ppm"],
                        np.deg2rad(res.eta["phase_deg"])])
        B = self._basis(eta)
        n_s = len(self.species)
        rf = np.array([self.response_correction.get(sp, 1.0)
                       for sp in self.species]) if self.response_correction \
            else np.ones(n_s)
        bias = (self.empirical_bias if self.empirical_bias is not None
                else np.zeros(n_s))
        amp = (np.asarray(res.conc_M, dtype=float) + bias) * rf
        out = {sp: B[:, i] * amp[i] for i, sp in enumerate(self.species)}
        na = res.nuisance_amplitudes or {}
        out["exchange_pool"] = B[:, n_s] * float(na.get("pool_area", 0.0))
        out["baseline"] = sum(
            B[:, n_s + 1 + k] * float(na.get(f"b{k}", 0.0)) for k in range(3))
        return out

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
        # Two mutually exclusive ways to describe the error the single-
        # spectrum Jacobian cannot see (never both - that double-counts):
        #   calibrated:   Sigma_eff = Sigma_fit + Sigma_empirical
        #                 (measured on standards, added in _package below)
        #   uncalibrated: the ASSUMED surrogate terms here (floor, coherent
        #                 gain, shift jitter)
        calibrated = self.empirical_cov is not None
        if not calibrated:
            floor = (self.sigma_floor_abs_M
                     + self.sigma_floor_rel * np.maximum(a[:n_s], 0.0)) ** 2
            cov[np.diag_indices(n_s)] = np.diag(cov) + floor
            # coherent gain-drift term: rank-one, correlated across species
            c_pos = np.maximum(a[:n_s], 0.0)
            cov = cov + self.gain_drift_rel ** 2 * np.outer(c_pos, c_pos)
        # per-group shift-jitter propagation: linearized effect of each
        # group's center moving by sigma_jitter on the fitted amplitudes
        if self.shift_jitter_ppm > 0.0 and not calibrated:
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
        # empirical calibration (calibrate_empirical): remove the measured
        # systematic bias and ADD the measured residual covariance, which
        # carries the composition-dependent overlap error the single-
        # spectrum Jacobian cannot see (inter-species terms preserved)
        if self.empirical_bias is not None:
            conc = conc - self.empirical_bias
        if self.empirical_corr is not None:
            scale = (self.empirical_scale
                     if self.empirical_scale is not None
                     else np.ones(n_s))
            s_emp = scale * np.sqrt(
                self.empirical_var_const
                + (self.empirical_rel * np.maximum(conc, 0.0)) ** 2)
            cov = cov + self.empirical_corr * np.outer(s_emp, s_emp)
        elif self.empirical_cov is not None:
            cov = cov + self.empirical_cov

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
    eta-sensitivity columns).

    TWO MODES - and in the calibrated mode the design layer and the
    measurement layer share ONE public NMRCalibration artifact, so the
    covariance MBDoE expects is the covariance the instrument delivers:

      UNCALIBRATED:  Sigma_exp = Sigma_spectral
                                 + assumed floor/gain/shift-jitter terms
      CALIBRATED:    Sigma_exp = Sigma_spectral / (rf rf^T)
                                 + Sigma_empirical(c)     [same model, same
                                                          scale, same corr]

    The response-factor division is the same unit transform the fitter
    applies when it converts fitted amplitudes into concentrations."""

    def __init__(self, fitter: SpectralFitter,
                 assumed_noise_sigma: float = 0.10,     # CAL
                 assumed_pool_area: float = 100.0,      # CAL (~2*[H2O]*supp)
                 calibration: Optional["NMRCalibration"] = None):
        self.fitter = fitter
        self.species = fitter.species
        # adopt the SAME public artifact the measurement fitter uses
        cal = calibration if calibration is not None else fitter.calibration
        if cal is not None and fitter.calibration is None:
            fitter.apply_calibration(cal)
        self.calibration = cal
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
        if self.calibration is not None:
            # CALIBRATED: transform the spectral part into concentration
            # units exactly as the fitter does, then add the SAME empirical
            # residual model.  The assumed floor/gain/jitter surrogates are
            # NOT applied - that would double-count what the calibration
            # already measures.
            rf = self.calibration.rf_vector()
            cov = cov / np.outer(rf, rf)
            return cov + self.calibration.cov_emp(a[:n_s] / rf)
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
def _check_standards() -> List[Dict[str, float]]:
    """DATASET 2 - independent calibration-CHECK standards.

    Prepared mixtures that SPAN the composition range the campaign will
    actually measure (including high-conversion, water-rich reaction-like
    states), so the interval scale is estimated where it will be used.
    These are prepared compositions: public information, not truth."""
    return [
        {"EGDA": 0.45, "EGMA": 0.04, "EG": 0.01, "AcOH": 0.06, "H2O": 53.0},
        {"EGDA": 0.30, "EGMA": 0.12, "EG": 0.04, "AcOH": 0.20, "H2O": 52.5},
        {"EGDA": 0.18, "EGMA": 0.16, "EG": 0.10, "AcOH": 0.40, "H2O": 52.0},
        {"EGDA": 0.08, "EGMA": 0.14, "EG": 0.22, "AcOH": 0.60, "H2O": 51.0},
        {"EGDA": 0.01, "EGMA": 0.05, "EG": 0.38, "AcOH": 0.85, "H2O": 50.0},
        {"EGDA": 0.25, "EGMA": 0.00, "EG": 0.00, "AcOH": 0.00, "H2O": 54.0},
        {"EGDA": 0.00, "EGMA": 0.20, "EG": 0.20, "AcOH": 0.40, "H2O": 51.5},
        {"EGDA": 0.50, "EGMA": 0.10, "EG": 0.05, "AcOH": 0.15, "H2O": 52.0},
    ]


def calibrate_nmr(acq: AcquisitionSettings, acquire,
                  rng_fit: np.random.Generator,
                  rng_check: np.random.Generator,
                  species: Sequence[str] = QUANTIFIED_SPECIES,
                  standards_fit: Optional[List[Dict[str, float]]] = None,
                  standards_check: Optional[List[Dict[str, float]]] = None,
                  n_rep_fit: int = 4, n_rep_check: int = 6,
                  level: float = 0.95) -> NMRCalibration:
    """Build the PUBLIC calibration artifact from prepared standards.

    Three INDEPENDENT datasets / RNG streams:

      DATASET 1 (rng_fit, standards_fit)     -> response factors, bias,
                                                residual correlation and the
                                                variance model (const + rel)
      DATASET 2 (rng_check, standards_check) -> the interval SCALE, from the
                                                empirical distribution of the
                                                standardized residuals
      DATASET 3 (validation.py, its own RNG) -> never touched here

    The scale is the per-species factor that makes the claimed intervals
    attain their nominal level on DATASET 2:

        q_i = quantile_level( |e_i| / sigma_i ) / z_level

    computed on the calibration-CHECK data only.  Tuning it on the final
    validation set would be circular and is not done."""
    fitter = SpectralFitter(acq, species)
    calibrate_responses(fitter, acquire, rng_fit,
                        standards=standards_fit, n_rep=n_rep_fit)
    emp = calibrate_empirical(fitter, acquire, rng_fit,
                              standards=standards_fit, n_rep=n_rep_fit)

    # ---- DATASET 2: scale the intervals on independent check standards --- #
    sp = tuple(fitter.species)
    n_s = len(sp)
    z_level = {0.95: 1.959964, 0.90: 1.644854}.get(level, 1.959964)
    ratios = {i: [] for i in range(n_s)}
    for std in (standards_check or _check_standards()):
        truth = np.array([std.get(s, 0.0) for s in sp])
        for _ in range(n_rep_check):
            ppm, y = acquire(std, rng_check)
            res = fitter.fit(ppm, y)
            sig = np.sqrt(np.maximum(np.diag(res.cov), 1e-300))
            err = res.conc_M - truth
            for i, s in enumerate(sp):
                if s in res.censored:        # one-sided/censored: excluded
                    continue                 # from the two-sided scale
                ratios[i].append(abs(err[i]) / sig[i])
    scale = np.ones(n_s)
    n_used = {}
    for i in range(n_s):
        r = np.asarray(ratios[i])
        n_used[sp[i]] = int(len(r))
        if len(r) >= 8:
            q = float(np.quantile(r, level)) / z_level
            scale[i] = float(np.clip(q, 1.0, 25.0))   # never SHRINK claimed
    return NMRCalibration(                            # uncertainty
        species=sp,
        response_factors=dict(fitter.response_correction),
        bias_M=np.asarray(emp["bias_M"], dtype=float),
        corr=np.asarray(emp["corr"], dtype=float),
        var_const_M2=np.asarray(emp["var_const_M2"], dtype=float),
        rel=np.asarray(emp["rel"], dtype=float),
        scale=scale,
        meta={"n_obs_fit": emp["n_obs"], "n_check_used": n_used,
              "level": level, "n_rep_fit": n_rep_fit,
              "n_rep_check": n_rep_check,
              "engine": acq.engine, "n_points": acq.n_points})


def calibrate_empirical(fitter: SpectralFitter, acquire, rng,
                        standards: Optional[List[Dict[str, float]]] = None,
                        n_rep: int = 4) -> Dict:
    """Standard-mixture calibration of the FULL error model - the simulation
    analogue of calibrating a real Fourier 80 against prepared standards.

    Runs AFTER calibrate_responses() (which removes the multiplicative
    response bias).  From the residuals on the CALIBRATION standards

        e = c_fitted - c_true

    it estimates the part of the error the single-spectrum fit Jacobian
    cannot see: a systematic bias vector and an inter-species residual
    COVARIANCE.  The fitter then reports

        c_corrected = c_fitted - bias
        Sigma_eff   = Sigma_spectral_fit + Sigma_empirical

    which is the simplest model that can fix an under-covering species
    (bias-dominated AcOH in the acetyl cluster) without inflating anything
    by hand.  Sigma_empirical is symmetrized and PSD-projected.

    Calibration standards are PREPARED compositions and therefore public
    knowledge - using them does not breach the truth firewall.  The
    VALIDATION compositions and their seeds must be independent (see
    validation.py)."""
    if standards is None:
        standards = _default_standards()
    n_s = len(fitter.species)
    res_rows, conc_rows = [], []
    for std in standards:
        truth = np.array([std.get(sp, 0.0) for sp in fitter.species])
        for _ in range(n_rep):
            ppm, y = acquire(std, rng)
            res = fitter.fit(ppm, y)
            res_rows.append(res.conc_M - truth)
            conc_rows.append(truth)
    E = np.asarray(res_rows)                       # (n_obs, n_species)
    C = np.asarray(conc_rows)                      # (n_obs, n_species)
    bias = E.mean(axis=0)
    dev = E - bias[None, :]
    cov = (dev.T @ dev) / max(len(E) - 1, 1)
    cov = 0.5 * (cov + cov.T)
    w, V = np.linalg.eigh(cov)                     # PSD projection
    cov = V @ np.diag(np.maximum(w, 0.0)) @ V.T

    # Composition dependence: a CONSTANT empirical covariance under-covers on
    # held-out reaction compositions (measured in validation.py suite B), so
    # the residual scale is split into a constant and a concentration-
    # proportional part, both REGRESSED from the calibration residuals -
    # sigma_i(c)^2 = v_const_i + (rel_i * c_i)^2 - and the inter-species
    # CORRELATION measured on the standards is preserved.  This is the
    # simplest model that held-out validation shows to be sufficient.
    sd = np.sqrt(np.maximum(np.diag(cov), 1e-300))
    corr = cov / np.outer(sd, sd)
    corr = np.clip(corr, -0.99, 0.99)
    np.fill_diagonal(corr, 1.0)
    rel = np.zeros(n_s)
    v_const = np.zeros(n_s)
    for i in range(n_s):
        e2 = dev[:, i] ** 2
        c2 = np.maximum(C[:, i], 0.0) ** 2
        # non-negative least squares on [1, c^2] -> v_const + rel^2 c^2
        A = np.stack([np.ones_like(c2), c2], axis=1)
        try:
            sol, *_ = np.linalg.lstsq(A, e2, rcond=None)
        except np.linalg.LinAlgError:
            sol = np.array([float(np.mean(e2)), 0.0])
        v_const[i] = max(float(sol[0]), 0.25 * float(np.mean(e2)))
        rel[i] = float(np.sqrt(max(float(sol[1]), 0.0)))
    fitter.empirical_bias = bias
    fitter.empirical_cov = cov              # constant part (back-compat)
    fitter.empirical_corr = corr
    fitter.empirical_var_const = v_const
    fitter.empirical_rel = rel
    return {"bias_M": bias, "cov_M2": cov, "corr": corr,
            "var_const_M2": v_const, "rel": rel, "n_obs": len(E),
            "species": fitter.species}


def _default_standards() -> List[Dict[str, float]]:
    """Prepared calibration mixtures: four single-species standards plus
    mixtures spanning the overlap-relevant composition range."""
    return [
        {"EGDA": 0.40, "EGMA": 0.0, "EG": 0.0, "AcOH": 0.0, "H2O": 53.0},
        {"EGDA": 0.0, "EGMA": 0.30, "EG": 0.0, "AcOH": 0.0, "H2O": 53.0},
        {"EGDA": 0.0, "EGMA": 0.0, "EG": 0.30, "AcOH": 0.0, "H2O": 53.0},
        {"EGDA": 0.0, "EGMA": 0.0, "EG": 0.0, "AcOH": 0.40, "H2O": 53.0},
        {"EGDA": 0.20, "EGMA": 0.10, "EG": 0.05, "AcOH": 0.15, "H2O": 52.0},
        {"EGDA": 0.35, "EGMA": 0.06, "EG": 0.02, "AcOH": 0.10, "H2O": 52.5},
        {"EGDA": 0.10, "EGMA": 0.18, "EG": 0.14, "AcOH": 0.45, "H2O": 51.0},
        {"EGDA": 0.02, "EGMA": 0.06, "EG": 0.30, "AcOH": 0.70, "H2O": 50.0},
    ]


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
        standards = _default_standards()
    fitter.response_correction = {}          # fit standards uncorrected
    fitter.empirical_bias = None             # and un-bias-corrected
    fitter.empirical_cov = None
    fitter.empirical_corr = None
    fitter.empirical_var_const = None
    fitter.empirical_rel = None
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
