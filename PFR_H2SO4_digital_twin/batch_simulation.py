"""
BATCH base-case runs of the PFR digital twin.

Same physics and outputs as `run_simulation.py`, but instead of editing one
CONFIG and pressing Run over and over, you declare LISTS of values for any
parameters and every scenario is simulated in one go:

    BASE   - the reference configuration (same shape as run_simulation.CONFIG)
    VARY   - {dotted parameter path: [values, ...]} for the parameters to scan
    MODE   - "grid" (full factorial, default) or "zip" (paired lists)

Outputs (under `results/<batch_name>/`):

    <tagged folder>/            one per scenario, identical content to a
                                single run_simulation.py run (figures, a CSV
                                paired with every figure, profiles.csv,
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

from pfr_twin import resolve_root, make_run_dir, run_tag, write_rows_csv
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
    "temp_C":             [70.0, 100.0, 130.0],
    "reactor.length_m":   [0.060, 0.200],
    "stream2.C_cat_M":    [0.5, 1.5],
    # "catalyst":               ["H2SO4", "NaOH"],
    # "reactor.diameter_m":     [0.004, 0.018],
    # "stream1.C_EGDA_M":       [0.1, 0.5, 1.0],
    # "stream1.Q_mL_min":       [0.5, 2.0],
    # "stream2.Q_mL_min":       [0.5, 2.0],
    # "equilibrium.reversible": [True, False],
}

MODE = "grid"          # "grid" = full factorial | "zip" = paired lists
BATCH_NAME = "batch_base_case"     # subfolder of outdir holding this batch
OUTDIR = "results"                 # relative paths resolve next to this script
QUIET = True                       # True: one progress line per scenario
# ============================================================================


def run_batch(base: Dict, vary: Dict[str, List], *, mode: str = "grid",
              batch_name: str = "batch_base_case", outdir: str = "results",
              anchor: str = __file__, quiet: bool = True) -> List:
    """Simulate every scenario, write per-scenario folders and the summary."""
    scenarios = expand(base, vary, mode=mode)
    root = make_run_dir(resolve_root(outdir, anchor), batch_name)

    print(f"Batch '{batch_name}': {len(scenarios)} scenarios "
          f"({mode} over {', '.join(vary) or 'nothing'})")
    print("-" * 74)

    outcomes, run_dirs, t0 = [], [], time.time()
    for sc in scenarios:
        outcome = simulate_case(sc.config)
        run_dir = make_run_dir(root, run_tag(sc.config, prefix=f"s{sc.index:02d}"))
        write_case_outputs(outcome, run_dir)
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
                   {"BASE": base, "VARY": vary, "MODE": mode})

    print("-" * 74)
    print(f"{len(scenarios)} scenarios in {time.time() - t0:.1f} s")
    print(f"Per-scenario outputs : {root}")
    print(f"Batch summary        : {summary_dir}")
    return outcomes


def _write_summary(scenarios, outcomes, run_dirs, summary_dir: str,
                   batch_cfg: Dict) -> None:
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

    with open(os.path.join(summary_dir, "batch_config.json"), "w",
              encoding="utf-8") as fh:
        json.dump(batch_cfg, fh, indent=2, default=str)


def main() -> None:
    run_batch(BASE, VARY, mode=MODE, batch_name=BATCH_NAME, outdir=OUTDIR,
              anchor=__file__, quiet=QUIET)


if __name__ == "__main__":
    main()
