"""
NMR quantification validation (bias / RMSE / interval coverage), run OUTSIDE
the campaign loop and reported honestly - including where coverage is poor.

Two composition suites:

  A. "synthetic mixture stress test" - independent random compositions
     spanning the SPECTRAL space.  These are NOT all physically reachable
     EGDA reaction states; they stress the deconvolution (overlap, low
     concentrations, active bounds) beyond what the chemistry produces.

  B. "reachable reaction compositions" - Layer-1 profiles over a grid of
     realistic (T, Q, C_cat, z), i.e. exactly the states the campaign will
     meet (mass-balance-consistent, water-dominated).

Both run against the REALISTIC truth simulator (with all truth-model
mismatch effects enabled: pseudo-Voigt shapes, J mismatch, static shift
miscalibration, AR(1) noise, cubic baseline), after the same per-species
response calibration a real Fourier-80 campaign would perform.  A third
suite repeats a subset with the FID engine as truth ("FID truth ->
FFT/spectrum -> approximate analytic fitter"), so at least one validation
pathway is free of shared spectral physics between simulator and fitter.

Censored/bound cases: a species whose non-negativity bound is active is
counted separately ('censored'); its symmetric Gaussian interval is known to
be unreliable and its coverage is reported for the one-sided interval
[0, q95] instead - not silently mixed into the headline numbers.
"""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Sequence

import numpy as np

from sdl import Layer1Bridge, OperatingConditions

from .spectral import AcquisitionSettings, NMRSimulator, SpectralNuisance
from .spectral_fit import SpectralFitter, calibrate_nmr


def _suite(fitter: SpectralFitter, sim: NMRSimulator,
           compositions: List[Dict[str, float]], rng, n_rep: int = 4
           ) -> Dict[str, Dict[str, float]]:
    """Fit n_rep spectra per composition; per-species metrics with censored
    cases separated."""
    from scipy import stats
    n_s = len(fitter.species)
    errs = {sp: [] for sp in fitter.species}
    sigs = {sp: [] for sp in fitter.species}
    hits = {sp: 0 for sp in fitter.species}
    n_reg = {sp: 0 for sp in fitter.species}
    cens_hits = {sp: 0 for sp in fitter.species}
    n_cens = {sp: 0 for sp in fitter.species}
    for comp in compositions:
        truth = np.array([comp.get(sp, 0.0) for sp in fitter.species])
        for _ in range(n_rep):
            ppm, y, _ = sim.simulate(comp, rng)
            res = fitter.fit(ppm, y)
            sig = np.sqrt(np.diag(res.cov))
            for i, sp in enumerate(fitter.species):
                e = float(res.conc_M[i] - truth[i])
                errs[sp].append(e)
                sigs[sp].append(float(sig[i]))
                if sp in res.censored:
                    # one-sided interval [0, mu + 1.645 sigma]
                    n_cens[sp] += 1
                    if truth[i] <= res.conc_M[i] + 1.645 * sig[i]:
                        cens_hits[sp] += 1
                else:
                    n_reg[sp] += 1
                    if abs(e) <= 1.96 * sig[i]:
                        hits[sp] += 1
    out = {}
    for sp in fitter.species:
        e = np.asarray(errs[sp])
        out[sp] = {
            "bias_mM": float(np.mean(e)) * 1e3,
            "rmse_mM": float(np.sqrt(np.mean(e ** 2))) * 1e3,
            "mean_claimed_sigma_mM": float(np.mean(sigs[sp])) * 1e3,
            "coverage95": (hits[sp] / n_reg[sp] if n_reg[sp] else np.nan),
            "n": n_reg[sp],
            "coverage95_censored": (cens_hits[sp] / n_cens[sp]
                                    if n_cens[sp] else np.nan),
            "n_censored": n_cens[sp],
        }
    return out


def stress_compositions(rng, n: int = 30) -> List[Dict[str, float]]:
    """Suite A: independent random mixtures (SPECTRAL stress test - not all
    physically reachable reaction states), incl. deliberate low-conc/zero
    species to exercise the non-negativity bounds."""
    out = []
    for _ in range(n):
        c = {"EGDA": rng.uniform(0.0, 0.5), "EGMA": rng.uniform(0.0, 0.3),
             "EG": rng.uniform(0.0, 0.3), "AcOH": rng.uniform(0.0, 0.6),
             "H2O": rng.uniform(45.0, 55.0)}
        if rng.uniform() < 0.3:            # force a hard zero/near-zero case
            c[rng.choice(["EGMA", "EG", "AcOH"])] = float(
                rng.uniform(0.0, 0.004))
        out.append(c)
    return out


