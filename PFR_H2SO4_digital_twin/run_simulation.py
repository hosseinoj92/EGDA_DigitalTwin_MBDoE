"""
Base-case run of the PFR digital twin (selectable catalyst system).

Pipeline:  feed streams -> ideal micromixer -> isothermal 1D PFR
           -> catalyst-specific verification:
              H2SO4 : (1) integrator vs the closed-form solution in the
                      exactly linear irreversible limit, and (2) reversible
                      physics - conservation of the linear invariants along
                      x plus thermodynamic consistency (net rates vanish at
                      the coupled-equilibrium composition, outlet Q/K
                      reported);
              NaOH  : (1) cross-solver check (LSODA vs Radau - saponification
                      with depleting OH- has no closed form), and (2) the
                      saponification invariants (backbone, acetate groups,
                      OH- + acetate, constant water)
           -> figures + a paired CSV per figure + summary + run_config.json,
              all inside a hyperparameter-tagged folder under results/

IDE workflow: edit the CONFIG dictionary below and press Run.
For many scenarios at once use `batch_simulation.py`, which reuses the
`run_case()` function defined here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from pfr_twin import (
    EquilibriumStep, KineticParameters, KineticModel, PFRResult, ReactorGeometry,
    SolverSettings, Stream, mix_streams, simulate_pfr, default_kinetics,
    analytical_profiles, reaction_quotients, flow_diagnostics,
    run_tag, resolve_root, make_run_dir, write_run_config,
)
from pfr_twin.analytical import max_relative_error
from pfr_twin.parameters import SPECIES
from pfr_twin.plotting import (
    plot_concentration_profiles, plot_conversion_yield, plot_validation,
)

# ============================================================================
# CONFIG - all study parameters live here; edit and run.
# ============================================================================
CONFIG = {
    # ---- catalyst system -----------------------------------------------------
    # "H2SO4": reversible acid-catalyzed hydrolysis ([H+] constant, true catalyst)
    # "NaOH" : irreversible saponification (~1000x faster per mole; OH- is a
    #          stoichiometric reagent consumed 1:1 with acetate released)
    "catalyst": "H2SO4",  # "H2SO4" or "NaOH"

    # ---- reactor operating temperature -------------------------------------
    "temp_C": 150.0,                # isothermal reactor temperature, deg C

    # ---- feed stream 1: aqueous EGDA ----------------------------------------
    "stream1": {
        "Q_mL_min": 0.5,           # pump flow rate, mL/min
        "C_EGDA_M": 0.5,           # EGDA molarity, mol/L
        "density_g_L": 1005.0,     # solution density (for [H2O] and Re), g/L
    },

    # ---- feed stream 2: aqueous catalyst solution -----------------------------
    "stream2": {
        "Q_mL_min": 0.5,           # pump flow rate, mL/min
        "C_cat_M": 1.5,            # catalyst molarity (H2SO4 or NaOH), mol/L
        "density_g_L": 1060.0,     # solution density, g/L
                                   # (2 M H2SO4 ~ 1060; 2 M NaOH ~ 1080)
    },

    # ---- reactor geometry ------------------------------------------------------
    "reactor": {
        "length_m": 0.0600,         # tube length, m         (lab PFR: 0.200 / 0.600)
        "diameter_m": 0.004,       # inner diameter, m      (lab PFR: 0.018 / 0.032)
    },

    # ---- catalyst speciation (H2SO4 route only) -----------------------------------
    "h_plus_model": "equilibrium",  # "equilibrium" (HSO4- Ka2) | "stoichiometric"
    "n_eff_protons": 1.0,           # protons per H2SO4 (stoichiometric model only)
    "ka2_model": "tdep",            # "tdep" (Ka2(T), Clarke-Glew; Hovey-Hepler
                                    # thermochemistry) | "constant" (legacy 25 C)
    "activity_model": "dilute",     # "dilute" (gamma=1) | "pitzer" (PRS activity
                                    # model + co-fitted K2(T); use for molar acid
                                    # concentrations - strongly non-ideal)

    # ---- reverse reactions / chemical equilibrium (H2SO4 route only) ---------------
    # Hydrolysis-direction Keq (dimensionless, concentration basis) at 25 C and
    # van 't Hoff slopes; literature anchoring in pfr_twin/parameters.py.
    # reversible = False recovers the legacy irreversible pseudo-1st-order twin.
    # Ignored for catalyst = "NaOH": saponification is irreversible.
    "equilibrium": {
        "reversible": True,
        "K1_ref": 0.50,             # (EGMA.AcOH)/(EGDA.H2O) at equilibrium, 25 C
        "dH1_kJ": 5.0,              # hydrolysis reaction enthalpy step 1, kJ/mol
        "K2_ref": 0.125,            # (EG.AcOH)/(EGMA.H2O) at equilibrium, 25 C
        "dH2_kJ": 5.0,              # hydrolysis reaction enthalpy step 2, kJ/mol
    },

    # ---- output -------------------------------------------------------------------
    "outdir": "results",            # relative paths resolve next to this script
}
# ============================================================================


# ---------------------------------------------------------------------------
# Reusable single-case machinery (also used by batch_simulation.py)
# ---------------------------------------------------------------------------
@dataclass
class CaseOutcome:
    """Everything one base-case run produces."""
    cfg: Dict
    result: PFRResult
    inlet: object
    report: str
    metrics: Dict[str, float]
    run_dir: str = ""
    files: List[str] = field(default_factory=list)


def build_kinetics(cfg: Dict) -> KineticParameters:
    """KineticParameters for the configured catalyst system."""
    catalyst = cfg["catalyst"]
    if catalyst != "H2SO4":
        return default_kinetics(catalyst)
    eqcfg = cfg["equilibrium"]
    return default_kinetics(
        "H2SO4", reversible=eqcfg["reversible"],
        eq1=EquilibriumStep(K_ref=eqcfg["K1_ref"], dH_J=eqcfg["dH1_kJ"] * 1e3),
        eq2=EquilibriumStep(K_ref=eqcfg["K2_ref"], dH_J=eqcfg["dH2_kJ"] * 1e3),
        h_plus_model=cfg["h_plus_model"],
        n_eff_protons=cfg["n_eff_protons"],
        ka2_model=cfg.get("ka2_model", "tdep"),
        activity_model=cfg.get("activity_model", "dilute"))


def build_inlet(cfg: Dict, kinetics: KineticParameters, T_K: float):
    """Mixed inlet state at x = 0 from the two configured feed streams,
    with catalyst speciation evaluated at the reactor temperature T_K."""
    catalyst = cfg["catalyst"]
    s1, s2 = cfg["stream1"], cfg["stream2"]
    stream1 = Stream("aqueous EGDA", s1["Q_mL_min"], {"EGDA": s1["C_EGDA_M"]},
                     density_g_L=s1["density_g_L"])
    stream2 = Stream(f"aqueous {catalyst}", s2["Q_mL_min"],
                     {catalyst: s2["C_cat_M"]}, density_g_L=s2["density_g_L"])
    return mix_streams(stream1, stream2, kinetics, T_K=T_K)


def simulate_case(cfg: Dict) -> CaseOutcome:
    """Solve one configured base case and assemble its report and metrics.
    Writes nothing; `write_case_outputs` does the I/O."""
    T_K = cfg["temp_C"] + 273.15
    catalyst = cfg["catalyst"]
    kinetics = build_kinetics(cfg)
    model = KineticModel(kinetics)
    geometry = ReactorGeometry(**cfg["reactor"])
    inlet = build_inlet(cfg, kinetics, T_K)
    result = simulate_pfr(inlet, geometry, T_K, model, SolverSettings())

    # ---- verification 1: independent reference solution ---------------------
    if catalyst == "H2SO4":
        # The reversible ODEs have no closed-form transient, so the integrator
        # is checked in the exactly linear irreversible limit of the kinetics.
        kin_irr = KineticParameters(step1=kinetics.step1, step2=kinetics.step2,
                                    reversible=False,
                                    h_plus_model=cfg["h_plus_model"],
                                    n_eff_protons=cfg["n_eff_protons"])
        res_ref = (result if not kinetics.reversible else
                   simulate_pfr(inlet, geometry, T_K, KineticModel(kin_irr),
                                SolverSettings()))
        reference = analytical_profiles(inlet, res_ref.kappa1, res_ref.kappa2,
                                        res_ref.tau_s)
        err = max_relative_error(res_ref.conc, reference, scale=inlet.conc["EGDA"])
        ver1_lines = [f"Integrator vs closed form (irreversible limit): "
                      f"max rel. error = {err:.2e}  "
                      f"[{'PASS' if err < 1e-6 else 'FAIL'}]"]
    else:
        # Saponification with depleting OH- has no closed form: cross-check
        # LSODA against an independent stiff integrator (Radau).
        res_x = simulate_pfr(inlet, geometry, T_K, model,
                             SolverSettings(method="Radau",
                                            rtol=1e-9, atol=1e-12))
        err = max_relative_error(result.conc, res_x.conc,
                                 scale=inlet.conc["EGDA"])
        res_ref, reference = result, res_x.conc     # for the validation figure
        ver1_lines = [f"Cross-solver check (LSODA vs Radau): "
                      f"max rel. difference = {err:.2e}  "
                      f"[{'PASS' if err < 1e-6 else 'FAIL'}]"]

    # ---- verification 2: route-specific physics ------------------------------
    rev_lines: List[str] = []
    c_ref = inlet.conc["EGDA"]
    backbone = result.conc["EGDA"] + result.conc["EGMA"] + result.conc["EG"]
    acetate = (2.0 * result.conc["EGDA"] + result.conc["EGMA"]
               + result.conc["AcOH"])
    drift = float("nan")
    if catalyst == "NaOH":
        oh_acetate = result.conc["OH"] + result.conc["AcOH"]
        drift = max(float(np.ptp(v)) for v in
                    (backbone, acetate, oh_acetate, result.conc["H2O"])) / c_ref
        rev_lines = [
            f"Invariant conservation (backbone/acetate/OH-+acetate/water): "
            f"max drift = {drift:.2e} rel.  "
            f"[{'PASS' if drift < 1e-8 else 'FAIL'}]",
            f"Limiting-reagent bookkeeping: acetate released = "
            f"{result.conc['AcOH'][-1]:.4f} M vs OH- consumed = "
            f"{inlet.conc['OH'] - result.conc['OH'][-1]:.4f} M (must match)",
        ]
    elif kinetics.reversible:
        water_ac = result.conc["H2O"] + result.conc["AcOH"]
        drift = max(float(np.ptp(v)) for v in (backbone, acetate, water_ac)) / c_ref
        eq = result.eq_conc
        r_eq = model.rates([eq[sp] for sp in SPECIES], T_K, inlet.c_h_plus)
        r_in = model.rates([inlet.conc[sp] for sp in SPECIES], T_K, inlet.c_h_plus)
        r_resid = (max(abs(r_eq[0]), abs(r_eq[1]))
                   / max(abs(r_in[0]), abs(r_in[1]), 1e-30))
        q1, q2 = reaction_quotients({sp: result.conc[sp][-1] for sp in SPECIES})
        rev_lines = [
            f"Invariant conservation (backbone/acetate/water): max drift = "
            f"{drift:.2e} rel.  [{'PASS' if drift < 1e-8 else 'FAIL'}]",
            f"Thermodynamic consistency: |net rates| at coupled equilibrium = "
            f"{r_resid:.2e} rel. to inlet rate  "
            f"[{'PASS' if r_resid < 1e-9 else 'FAIL'}]",
            f"Outlet approach to equilibrium: Q1/K1 = {q1 / result.K1:.4f}, "
            f"Q2/K2 = {q2 / result.K2:.4f}",
        ]

    # ---- report -------------------------------------------------------------
    if catalyst == "NaOH":
        mode = "NaOH saponification, irreversible, OH- stoichiometric"
    elif kinetics.reversible:
        mode = "H2SO4, reversible hydrolysis/esterification"
    else:
        mode = "H2SO4, irreversible (legacy) hydrolysis"
    s1, s2 = cfg["stream1"], cfg["stream2"]
    lines = ["=" * 68,
             f"EGDA PFR digital twin - base case ({mode})",
             "=" * 68,
             "",
             "Feed streams (before micromixer):",
             f"  Stream 1: {s1['Q_mL_min']:5.2f} mL/min, "
             f"[EGDA]  = {s1['C_EGDA_M']:.3f} M",
             f"  Stream 2: {s2['Q_mL_min']:5.2f} mL/min, "
             f"[{catalyst}] = {s2['C_cat_M']:.3f} M",
             "",
             "Mixed inlet (x = 0):"]
    lines += [f"  [{sp}] = {inlet.conc[sp]:.4f} M" for sp in SPECIES
              if sp != "OH" or catalyst == "NaOH"]
    if catalyst == "H2SO4":
        lines += [f"  [H2SO4] total = {inlet.c_h2so4:.4f} M",
                  f"  [H+] catalytic = {inlet.c_h_plus:.4f} M"]
    else:
        lines += [f"  [NaOH] total = {inlet.c_naoh:.4f} M"]
    lines += ["  " + n for n in inlet.notes]
    lines += ["", "Flow / plug-flow diagnostics:"]
    lines += ["  " + s for s in flow_diagnostics(inlet, geometry, T_K)]
    lines += ["", "Reactor solution:"]
    lines += ["  " + s for s in result.summary_lines()]
    lines += ["", "Verification:"]
    lines += ["  " + s for s in ver1_lines]
    lines += ["  " + s for s in rev_lines]
    lines += [""]

    metrics = {
        "T_C": float(cfg["temp_C"]),
        "tau_s": result.residence_time_s,
        "X_EGDA": float(result.conversion[-1]),
        "Y_EGMA": float(result.yield_of("EGMA")[-1]),
        "Y_EG": float(result.yield_of("EG")[-1]),
        "S_EGMA": float(result.selectivity_egma),
        "kappa1_1_s": result.kappa1,
        "kappa2_1_s": result.kappa2,
        "C_EGDA_out_M": float(result.conc["EGDA"][-1]),
        "C_EGMA_out_M": float(result.conc["EGMA"][-1]),
        "C_EG_out_M": float(result.conc["EG"][-1]),
        "C_AcOH_out_M": float(result.conc["AcOH"][-1]),
        "verification_error": float(err),
        "invariant_drift": float(drift),
    }
    if catalyst == "NaOH":
        oh0 = inlet.conc["OH"]
        metrics["C_OH_out_M"] = float(result.conc["OH"][-1])
        metrics["OH_consumed_frac"] = (float((oh0 - result.conc["OH"][-1]) / oh0)
                                       if oh0 > 0 else float("nan"))
        metrics["NaOH_per_acetate_group"] = float(
            oh0 / (2.0 * inlet.conc["EGDA"] + inlet.conc["EGMA"]))
    else:
        metrics["K1"] = result.K1
        metrics["K2"] = result.K2
        if result.eq_conc is not None:
            metrics["X_eq"] = float(1.0 - result.eq_conc["EGDA"] / c_ref)
            metrics["Y_EGMA_eq"] = float(
                (result.eq_conc["EGMA"] - inlet.conc["EGMA"]) / c_ref)

    outcome = CaseOutcome(cfg=cfg, result=result, inlet=inlet,
                          report="\n".join(lines), metrics=metrics)
    outcome._reference = (res_ref, reference)      # for the validation figure
    return outcome


def write_case_outputs(outcome: CaseOutcome, run_dir: str) -> CaseOutcome:
    """Write every figure (each with its paired CSV), the profile table, the
    text summary, and the exact run configuration into `run_dir`."""
    res_ref, reference = outcome._reference
    result = outcome.result

    result.write_csv(os.path.join(run_dir, "profiles.csv"))
    with open(os.path.join(run_dir, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write(outcome.report)

    files = [
        plot_concentration_profiles(
            result, os.path.join(run_dir, "concentration_profiles.png")),
        plot_conversion_yield(
            result, os.path.join(run_dir, "conversion_yield.png")),
        plot_validation(
            res_ref, reference, os.path.join(run_dir, "solver_validation.png")),
    ]
    write_run_config(run_dir, outcome.cfg, {"metrics": outcome.metrics})

    outcome.run_dir = run_dir
    outcome.files = files
    return outcome


def run_case(cfg: Dict, root: str, *, prefix: str = "base_case",
             verbose: bool = True) -> CaseOutcome:
    """Simulate one configuration and write its hyperparameter-tagged folder."""
    outcome = simulate_case(cfg)
    run_dir = make_run_dir(root, run_tag(cfg, prefix=prefix))
    write_case_outputs(outcome, run_dir)
    if verbose:
        print(outcome.report)
        print(f"Outputs written to: {run_dir}")
    return outcome


def main() -> None:
    root = resolve_root(CONFIG["outdir"], __file__)
    run_case(CONFIG, root)


if __name__ == "__main__":
    main()
