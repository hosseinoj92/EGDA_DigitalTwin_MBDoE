"""
Temperature sensitivity study of the PFR digital twin.

Sweeps the (isothermal) reactor temperature at otherwise fixed conditions,
reporting outlet conversion and yields, and overlaying the EGMA axial profile
at a few selected temperatures.  Both catalyst routes form the same series
network, so the outlet EGMA yield passes through a maximum: too cold ->
little conversion; too hot -> EGMA over-cleaves to EG.  On the H2SO4 route
the hot end additionally saturates at the chemical-equilibrium limit
(X_eq < 100%); on the NaOH route (saponification, ~1000x faster) the ceiling
is instead the stoichiometric NaOH supply when the base is sub-stoichiometric.

Outputs go into a hyperparameter-tagged folder under results/, with a CSV
paired to every figure plus the exact run configuration.

IDE workflow: edit the CONFIG dictionary below and press Run.
For many scenarios at once use `batch_temperature_study.py`, which reuses the
`run_sweep()` function defined here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from pfr_twin import (
    KineticModel, PFRResult, ReactorGeometry, SolverSettings, simulate_pfr,
    run_tag, resolve_root, make_run_dir, write_run_config, write_columns_csv,
)
from pfr_twin.plotting import plot_temperature_sweep, plot_profile_overlay

from run_simulation import build_inlet, build_kinetics

# ============================================================================
# CONFIG - all study parameters live here; edit and run.
# ============================================================================
CONFIG = {
    # ---- catalyst system -------------------------------------------------------
    # "H2SO4": reversible acid-catalyzed hydrolysis  |  "NaOH": saponification
    # (~1000x faster per mole of catalyst; OH- consumed stoichiometrically -
    # for NaOH consider a colder sweep window, e.g. 5-60 C, and note that the
    # conversion ceiling is min(1, NaOH / acetate groups), not equilibrium)
    "catalyst": "H2SO4",  # "H2SO4" or "NaOH"

    # ---- temperature sweep ---------------------------------------------------
    "T_min_C": 40.0,               # lowest temperature, deg C
    "T_max_C": 150.0,               # highest temperature, deg C
    "n_points": 27,                # number of sweep points

    # temperatures for the EGMA axial-profile overlay figure (max 4 recommended)
    "profile_temps_C": [40.0, 60, 80.0, 100, 120.0, 150.0, 180.0],

    # ---- feed stream 1: aqueous EGDA ----------------------------------------
    "stream1": {
        "Q_mL_min": 0.5,           # pump flow rate, mL/min
        "C_EGDA_M": 0.1,           # EGDA molarity, mol/L
        "density_g_L": 1005.0,     # solution density (for [H2O] and Re), g/L
    },

    # ---- feed stream 2: aqueous catalyst solution -----------------------------
    "stream2": {
        "Q_mL_min": 0.5,           # pump flow rate, mL/min
        "C_cat_M": 0.2,            # catalyst molarity (H2SO4 or NaOH), mol/L
        "density_g_L": 1060.0,     # solution density, g/L
                                   # (2 M H2SO4 ~ 1060; 2 M NaOH ~ 1080)
    },

    # ---- reactor geometry -----------------------------------------------------------
    "reactor": {
        "length_m": 0.0600,         # tube length, m         (lab PFR: 0.200 / 0.600)
        "diameter_m": 0.004,       # inner diameter, m      (lab PFR: 0.018 / 0.032)
    },

    # ---- catalyst speciation (H2SO4 route only) -------------------------------------
    "h_plus_model": "equilibrium",  # "equilibrium" (HSO4- Ka2) | "stoichiometric"
    "n_eff_protons": 1.0,           # protons per H2SO4 (stoichiometric model only)
    "ka2_model": "tdep",            # "tdep" (Ka2(T), Clarke-Glew) | "constant" (25 C)
    "activity_model": "dilute",     # "dilute" (gamma=1) | "pitzer" (PRS, molar acid)

    # ---- reverse reactions / chemical equilibrium (H2SO4 route only) -----------------
    "equilibrium": {
        "reversible": True,         # False = legacy irreversible pseudo-1st-order model
        "K1_ref": 0.50,             # (EGMA.AcOH)/(EGDA.H2O) at equilibrium, 25 C
        "dH1_kJ": 5.0,              # hydrolysis reaction enthalpy step 1, kJ/mol
        "K2_ref": 0.125,            # (EG.AcOH)/(EGMA.H2O) at equilibrium, 25 C
        "dH2_kJ": 5.0,              # hydrolysis reaction enthalpy step 2, kJ/mol
    },

    # ---- output ---------------------------------------------------------------------------
    "outdir": "results",            # relative paths resolve next to this script
}
# ============================================================================


# ---------------------------------------------------------------------------
# Reusable sweep machinery (also used by batch_temperature_study.py)
# ---------------------------------------------------------------------------
@dataclass
class SweepOutcome:
    """Everything one temperature sweep produces."""
    cfg: Dict
    T_C: np.ndarray
    X: np.ndarray
    Y_egma: np.ndarray
    Y_eg: np.ndarray
    overlay: List[PFRResult]
    inlet: object
    summary: Dict[str, float]
    run_dir: str = ""
    files: List[str] = field(default_factory=list)


def simulate_sweep(cfg: Dict) -> SweepOutcome:
    """Run the configured temperature sweep. Writes nothing.

    The inlet is re-mixed at every sweep temperature: the composition is
    T-independent, but the catalytic [H+] is not (bisulfate Ka2 falls
    steeply with temperature, and the Pitzer activity model is also
    T-dependent), so speciation must follow the sweep."""
    kinetics = build_kinetics(cfg)
    model = KineticModel(kinetics)
    geometry = ReactorGeometry(**cfg["reactor"])
    settings = SolverSettings()

    T_C = np.linspace(cfg["T_min_C"], cfg["T_max_C"], cfg["n_points"])
    X, Y_egma, Y_eg = (np.empty_like(T_C) for _ in range(3))
    inlet = last = None
    for i, t_c in enumerate(T_C):
        inlet = build_inlet(cfg, kinetics, t_c + 273.15)
        res = simulate_pfr(inlet, geometry, t_c + 273.15, model, settings)
        X[i] = res.conversion[-1]
        Y_egma[i] = res.yield_of("EGMA")[-1]
        Y_eg[i] = res.yield_of("EG")[-1]
        last = res

    overlay = [simulate_pfr(build_inlet(cfg, kinetics, t_c + 273.15),
                            geometry, t_c + 273.15, model, settings)
               for t_c in cfg["profile_temps_C"]]

    i_max = int(np.argmax(Y_egma))
    summary = {
        "X_at_T_min": float(X[0]), "X_at_T_max": float(X[-1]),
        "Y_EGMA_max": float(Y_egma[i_max]),
        "T_at_Y_EGMA_max_C": float(T_C[i_max]),
        "interior_optimum": bool(0 < i_max < len(T_C) - 1),
        "tau_s": float(last.residence_time_s),
    }
    if last.eq_conc is not None:
        summary["X_eq_at_T_max"] = float(
            1.0 - last.eq_conc["EGDA"] / inlet.conc["EGDA"])
    elif cfg["catalyst"] == "NaOH":
        summary["NaOH_per_acetate_group"] = float(
            inlet.conc["OH"] / (2.0 * inlet.conc["EGDA"] + inlet.conc["EGMA"]))

    return SweepOutcome(cfg=cfg, T_C=T_C, X=X, Y_egma=Y_egma, Y_eg=Y_eg,
                        overlay=overlay, inlet=inlet, summary=summary)


def write_sweep_outputs(outcome: SweepOutcome, run_dir: str) -> SweepOutcome:
    """Write both figures with their paired CSVs, the sweep table, and the
    exact run configuration into `run_dir`."""
    write_columns_csv(os.path.join(run_dir, "temperature_sweep.csv"),
                      {"T_C": outcome.T_C, "X_EGDA": outcome.X,
                       "Y_EGMA": outcome.Y_egma, "Y_EG": outcome.Y_eg},
                      fmt="%.6e")
    files = [
        plot_temperature_sweep(outcome.T_C, outcome.X, outcome.Y_egma,
                               outcome.Y_eg,
                               os.path.join(run_dir, "temperature_sweep.png")),
        plot_profile_overlay(outcome.overlay, "EGMA",
                             os.path.join(run_dir, "egma_profiles_vs_T.png")),
    ]
    write_run_config(run_dir, outcome.cfg, {"summary": outcome.summary})
    outcome.run_dir, outcome.files = run_dir, files
    return outcome


def summary_lines(outcome: SweepOutcome) -> List[str]:
    cfg, s = outcome.cfg, outcome.summary
    T_C = outcome.T_C
    lines = [f"Temperature sweep ({cfg['T_min_C']:.0f}-{cfg['T_max_C']:.0f} C, "
             f"{cfg['n_points']} points, catalyst {cfg['catalyst']}) complete.",
             f"  Outlet conversion : {s['X_at_T_min']:.1%} at {T_C[0]:.0f} C  ->  "
             f"{s['X_at_T_max']:.1%} at {T_C[-1]:.0f} C"]
    if "X_eq_at_T_max" in s:
        lines.append(f"  Equilibrium limit : X_eq = {s['X_eq_at_T_max']:.1%} at "
                     f"{T_C[-1]:.0f} C (reversible model: conversion saturates "
                     "below 100%)")
    elif "NaOH_per_acetate_group" in s:
        cap = s["NaOH_per_acetate_group"]
        lines.append(f"  Stoichiometric cap: NaOH / acetate groups = {cap:.2f} -> "
                     f"max acetate release = {min(1.0, cap):.1%} "
                     "(OH- is the limiting reagent when < 1)")
    if s["interior_optimum"]:
        lines.append(f"  EGMA yield maximum: {s['Y_EGMA_max']:.1%} at "
                     f"{s['T_at_Y_EGMA_max_C']:.1f} C "
                     "(series-reaction optimum inside the sweep window)")
    else:
        lines.append(f"  EGMA yield is monotonic over this window "
                     f"(max {s['Y_EGMA_max']:.1%} at the "
                     f"{s['T_at_Y_EGMA_max_C']:.0f} C end).")
    return lines


def run_sweep(cfg: Dict, root: str, *, prefix: str = "temperature_study",
              verbose: bool = True) -> SweepOutcome:
    """Run one temperature sweep and write its hyperparameter-tagged folder."""
    outcome = simulate_sweep(cfg)
    run_dir = make_run_dir(root, run_tag(cfg, prefix=prefix, sweep=True))
    write_sweep_outputs(outcome, run_dir)
    if verbose:
        print("\n".join(summary_lines(outcome)))
        print(f"Outputs written to: {run_dir}")
    return outcome


def main() -> None:
    root = resolve_root(CONFIG["outdir"], __file__)
    run_sweep(CONFIG, root)


if __name__ == "__main__":
    main()