#: axial fractions of the reactor length sampled by the control/validation
#: composition sets - spanning inlet to outlet, i.e. unreacted feed to the
#: most converted state the campaign can produce
_CONTROL_Z_FRACTIONS = (0.05, 0.2, 0.4, 0.7, 1.0)


def reachable_compositions(geometry: Dict[str, float], t_ref_K: float,
                           theta: Dict[str, float],
                           n_max: int = 30,
                           design: Optional[Dict] = None,
                           stride: int = 1) -> List[Dict[str, float]]:
    """Layer-1 compositions over the operating envelope the campaign can
    actually command.

    `theta` is a DOCUMENTED nominal parameter set (e.g. the literature
    guess) - validation compositions need not and do not use hidden truth.

    WHY `design` MATTERS.  These compositions are the control data from
    which the governor's systematic allowance kappa is derived, so they have
    to span what the campaign will meet.  The original hard-coded corners
    (3 temperatures x 2 flows x 2 acid levels x 3 positions, EGDA feed fixed
    at 1 M) were a subset of the V6 design space, which reaches four EGDA
    and four acid levels; deriving an allowance on a subset and applying it
    on the whole space under-states it.  Passing the DECLARED design makes
    the control set follow the design space automatically.  With
    `design=None` the historical corner set is reproduced exactly."""
    bridge = Layer1Bridge(geometry, t_ref_K, activity_model="pitzer")
    L = geometry["length_m"]
    species = ("EGDA", "EGMA", "EG", "AcOH", "H2O")
    if design is None:
        temps, flows = (60.0, 110.0, 160.0), (0.5, 2.0)
        cats, egdas = (0.5, 1.0), (1.0,)
        z_frac = (0.2, 0.6, 1.0)
    else:
        # corners plus interior of every declared design dimension: the
        # composition extremes live at the corners, the overlap-worst states
        # in between
        t_lev = sorted(float(t) for t in design["T_C_levels"])
        temps = tuple(t_lev[:: max(len(t_lev) // 4, 1)] or t_lev)
        flows = tuple(sorted(float(q) for q in
                             design["Q_total_mL_min_levels"]))
        c_lev = sorted(float(c) for c in design["C_cat_M_levels"])
        cats = (c_lev[0], c_lev[-1]) if len(c_lev) > 1 else tuple(c_lev)
        e_lev = sorted(float(c) for c in design["C_EGDA_M_levels"])
        egdas = (e_lev[0], e_lev[-1]) if len(e_lev) > 1 else tuple(e_lev)
        z_frac = _CONTROL_Z_FRACTIONS
    out = []
    z = np.array([f * L for f in z_frac])
    for T in temps:
        for q in flows:
            for cat in cats:
                for ce in egdas:
                    u = OperatingConditions(float(T), q / 2, q / 2,
                                            float(ce), float(cat))
                    flat = bridge.concentrations_at(theta, u, z, species)
                    for k in range(len(z)):
                        out.append({sp: float(flat[i * len(z) + k])
                                    for i, sp in enumerate(species)})
    out = out[::max(int(stride), 1)]
    return out[:n_max] if n_max else out


def run_validation(acq: AcquisitionSettings, nuisance: SpectralNuisance,
                   geometry: Dict[str, float], t_ref_K: float,
                   theta_nominal: Dict[str, float], seed: int = 0,
                   n_stress: int = 25, n_rep: int = 3
                   ) -> Dict[str, Dict]:
    """The full quantification-validation report (suites A, B, FID)."""
    results: Dict[str, Dict] = {}

    def _make(engine: str):
        """Fitter calibrated on CALIBRATION spectra (own RNG stream) and
        returned with an INDEPENDENT validation RNG - calibration data and
        validation data never share a seed."""
        acq_e = dataclasses.replace(acq, engine=engine)
        sim = NMRSimulator(acq_e, nuisance)
        acquire = lambda s, r: sim.simulate(s, r)[:2]
        # DATASET 1 (fit) / DATASET 2 (check) / DATASET 3 (validation):
        # three INDEPENDENT RNG streams; the validation stream is never
        # used for any fitting or scaling
        cal = calibrate_nmr(acq_e, acquire,
                            rng_fit=np.random.default_rng(seed + 900_001),
                            rng_check=np.random.default_rng(seed + 800_002))
        fitter = SpectralFitter(acq_e)
        fitter.apply_calibration(cal)
        val_rng = np.random.default_rng(seed + 12_345)      # DATASET 3
        return sim, fitter, val_rng

    # A. stress suite (analytic truth engine, fast)
    sim, fitter, rng = _make("analytic")
    results["A_stress_synthetic_mixtures"] = _suite(
        fitter, sim, stress_compositions(rng, n_stress), rng, n_rep)

    # B. reachable reaction compositions
    sim, fitter, rng = _make("analytic")
    comps = reachable_compositions(geometry, t_ref_K, theta_nominal)
    results["B_reachable_reaction_states"] = _suite(fitter, sim, comps, rng,
                                                    n_rep)

    # C. FID-truth validation: FID engine generates the truth spectra; the
    # SAME approximate analytic-basis fitter quantifies them (no shared
    # frequency-domain shortcut between truth and analysis)
    sim, fitter, rng = _make("fid")
    results["C_fid_truth"] = _suite(
        fitter, sim, stress_compositions(rng, max(n_stress // 2, 8)), rng,
        max(n_rep - 1, 2))
    return results


def validation_rows(results: Dict[str, Dict]) -> List[Dict]:
    rows = []
    for suite, per_sp in results.items():
        for sp, m in per_sp.items():
            rows.append({"suite": suite, "species": sp, **m})
    return rows


def derive_systematic_allowance(acq, nuisance, geometry, t_ref_K,
                                theta_nominal, seed: int = 0,
                                n_rep: int = 3,
                                design: Optional[Dict] = None,
                                n_control: int = 80,
                                stride: int = 3) -> Dict:
    """Derive the governor's residual systematic allowance kappa from
    WELL-SPECIFIED CONTROL data - never from kinetic-benchmark performance.

    Quantifies NMR compositions of known (prepared) content through the
    calibrated pathway on a CONTROL RNG stream that is independent of the
    calibration-fit, calibration-check and final-validation streams, and
    measures the standardized residual z = (c_hat - c_true) / sigma_claimed.

    If the covariance were perfect, rms(z) = 1.  Any excess is a bounded
    measurement systematic that survives calibration (here: composition-
    dependent residual bias in the overlapped resonances), so

        kappa = sqrt( max(rms(z)^2 - 1, 0) )

    is the allowance the adequacy governor must grant the MEASUREMENT model
    before attributing residuals to KINETIC model error.

    THE CONTROL SET MUST MATCH THE OPERATING ENVELOPE.  kappa is a property
    of the measurement pathway AT THE COMPOSITIONS IT WILL MEASURE; deriving
    it on a narrow corner of the design space and applying it across the
    whole space under-states it, which is what produced the 57.5 %
    false-inadequacy rate.  Passing the declared `design` walks the control
    set over the full envelope; `design=None` reproduces the historical
    corner set."""
    from .spectral_fit import SpectralFitter, calibrate_nmr
    sim = NMRSimulator(acq, nuisance)
    acquire = lambda s, r: sim.simulate(s, r)[:2]
    cal = calibrate_nmr(acq, acquire,
                        rng_fit=np.random.default_rng(seed + 900_001),
                        rng_check=np.random.default_rng(seed + 800_002))
    fitter = SpectralFitter(acq)
    fitter.apply_calibration(cal)
    rng = np.random.default_rng(seed + 700_003)        # CONTROL stream
    comps = reachable_compositions(geometry, t_ref_K, theta_nominal,
                                   n_max=(n_control if design is not None
                                          else 30),
                                   design=design,
                                   stride=(stride if design is not None
                                           else 1))
    Z = []
    for c in comps:
        for _ in range(n_rep):
            ppm, y, _ = sim.simulate(c, rng)
            res = fitter.fit(ppm, y)
            truth = np.array([c.get(s, 0.0) for s in res.species])
            sig = np.sqrt(np.maximum(np.diag(res.cov), 1e-300))
            Z.append((res.conc_M - truth) / sig)
    Z = np.asarray(Z)
    rms = float(np.sqrt(np.mean(Z ** 2)))
    span = {sp: [float(min(c.get(sp, 0.0) for c in comps)),
                 float(max(c.get(sp, 0.0) for c in comps))]
            for sp in fitter.species}
    return {"rms_z": rms,
            "kappa": float(np.sqrt(max(rms ** 2 - 1.0, 0.0))),
            "z_std_by_species": Z.std(axis=0).tolist(),
            "z_mean_by_species": Z.mean(axis=0).tolist(),
            "species": list(fitter.species), "n_obs": int(len(Z)),
            "n_control_compositions": int(len(comps)),
            "control_span_M": span,
            "design_spanning": bool(design is not None)}
