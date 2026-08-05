"""
Layer 2 showcase: virtual self-driving laboratory around the Layer 1 PFR twin.

Runs the four campaign strategies on the SAME hidden truth and budget:

    A  outlet only     + fixed design      C  outlet only     + MBDoE
    B  spatial profile + fixed design      D  spatial profile + MBDoE

and produces the comparison figures/report in results/.

IDE workflow: edit the CONFIG dictionary below and press Run.
Typical runtime with the default budget: ~1-3 minutes.
"""

from __future__ import annotations

import os
import time

import numpy as np

from sdl import (
    Layer1Bridge, OperatingConditions, ParameterSpace, NoiseModel,
    VirtualLaboratory, InferenceModel, MBDoESelector,
    build_candidates, build_fixed_design, literature_guess,
    param_keys_for, run_strategy, STRATEGY_DEFS,
    reference_design, screen,
)
from sdl.campaign import STRATEGY_NAMES
from sdl import reporting

# ============================================================================
# CONFIG - all campaign parameters live here; edit and run.
# ============================================================================
CONFIG = {
    "seed": 7,                      # master RNG seed (per-strategy offsets added)
    "budget": 10,                    # experiments allowed per strategy
    "strategies": ["A", "B", "C", "D"],
    "target_rel_ci_pct": None,      # e.g. 5.0 -> stop early when every 95% CI
                                    # is tighter than 5 %; None = use full budget

    # ---- catalyst system ------------------------------------------------------
    # "H2SO4": reversible acid hydrolysis, 6 estimated parameters (incl. Keqs)
    # "NaOH" : irreversible saponification, 4 estimated parameters, OH- is a
    #          consumable reagent (its molarity is a stoichiometric design axis)
    "catalyst": "H2SO4",

    # ---- hidden truth (used ONLY inside the virtual laboratory) --------------
    "truth": {
        "H2SO4": {
            "k1_ref": 1.00e-3,      # L/(mol s) at T_ref     (literature: 2.37e-3)
            "Ea1_kJ": 40,         # kJ/mol                 (literature: 55.0)
            "k2_ref": 6.50e-4,      # L/(mol s) at T_ref     (literature: 1.15e-3)
            "Ea2_kJ": 48.0,         # kJ/mol                 (literature: 57.0)
            "K1_ref": 0.90,         # hydrolysis Keq step 1 at T_ref (lit.: 0.62)
            "K2_ref": 0.07,         # hydrolysis Keq step 2 at T_ref (lit.: 0.15)
        },
        "NaOH": {
            "k1_ref": 2.20,         # L/(mol s) at T_ref     (literature: 1.58)
            "Ea1_kJ": 44.0,         # kJ/mol                 (literature: 46.0)
            "k2_ref": 0.60,         # L/(mol s) at T_ref     (literature: 0.77)
            "Ea2_kJ": 50.0,         # kJ/mol                 (literature: 48.0)
        },
    },

    # ---- synthetic CPR-NMR observation model -----------------------------------
    "measurement": {
        "species": ["EGDA", "EGMA", "EG", "AcOH"],   # quantified by NMR
        "n_ports": 10,               # equally spaced sampling ports (incl. outlet)
        "noise_true": {             # noise the virtual instrument actually adds
            "sigma_abs_M": 0.004,   # absolute floor, mol/L
            "sigma_rel": 0.02,      # relative peak-integration error
            "rho_overlap": 0.3,     # EGDA/EGMA acetyl-peak overlap correlation
        },
        "noise_assumed": {          # covariance the estimator assumes (default:
            "sigma_abs_M": 0.004,   # well-calibrated = same as noise_true)
            "sigma_rel": 0.02,
            "rho_overlap": 0.3,
        },
        # optional systematic effects in the TRUTH only (robustness studies):
        "transfer_time_s": 0.0,     # sample keeps reacting during transfer line
        "calibration_gain": {},     # e.g. {"EGMA": 1.03} = +3% bias on EGMA
    },

    # ---- reactor (Layer 1) -------------------------------------------------------
    "reactor": {
        "length_m": 0.06,          # matches the current Layer 1 base case
        "diameter_m": 0.004,
    },
    "h_plus_model": "equilibrium",
    "ka2_model": "tdep",            # bisulfate Ka2(T): "tdep" | "constant" (25 C)
    "activity_model": "pitzer",     # "dilute" | "pitzer" (concentrated acid)
    "reversible": True,             # H2SO4 route only (NaOH is always irreversible)
    "forward_engine": "ode",        # "ode" | "analytical" (acid irreversible only)

    # ---- estimation ------------------------------------------------------------------
    "t_ref_C": 60.0,                # reference T of the k_ref parameterization
                                    # (initial guess = Layer 1 literature kinetics)

    # ---- experiment design space (per catalyst) -------------------------------------------
    # NaOH saponification is ~1000x faster, so its window is colder, faster-
    # flowing, and includes the NaOH/acetate stoichiometric ratio as an axis.
    "design_space": {
        "H2SO4": {
            "T_C_levels": [40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160],  # MBDoE stream-1 levels
            "Q_total_mL_min_levels": [0.2, 0.4, 0.8, 1.0, 2.0, 4.0, 8.0],
            "C_cat_M_levels": [0.1, 0.5, 0.75, 1.0],   # MBDoE stream-2 levels
            "C_EGDA_M_levels": [0.1, 0.5, 0.75, 1.0],  # MBDoE stream-1 levels
            "C_EGDA_M": 1.0,        # fixed-design stream-1 molarity
            # User-validated admissible region for continuous refinement.
            # These limits constrain the optimizer; they are not a safety
            # certification by the software.
            "continuous_bounds": {
                "T_C": [30.0, 160.0],
                "Q_total_mL_min": [0.2, 8.0],
                "C_cat_M": [0.1, 1.0],
                "C_EGDA_M": [0.1, 1.0],
            },
            # conventional (fixed) campaign: temperature ladder at nominal settings
            "fixed_design_T_C": [40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160],
            "nominal_Q_total_mL_min": 1.0,
            "nominal_C_cat_M": 0.5,
        },
        "NaOH": {
            "T_C_levels": [10, 20, 30, 40, 50],
            "Q_total_mL_min_levels": [10.0, 20.0, 40.0],
            "C_cat_M_levels": [0.5, 1.0],   # mixed OH-/acetate ratio 0.5 / 1.0
            "C_EGDA_M_levels": [0.25, 0.50, 0.75],
            "C_EGDA_M": 0.5,        # fixed-design stream-1 molarity
            "continuous_bounds": {
                "T_C": [10.0, 50.0],
                "Q_total_mL_min": [10.0, 40.0],
                "C_cat_M": [0.5, 1.0],
                "C_EGDA_M": [0.25, 0.75],
            },
            "fixed_design_T_C": [40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160],
            "nominal_Q_total_mL_min": 20.0,
            "nominal_C_cat_M": 1.0,
        },
    },
    # ---- identifiability screen ---------------------------------------------
    # Before spending an experiment, build the FIM at the initial guess over
    # the corners+centre of the admissible box (an upper bound on what any
    # campaign inside those bounds could learn) and hold fixed any parameter
    # whose best achievable 95% CI still exceeds the threshold below.
    # On the acid route this removes K1_ref: with water at ~55 M, step 1 runs
    # effectively to completion and K1 leaves almost no signature, so
    # estimating it only buys a flat FIM direction and a parameter parked on
    # its box bound.  Set False to reproduce the old (unscreened) behaviour.
    "identifiability_screen": True,
    "identifiability_max_rel_ci_pct": 200.0,

    "mbdoe_criterion": "D",         # "D" | "A"
    # False: choose the best point on the grid above.
    # True : screen the grid, then continuously refine the best point inside
    #        continuous_bounds.  Applies only to autonomous strategies C/D.
    "continuous_design": True,
    "continuous_maxiter": 30,

    # ---- validation figure (per catalyst) ---------------------------------------------------
    "validation_condition": {
        "H2SO4": {"T_C": 160.0, "Q_total_mL_min": 0.5,
                   "C_EGDA_M": 1.0, "C_cat_M": 1.0},
        "NaOH": {"T_C": 30.0, "Q_total_mL_min": 20.0,
                  "C_EGDA_M": 0.5, "C_cat_M": 1.0},
    },

    # ---- output ------------------------------------------------------------------------------
    "outdir": "results",            # relative paths resolve next to this script
}
# ============================================================================


