"""
Advanced-layer demonstration campaign: Reacnostics CPR (one moving sampling
capillary) + Bruker Fourier 80 virtual instrument.

Runs a single-seed strategy-F campaign under realistic NMR + transport
physics next to a strategy-D baseline on the SAME virtual laboratory class,
and produces Figures A-D (spatial value, position decisions, spectra,
concentration recovery) plus the campaign history CSV.

IDE workflow: edit CONFIG below and press Run.  Everything needed for exact
reproduction (CONFIG + seeds) is written to <outdir>/config_used.json.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time

import numpy as np

from sdl import Layer1Bridge, build_candidates, build_fixed_design
from sdl_advanced import benchmark as bm
from sdl_advanced import reporting as rep
from sdl_advanced.bayes_design import NoiseSurrogate
from sdl_advanced.instrument import InstrumentConfig
from sdl_advanced.spatial_design import (SensitivityField, SpatialDesigner,
                                         fixed_equal_positions)
from sdl_advanced.spectral import NMRSimulator, SpectralNuisance
from sdl_advanced.spectral_fit import SpectralFitter

CONFIG = {
    "seed": 7,
    "budget": 6,                  # reactor conditions per strategy
    "scenario": "S3_transport",   # the full-physics demonstration
    "strategies": ["D", "F"],
    "outdir": "results_advanced_v2",   # v2: corrected framework outputs
    "n_recovery_mc": 120,         # Figure D Monte Carlo size
}


def resolve_outdir(outdir: str) -> str:
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              outdir)
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _figure_a(outdir: str) -> None:
    """True profile + equal vs optimized positions + information density."""
    spec = bm.SCENARIOS["S1_ideal"]
    lab = bm.make_lab(spec, seed=0)
    from sdl import OperatingConditions
    u = OperatingConditions(T_C=160.0, Q1_mL_min=0.25, Q2_mL_min=0.25,
                            C_EGDA_M=1.0, C_cat_M=1.0)   # curved profile
    bridge = Layer1Bridge(bm.GEOMETRY, bm.T_REF_C + 273.15,
                          activity_model="pitzer")
    L = lab.length_m
    z_prof = np.linspace(0.002, L, 120)
    flat = bridge.concentrations_at(bm.TRUTH, u, z_prof, bm.SPECIES)
    prof = {sp: flat[i * len(z_prof):(i + 1) * len(z_prof)]
            for i, sp in enumerate(bm.SPECIES)}

    from sdl import ParameterSpace, literature_guess
    space = ParameterSpace(t_ref_K=bm.T_REF_C + 273.15,
                           initial_guess=literature_guess(
                               bm.T_REF_C + 273.15))
    theta = space.to_vector(space.initial_guess)
    designer = SpatialDesigner(
        bm._spatial_cfg("optimized"), L,
        lambda y: bm.NOISE_DIRECT.covariance(y, bm.SPECIES, 1))

    def predict(th, z):
        return bridge.concentrations_at(space.to_natural(th), u, z,
                                        bm.SPECIES)

    field = SensitivityField(predict, theta, space.fd_steps,
                             designer.candidate_grid(), len(bm.SPECIES))
    p = space.n_params
    z_opt = designer.positions(field, np.zeros((p, p)))
    z_eq = fixed_equal_positions(L, bm.N_PORTS)
    info_z, info_g = designer.information_density(field, np.eye(p) * 1.0)
    rep.figure_a_spatial_value(z_prof, prof, z_eq, z_opt, info_z, info_g,
                               os.path.join(outdir, "figure_A_spatial.png"))


def _figure_d(outdir: str, n_mc: int, seed: int) -> None:
    """Truth vs deconvolved concentration over random compositions."""
    from sdl_advanced.spectral_fit import calibrate_responses
    rng = np.random.default_rng(seed)
    sim = NMRSimulator(bm.ACQ, bm.NMR_NUISANCE_TRUE)
    fitter = SpectralFitter(bm.ACQ)
    calibrate_responses(fitter, lambda s, r: sim.simulate(s, r)[:2], rng)
    truths, ests, sigs = [], [], []
    for _ in range(n_mc):
        c = {"EGDA": rng.uniform(0.0, 0.5), "EGMA": rng.uniform(0.0, 0.3),
             "EG": rng.uniform(0.0, 0.3), "AcOH": rng.uniform(0.0, 0.6),
             "H2O": rng.uniform(45.0, 55.0)}
        ppm, y, _ = sim.simulate(c, rng)
        res = fitter.fit(ppm, y)
        truths.append([c[sp] for sp in fitter.species])
        ests.append(res.conc_M)
        sigs.append(np.sqrt(np.diag(res.cov)))
    rep.figure_d_truth_vs_recovered(
        np.array(truths), np.array(ests), np.array(sigs), fitter.species,
        os.path.join(outdir, "figure_D_recovery.png"))


def main() -> None:
    cfg = CONFIG
    outdir = resolve_outdir(cfg["outdir"])
    spec = bm.SCENARIOS[cfg["scenario"]]
    t0 = time.time()

    print("=" * 74)
    print(f"Advanced campaign demo - scenario {spec.name}: "
          f"{spec.description}")
    print(f"  budget {cfg['budget']} conditions | strategies "
          f"{cfg['strategies']} | seed {cfg['seed']}")
    print("=" * 74)

    histories, results, labs = {}, {}, {}
    for strategy in cfg["strategies"]:
        print(f"\nStrategy {strategy}:")
        store = strategy.startswith("F")
        res, lab, extra = bm.run_one_campaign(
            spec, strategy, cfg["seed"], cfg["budget"], verbose=True,
            store_spectra=store)
        results[strategy], labs[strategy] = res, lab
        if hasattr(res, "history") and res.history and \
                hasattr(res.history[0], "z_positions"):
            histories[strategy] = res.history

    # ---- figures -------------------------------------------------------- #
    _figure_a(outdir)
    if histories:
        rep.figure_b_position_rounds(
            histories, labs[cfg["strategies"][0]].length_m,
            os.path.join(outdir, "figure_B_positions.png"))
    # Figure C from the first stored F-spectra
    for strategy in cfg["strategies"]:
        if not strategy.startswith("F"):
            continue
        for cm_meas in (results[strategy].ensemble.best.inference
                        .measurements):
            spectra = (cm_meas.meta or {}).get("spectra")
            if spectra:
                qc = cm_meas.meta["qc"]
                pick = list(range(min(3, len(spectra))))
                rep.figure_c_spectrum(
                    [spectra[i] for i in pick], [qc[i] for i in pick],
                    [cm_meas.z_m[i] for i in pick],
                    labs[strategy].length_m,
                    os.path.join(outdir, "figure_C_spectra.png"))
                break
        break
    _figure_d(outdir, cfg["n_recovery_mc"], cfg["seed"])

    # ---- reproducibility record ----------------------------------------- #
    with open(os.path.join(outdir, "config_used.json"), "w") as fh:
        json.dump({"CONFIG": cfg,
                   "scenario": dataclasses.asdict(spec),
                   "truth": bm.TRUTH, "geometry": bm.GEOMETRY,
                   "design": bm.DESIGN,
                   "nmr_nuisance_true": dataclasses.asdict(
                       bm.NMR_NUISANCE_TRUE),
                   "acquisition": dataclasses.asdict(bm.ACQ)},
                  fh, indent=2, default=str)
    print(f"\nDone in {time.time() - t0:.1f} s.  Outputs in: {outdir}")


if __name__ == "__main__":
    main()
