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
from .spectral_fit import SpectralFitter, calibrate_responses


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


def reachable_compositions(geometry: Dict[str, float], t_ref_K: float,
                           theta: Dict[str, float],
                           n_max: int = 30) -> List[Dict[str, float]]:
    """Suite B: Layer-1 compositions over realistic (T, Q, C_cat, z).
    `theta` is a DOCUMENTED nominal parameter set (e.g. the literature
    guess) - validation compositions need not and do not use hidden truth."""
    bridge = Layer1Bridge(geometry, t_ref_K, activity_model="pitzer")
    L = geometry["length_m"]
    species = ("EGDA", "EGMA", "EG", "AcOH", "H2O")
    out = []
    for T in (60.0, 110.0, 160.0):
        for q in (0.5, 2.0):
            for cat in (0.5, 1.0):
                u = OperatingConditions(T, q / 2, q / 2, 1.0, cat)
                z = np.array([0.2 * L, 0.6 * L, L])
                flat = bridge.concentrations_at(theta, u, z, species)
                for k in range(len(z)):
                    out.append({sp: float(flat[i * len(z) + k])
                                for i, sp in enumerate(species)})
    return out[:n_max]


def run_validation(acq: AcquisitionSettings, nuisance: SpectralNuisance,
                   geometry: Dict[str, float], t_ref_K: float,
                   theta_nominal: Dict[str, float], seed: int = 0,
                   n_stress: int = 25, n_rep: int = 3
                   ) -> Dict[str, Dict]:
    """The full quantification-validation report (suites A, B, FID)."""
    results: Dict[str, Dict] = {}

    def _make(engine: str):
        acq_e = dataclasses.replace(acq, engine=engine)
        rng = np.random.default_rng(seed)
        sim = NMRSimulator(acq_e, nuisance)
        fitter = SpectralFitter(acq_e)
        calibrate_responses(fitter,
                            lambda s, r: sim.simulate(s, r)[:2], rng)
        return sim, fitter, rng

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