def resolve_outdir(outdir: str) -> str:
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), outdir)
    os.makedirs(outdir, exist_ok=True)
    return outdir


def main() -> None:
    cfg = CONFIG
    outdir = resolve_outdir(cfg["outdir"])
    t_ref_K = cfg["t_ref_C"] + 273.15
    catalyst = cfg["catalyst"]
    mcfg, dcfg = cfg["measurement"], cfg["design_space"][catalyst]

    bridge = Layer1Bridge(cfg["reactor"], t_ref_K,
                          h_plus_model=cfg["h_plus_model"],
                          engine=cfg["forward_engine"],
                          reversible=cfg["reversible"],
                          catalyst=catalyst,
                          ka2_model=cfg.get("ka2_model", "tdep"),
                          activity_model=cfg.get("activity_model", "dilute"))
    L = bridge.geometry.length_m
    ports = L * np.arange(1, mcfg["n_ports"] + 1) / mcfg["n_ports"]
    species = tuple(mcfg["species"])

    tcfg = cfg["truth"][catalyst]
    theta_true = {"k1_ref": tcfg["k1_ref"], "Ea1_J": tcfg["Ea1_kJ"] * 1e3,
                  "k2_ref": tcfg["k2_ref"], "Ea2_J": tcfg["Ea2_kJ"] * 1e3}
    if catalyst == "H2SO4":
        theta_true["K1_ref"] = tcfg["K1_ref"]
        theta_true["K2_ref"] = tcfg["K2_ref"]

    candidates = build_candidates(dcfg)
    # subsample (not truncate) the declared ladder to the budget, so the
    # conventional baseline spans the same box the autonomous strategies see
    fixed_design = build_fixed_design(dcfg, budget=cfg["budget"])
    guess = literature_guess(t_ref_K, catalyst)
    pkeys = param_keys_for(catalyst)

    print("=" * 74)
    print(f"Virtual self-driving laboratory - campaign comparison "
          f"[catalyst: {catalyst}]")
    print(f"  budget {cfg['budget']} experiments/strategy | "
          f"{len(candidates)} MBDoE candidates | "
          f"{mcfg['n_ports']} ports x {len(species)} species | "
          f"{len(pkeys)} parameters")
    print("  autonomous design: "
          + ("coarse grid + bounded continuous refinement"
             if cfg["continuous_design"] else "coarse candidate grid"))
    guess_txt = (f"k1_ref={guess['k1_ref']:.3e}, Ea1={guess['Ea1_J'] / 1e3:.1f} kJ, "
                 f"k2_ref={guess['k2_ref']:.3e}, Ea2={guess['Ea2_J'] / 1e3:.1f} kJ")
    if catalyst == "H2SO4":
        guess_txt += (f", K1_ref={guess['K1_ref']:.3f}, "
                      f"K2_ref={guess['K2_ref']:.3f}")
    print(f"  initial guess (literature): {guess_txt}")
    print("=" * 74)

    # ---- identifiability screen (before any experiment is spent) ------------
    base_space = ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess),
                                param_keys=pkeys)
    screen_lines = None
    if cfg.get("identifiability_screen", True):
        # screen with the most informative observation mode in play, so the
        # verdict is "can this platform identify it at all", and every
        # strategy keeps the SAME theta (the comparison stays like-for-like)
        z_screen = (ports if any(STRATEGY_DEFS[k][0] for k in cfg["strategies"])
                    else np.array([L]))
        t_screen = time.time()
        sr = screen(base_space, bridge, NoiseModel(**mcfg["noise_assumed"]),
                    list(candidates) + reference_design(dcfg), z_screen,
                    species, budget=cfg["budget"],
                    max_rel_ci_pct=cfg["identifiability_max_rel_ci_pct"])
        screen_lines = sr.summary_lines(cfg["identifiability_max_rel_ci_pct"])
        base_space = sr.space
        print("\n".join(screen_lines))
        print(f"  ({time.time() - t_screen:.1f} s)")
        print("=" * 74)
    pkeys = base_space.param_keys

    results, labs = {}, {}
    t0 = time.time()
    for idx, key in enumerate(cfg["strategies"]):
        spatial, autonomous = STRATEGY_DEFS[key]
        print(f"\nStrategy {key} ({STRATEGY_NAMES[key]}):")
        lab = VirtualLaboratory(
            theta_true, bridge, NoiseModel(**mcfg["noise_true"]),
            ports, species, seed=cfg["seed"] + idx,
            transfer_time_s=mcfg["transfer_time_s"],
            calibration_gain=mcfg["calibration_gain"])
        space = ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess),
                               param_keys=pkeys, fixed=dict(base_space.fixed))
        inference = InferenceModel(space, bridge,
                                   NoiseModel(**mcfg["noise_assumed"]))
        selector = MBDoESelector(
            inference=inference, candidates=candidates, spatial=spatial,
            ports_z_m=ports, outlet_z_m=np.array([L]), species=species,
            criterion=cfg["mbdoe_criterion"],
            continuous=cfg["continuous_design"],
            continuous_bounds=dcfg.get("continuous_bounds"),
            continuous_maxiter=cfg["continuous_maxiter"]) if autonomous else None
        results[key] = run_strategy(
            key, lab, inference, fixed_design, selector,
            budget=cfg["budget"], target_rel_ci_pct=cfg["target_rel_ci_pct"])
        labs[key] = lab
    print(f"\nAll campaigns finished in {time.time() - t0:.1f} s.")

    # ---- post-campaign benchmarking (truth revealed only here) --------------
    truth = labs[cfg["strategies"][0]].reveal_truth()
    vcfg = cfg["validation_condition"][catalyst]
    u_val = OperatingConditions(
        T_C=vcfg["T_C"], Q1_mL_min=vcfg["Q_total_mL_min"] / 2.0,
        Q2_mL_min=vcfg["Q_total_mL_min"] / 2.0,
        C_EGDA_M=vcfg.get("C_EGDA_M", dcfg["C_EGDA_M"]),
        C_cat_M=vcfg["C_cat_M"])
    # rank on the geometric-mean error over identifiable, unpinned components
    best_key = min(results,
                   key=lambda k: reporting.campaign_score_pct(results[k], truth))

    reporting.plot_error_convergence(
        results, truth, os.path.join(outdir, "convergence_error.png"))
    reporting.plot_uncertainty_convergence(
        results, os.path.join(outdir, "convergence_uncertainty.png"))
    reporting.plot_final_estimates(
        results, truth, os.path.join(outdir, "final_estimates.png"))
    reporting.plot_validation_profiles(
        bridge, truth, results[best_key], u_val,
        os.path.join(outdir, "validation_profiles.png"))
    reporting.write_history_csv(
        results, truth, os.path.join(outdir, "campaign_history.csv"))
    lab_stats = {"experiments": sum(l.n_experiments_run for l in labs.values()),
                 "reveals": sum(l.n_truth_reveals for l in labs.values())}
    text = reporting.write_final_report(
        results, truth, lab_stats, os.path.join(outdir, "final_report.txt"),
        screen_lines=screen_lines)
    print("\n" + text)
    print(f"Outputs written to: {outdir}")


if __name__ == "__main__":
    main()
