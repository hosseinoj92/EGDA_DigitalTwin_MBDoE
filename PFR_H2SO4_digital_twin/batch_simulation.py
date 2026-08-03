"""
BATCH base-case runs of the PFR digital twin.

Same physics and outputs as `run_simulation.py`, but instead of editing one
CONFIG and pressing Run over and over, you declare LISTS of values for any
parameters and every scenario is simulated in one go:

    BASE   - the reference configuration (same shape as run_simulation.CONFIG)
    VARY   - {dotted parameter path: [values, ...]} for the parameters to scan
    MODE   - "grid" (full factorial, default) or "zip" (paired lists)
    LINK_FLOWS - True keeps the two feed flows equal (Q1 = Q2), collapsing the
             redundant Q1xQ2 cross-product into one flow axis (put the sweep
             in stream1.Q_mL_min)
    SAVE_IMAGES - True writes PNG figures; False writes only CSV, JSON, and
                  text summaries

Outputs (directly under OUTDIR):

    <tagged folder>/            one per scenario, identical content to a
                                single run_simulation.py run (optional figures,
                                their CSV data, profiles.csv,
                                summary.txt, run_config.json)
    _batch_summary/
        scenario_index.csv      one row per scenario: varied parameters,
                                outlet KPIs, verification residuals, folder
        outlet_kpis.png/.csv    grouped bars, X / Y_EGMA / Y_EG per scenario
        conversion_vs_x.png/.csv    axial conversion, one curve per scenario
        egma_vs_x.png/.csv          axial EGMA, one curve per scenario
        batch_config.json       BASE + VARY + MODE, exactly as run

IDE workflow: edit BASE / VARY / MODE below and press Run.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List

import numpy as np

from pfr_twin import (
    resolve_root, make_run_dir, run_tag, write_rows_csv, write_columns_csv,
    write_run_config,
)
from pfr_twin.batch import expand, index_rows
from pfr_twin.plotting import plot_scenario_bars, plot_scenario_curves

from run_simulation import CONFIG as DEFAULT_CONFIG
from run_simulation import simulate_case, write_case_outputs

# ============================================================================
# BATCH CONFIG - edit and run.
# ============================================================================
# Reference configuration: every key not listed in VARY keeps this value.
# Start from run_simulation.CONFIG and override what you want as the baseline.
BASE = dict(DEFAULT_CONFIG)
BASE.update({
    "catalyst": "H2SO4",
    "temp_C": 100.0,
    "stream1": {"Q_mL_min": 0.5, "C_EGDA_M": 0.5, "density_g_L": 1005.0},
    "stream2": {"Q_mL_min": 0.5, "C_cat_M": 1.0, "density_g_L": 1060.0},
    "reactor": {"length_m": 0.200, "diameter_m": 0.004},
})



# Parameters to scan. Keys are DOTTED PATHS into BASE; values are lists.
# Comment a line out to hold that parameter at its BASE value.
VARY: Dict[str, List] = {
    "temp_C":             [25, 40, 60, 80, 100, 120, 140, 160],
    "reactor.length_m":   [0.20],
    "stream2.C_cat_M":    [0.1, 0.2, 0.3, 0.4, 0.5],
    "stream1.C_EGDA_M":       [0.1, 0.2, 0.3, 0.4, 0.5],
    "catalyst":               ["NaOH"],
    "reactor.diameter_m":     [0.018],
    "stream1.Q_mL_min":       [1.0, 2.0, 3.0, 4.0, 5.0],
    "stream2.Q_mL_min":       [1.0, 2.0, 3.0, 4.0, 5.0],
    "equilibrium.reversible": [True],
}



MODE = "grid"          # "grid" = full factorial | "zip" = paired lists
# LINK_FLOWS = True keeps the two feed flows EQUAL (Q1 = Q2), so they form ONE
# axis instead of a cross-product: put the flow sweep in `stream1.Q_mL_min`
# and stream 2 follows it (any `stream2.Q_mL_min` list is ignored). Since the
# flow ratio is redundant (it only retunes the mixed concentration + tau),
# this drops the wasteful Q1xQ2 grid - e.g. 5x5=25 flow points become 5.
LINK_FLOWS = True
# Full output path for this batch. Scenarios land DIRECTLY here. A relative
# path resolves next to this script; give an absolute path to save anywhere,
# e.g. r"D:\Simulations\egda_runs\my_study".
OUTDIR = r"C:\Users\vt4ho\Simulations\kinetics_sim\EDGA\Homogenous_RESULTS\BatchSweep\NaOH\PFR_dimensions"
QUIET = True                       # True: one progress line per scenario
SAVE_IMAGES = False                 # False: keep only CSV, JSON, and TXT outputs
# ============================================================================


def run_batch(base: Dict, vary: Dict[str, List], *, mode: str = "grid",
              link_flows: bool = False, outdir: str = "results",
              anchor: str = __file__, quiet: bool = True,
              save_images: bool = True) -> List:
    """Simulate every scenario, write per-scenario folders and the summary."""
    link = {"stream2.Q_mL_min": "stream1.Q_mL_min"} if link_flows else None
    scenarios = expand(base, vary, mode=mode, link=link)
    root = resolve_root(outdir, anchor)

    print(f"Batch of {len(scenarios)} scenarios -> {root}\n"
          f"  ({mode} over {', '.join(vary) or 'nothing'})")
    print("-" * 74)

    outcomes, run_dirs, t0 = [], [], time.time()
    for sc in scenarios:
        outcome = simulate_case(sc.config)
        run_dir = make_run_dir(root, run_tag(sc.config, prefix=f"s{sc.index:02d}"))
        if save_images:
            write_case_outputs(outcome, run_dir)
        else:
            _write_case_outputs_csv_only(outcome, run_dir)
            _remove_png_files(run_dir)
        outcomes.append(outcome)
        run_dirs.append(run_dir)
        m = outcome.metrics
        print(f"  [{sc.index + 1:>3}/{len(scenarios)}] {sc.label():<46s} "
              f"X={m['X_EGDA']:6.2%}  Y_EGMA={m['Y_EGMA']:6.2%}  "
              f"Y_EG={m['Y_EG']:6.2%}  tau={m['tau_s']:8.1f}s")
        if not quiet:
            print(outcome.report)

    summary_dir = make_run_dir(root, "_batch_summary")
    _write_summary(scenarios, outcomes, run_dirs, summary_dir,
                   {"BASE": base, "VARY": vary, "MODE": mode,
                    "SAVE_IMAGES": save_images},
                   save_images=save_images)

    print("-" * 74)
    print(f"{len(scenarios)} scenarios in {time.time() - t0:.1f} s")
    print(f"Per-scenario outputs : {root}")
    print(f"Batch summary        : {summary_dir}")
    return outcomes


def _write_summary(scenarios, outcomes, run_dirs, summary_dir: str,
                   batch_cfg: Dict, *, save_images: bool = True) -> None:
    """Index table plus the cross-scenario comparison figures (each + CSV)."""
    header, rows = index_rows(scenarios, [o.metrics for o in outcomes], run_dirs)
    write_rows_csv(os.path.join(summary_dir, "scenario_index.csv"), header, rows)

    labels = [sc.label(max_len=32) for sc in scenarios]
    plot_scenario_bars(
        labels,
        {"X EGDA": [o.metrics["X_EGDA"] for o in outcomes],
         "Y EGMA": [o.metrics["Y_EGMA"] for o in outcomes],
         "Y EG": [o.metrics["Y_EG"] for o in outcomes]},
        os.path.join(summary_dir, "outlet_kpis.png"))

    plot_scenario_curves(
        labels, [o.result.x_m for o in outcomes],
        [o.result.conversion for o in outcomes],
        os.path.join(summary_dir, "conversion_vs_x.png"),
        "EGDA conversion along the reactor - all scenarios",
        "reactor position x (m)", "X EGDA (–)")

    plot_scenario_curves(
        labels, [o.result.x_m for o in outcomes],
        [o.result.conc["EGMA"] for o in outcomes],
        os.path.join(summary_dir, "egma_vs_x.png"),
        "EGMA concentration along the reactor - all scenarios",
        "reactor position x (m)", "C EGMA (mol/L)")

    if not save_images:
        _remove_png_files(summary_dir)

    with open(os.path.join(summary_dir, "batch_config.json"), "w",
              encoding="utf-8") as fh:
        json.dump(batch_cfg, fh, indent=2, default=str)


def _write_case_outputs_csv_only(outcome, run_dir: str) -> None:
    """Write the normal numerical outputs without constructing figures."""
    result = outcome.result
    res_ref, reference = outcome._reference

    result.write_csv(os.path.join(run_dir, "profiles.csv"))
    with open(os.path.join(run_dir, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write(outcome.report)

    species = ["EGDA", "EGMA", "EG", "AcOH"]
    if result.catalyst == "NaOH":
        species.append("OH")
    concentration_data = {"x_m": result.x_m, "tau_s": result.tau_s}
    for sp in species:
        concentration_data[f"C_{sp}_mol_L"] = result.conc[sp]
        if result.eq_conc is not None and sp != "OH":
            concentration_data[f"C_{sp}_eq_mol_L"] = np.full_like(
                result.x_m, result.eq_conc[sp])
    write_columns_csv(
        os.path.join(run_dir, "concentration_profiles.csv"),
        concentration_data)

    write_columns_csv(
        os.path.join(run_dir, "conversion_yield.csv"),
        {"x_m": result.x_m, "tau_s": result.tau_s,
         "X_EGDA": result.conversion,
         "Y_EGMA": result.yield_of("EGMA"),
         "Y_EG": result.yield_of("EG")})

    validation_data = {"tau_s": res_ref.tau_s}
    for sp in ("EGDA", "EGMA", "EG", "AcOH"):
        validation_data[f"C_{sp}_numerical"] = res_ref.conc[sp]
        validation_data[f"C_{sp}_reference"] = reference[sp]
    write_columns_csv(
        os.path.join(run_dir, "solver_validation.csv"), validation_data)

    write_run_config(run_dir, outcome.cfg, {"metrics": outcome.metrics})
    outcome.run_dir = run_dir
    outcome.files = [
        os.path.join(run_dir, "concentration_profiles.csv"),
        os.path.join(run_dir, "conversion_yield.csv"),
        os.path.join(run_dir, "solver_validation.csv"),
    ]


def _remove_png_files(directory: str) -> None:
    """Remove stale or summary figures while retaining paired CSV files."""
    for name in os.listdir(directory):
        if name.lower().endswith(".png"):
            os.remove(os.path.join(directory, name))


def main() -> None:
    run_batch(BASE, VARY, mode=MODE, link_flows=LINK_FLOWS, outdir=OUTDIR,
              anchor=__file__, quiet=QUIET, save_images=SAVE_IMAGES)


if __name__ == "__main__":
    main()
