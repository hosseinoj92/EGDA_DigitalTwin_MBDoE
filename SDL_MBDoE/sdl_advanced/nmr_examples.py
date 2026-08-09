"""
Three deterministic representative NMR examples for the publication figures.

WHEN THIS RUNS AND WHY IT MATTERS: after the benchmark has finished, in its
own process, from its own fixed generator (`EXAMPLE_SEED`).  It therefore
consumes no campaign RNG and cannot shift a single kinetic result.  It is
also why these spectra are *representative* rather than *sampled from a
campaign*: pulling a stored spectrum out of a campaign would either require
carrying every spectrum through the run (large, and it changes what the
worker returns) or re-simulating inside a seeded stream (which would move
it).  Generating them separately keeps both the campaign and the figure
reproducible, independently.

The three compositions span the regimes the deconvolution actually has to
cope with, and are stated as fixed mixtures rather than "whatever round 3
produced", so the figure means the same thing in every run:

    low            early conversion - EGDA dominant, product peaks small and
                   sitting on the shoulder of a much larger neighbour
    intermediate   the OVERLAP-RICH case: EGDA, EGMA and EG all present at
                   comparable levels, which is where the acetyl-region
                   correlation that drives the EGMA/AcOH bias is worst
    high           near-complete conversion - EGDA nearly gone, so its
                   estimate is a small difference of large fitted areas and
                   the non-negativity bound starts to bite

Each example writes the ppm axis, the observed (noisy) spectrum, the fitted
spectrum, the residual, and the individual fitted species components.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .spectral import AcquisitionSettings, NMRSimulator, SpectralNuisance
from .spectral_fit import SpectralFitter, calibrate_nmr

#: fixed and independent of every campaign seed (see module docstring)
EXAMPLE_SEED = 20_260_809

EXAMPLES: Dict[str, Dict[str, float]] = {
    "low_conversion": {"EGDA": 0.90, "EGMA": 0.07, "EG": 0.01,
                       "AcOH": 0.09, "H2O": 52.0},
    "intermediate_overlap": {"EGDA": 0.34, "EGMA": 0.33, "EG": 0.30,
                             "AcOH": 0.93, "H2O": 52.0},
    "high_conversion": {"EGDA": 0.04, "EGMA": 0.11, "EG": 0.83,
                        "AcOH": 1.72, "H2O": 52.0},
}


def _species_components(fitter: SpectralFitter, res) -> Dict[str, np.ndarray]:
    """Per-species (plus pool and baseline) contribution to the FITTED
    spectrum.  Delegates to the fitter's own reporting helper, which
    rebuilds the decomposition from the stored fit and refits nothing."""
    return fitter.component_spectra(res)


def generate(acq: AcquisitionSettings, nuisance: SpectralNuisance,
             outdir: str, seed: int = EXAMPLE_SEED) -> List[Dict]:
    """Simulate, deconvolve and export the three examples.

    Returns one summary row per example; writes one CSV per example."""
    os.makedirs(outdir, exist_ok=True)
    rng_cal = np.random.default_rng(seed + 900_001)
    rng_chk = np.random.default_rng(seed + 800_002)
    sim = NMRSimulator(acq, nuisance)
    cal = calibrate_nmr(acq, lambda s, r: sim.simulate(s, r)[:2],
                        rng_fit=rng_cal, rng_check=rng_chk)
    fitter = SpectralFitter(acq)
    fitter.apply_calibration(cal)

    summary: List[Dict] = []
    for n, (name, comp) in enumerate(EXAMPLES.items()):
        rng = np.random.default_rng(seed + 1000 * (n + 1))
        ppm, obs, _realized = sim.simulate(comp, rng)
        res = fitter.fit(ppm, obs)
        comps = _species_components(fitter, res)
        path = os.path.join(outdir, f"nmr_example_{name}.csv")
        header = ["ppm", "observed", "fitted", "residual"] + \
                 [f"component_{sp}" for sp in comps]
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(",".join(header) + "\n")
            for k in range(len(ppm)):
                vals = [ppm[k], obs[k], res.fitted[k], res.residual[k]]
                vals += [comps[sp][k] for sp in comps]
                fh.write(",".join(f"{v:.6g}" for v in vals) + "\n")
        for i, sp in enumerate(res.species):
            summary.append({
                "example": name, "species": sp,
                "c_true_M": float(comp.get(sp, 0.0)),
                "c_fitted_M": float(res.conc_M[i]),
                "sigma_M": float(np.sqrt(max(res.cov[i, i], 0.0))),
                "residual_M": float(res.conc_M[i] - comp.get(sp, 0.0)),
                "censored": int(sp in res.censored),
                "residual_rms": float(res.residual_rms),
                "fit_condition_number": float(res.condition_number),
                "qc_flags": ";".join(res.qc_flags),
                "example_seed": int(seed),
            })
        summary.append({"example": name, "species": "_spectrum_csv",
                        "c_true_M": float("nan"),
                        "c_fitted_M": float("nan"), "sigma_M": float("nan"),
                        "residual_M": float("nan"), "censored": 0,
                        "residual_rms": float(res.residual_rms),
                        "fit_condition_number": float(res.condition_number),
                        "qc_flags": os.path.basename(path),
                        "example_seed": int(seed)})
    return summary


def spectra_for_plot(acq: AcquisitionSettings, nuisance: SpectralNuisance,
                     seed: int = EXAMPLE_SEED
                     ) -> List[Tuple[str, np.ndarray, np.ndarray, np.ndarray,
                                     np.ndarray, Dict[str, np.ndarray]]]:
    """(label, ppm, observed, fitted, residual, components) per example."""
    rng_cal = np.random.default_rng(seed + 900_001)
    rng_chk = np.random.default_rng(seed + 800_002)
    sim = NMRSimulator(acq, nuisance)
    cal = calibrate_nmr(acq, lambda s, r: sim.simulate(s, r)[:2],
                        rng_fit=rng_cal, rng_check=rng_chk)
    fitter = SpectralFitter(acq)
    fitter.apply_calibration(cal)
    out = []
    for n, (name, comp) in enumerate(EXAMPLES.items()):
        rng = np.random.default_rng(seed + 1000 * (n + 1))
        ppm, obs, _r = sim.simulate(comp, rng)
        res = fitter.fit(ppm, obs)
        out.append((name, ppm, obs, res.fitted, res.residual,
                    _species_components(fitter, res)))
    return out
