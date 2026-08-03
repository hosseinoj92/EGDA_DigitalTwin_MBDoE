"""
BATCH temperature studies of the PFR digital twin.

Same physics and outputs as `run_temperature_study.py`, but you declare LISTS
of values for any parameters and every scenario is swept in one go - so you
can compare, say, three tube lengths x two acid loadings as six temperature
sweeps without editing anything by hand between runs:

    BASE   - the reference configuration (same shape as
             run_temperature_study.CONFIG)
    VARY   - {dotted parameter path: [values, ...]} for the parameters to scan
    MODE   - "grid" (full factorial, default) or "zip" (paired lists)

Note that the sweep axis itself (T_min_C / T_max_C / n_points) is part of the
config, so sweep WINDOWS can also be varied - useful when comparing the two
catalyst routes, whose useful temperature ranges differ by ~50 C.

Outputs (directly under OUTDIR):

    <tagged folder>/            one per scenario, identical content to a single
                                run_temperature_study.py run (both figures,
                                a CSV paired with each, temperature_sweep.csv,
                                run_config.json)
    _batch_summary/
        scenario_index.csv      one row per scenario: varied parameters, the
                                EGMA optimum, conversion at both window ends,
                                equilibrium / stoichiometric ceiling, folder
        conversion_vs_T.png/.csv    X(T), one curve per scenario
        egma_yield_vs_T.png/.csv    Y_EGMA(T), one curve per scenario
        eg_yield_vs_T.png/.csv      Y_EG(T), one curve per scenario
        egma_optimum.png/.csv       best EGMA yield and its temperature
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

from run_temperature_study import CONFIG as DEFAULT_CONFIG
from run_temperature_study import simulate_sweep, write_sweep_outputs

# ============================================================================
# BATCH CONFIG - edit and run.
# ============================================================================
BASE = dict(DEFAULT_CONFIG)
BASE.update({
    "catalyst": "H2SO4",
    "T_min_C": 40.0,
    "T_max_C": 150.0,
    "n_points": 23,
    "profile_temps_C": [40.0, 70.0, 100.0, 130.0, 150.0],
    "stream1": {"Q_mL_min": 0.5, "C_EGDA_M": 0.5, "density_g_L": 1005.0},
    "stream2": {"Q_mL_min": 0.5, "C_cat_M": 1.0, "density_g_L": 1060.0},
    "reactor": {"length_m": 0.200, "diameter_m": 0.004},
})

# Parameters to scan. Keys are DOTTED PATHS into BASE; values are lists.
VARY: Dict[str, List] = {
    "reactor.length_m":  [0.060, 0.200, 0.600],
    "stream2.C_cat_M":   [0.5, 1.5],
    # "stream1.C_EGDA_M":  [0.1, 0.5],
    # "stream1.Q_mL_min":  [0.5, 2.0],
    # "stream2.Q_mL_min":  [0.5, 2.0],
    # "reactor.diameter_m":[0.004, 0.018],
    # ---- comparing catalysts: vary the sweep window with the catalyst,
    #      using MODE = "zip" so the lists are walked as paired scenarios
    # "catalyst":          ["H2SO4", "NaOH"],
    # "T_min_C":           [40.0, 5.0],
    # "T_max_C":           [150.0, 60.0],
}

MODE = "grid"          # "grid" = full factorial | "zip" = paired lists
# LINK_FLOWS = True keeps the two feed flows EQUAL (Q1 = Q2), so they form ONE
# axis instead of a cross-product: put the flow sweep in `stream1.Q_mL_min`
# and stream 2 follows it (any `stream2.Q_mL_min` list is ignored).
LINK_FLOWS = True
# Full output path for this batch. Scenarios land DIRECTLY here. A relative
# path resolves next to this script; give an absolute path to save anywhere,
# e.g. r"D:\Simulations\egda_runs\my_study".
OUTDIR = "results/batch_temperature_study"
# ============================================================================


def run_batch(base: Dict, vary: Dict[str, List], *, mode: str = "grid",
              link_flows: bool = False, outdir: str = "results",
              anchor: str = __file__) -> List:
    """Sweep every scenario, write per-scenario folders and the summary."""
    link = {"stream2.Q_mL_min": "stream1.Q_mL_min"} if link_flows else None
    scenarios = expand(base, vary, mode=mode, link=link)
    root = resolve_root(outdir, anchor)

    print(f"Batch of {len(scenarios)} temperature sweeps -> {root}\n"
          f"  ({mode} over {', '.join(vary) or 'nothing'})")
    print("-" * 78)

    outcomes, run_dirs, t0 = [], [], time.time()
    for sc in scenarios:
        outcome = simulate_sweep(sc.config)
        run_dir = make_run_dir(root, run_tag(sc.config, prefix=f"s{sc.index:02d}",
                                             sweep=True))
        write_sweep_outputs(outcome, run_dir)
        outcomes.append(outcome)
        run_dirs.append(run_dir)
        s = outcome.summary
        opt = ("interior" if s["interior_optimum"] else "at window edge")
        print(f"  [{sc.index + 1:>3}/{len(scenarios)}] {sc.label():<38s} "
              f"X: {s['X_at_T_min']:6.1%} -> {s['X_at_T_max']:6.1%}   "
              f"Y_EGMA max {s['Y_EGMA_max']:6.1%} @ "
              f"{s['T_at_Y_EGMA_max_C']:5.1f} C ({opt})")

    summary_dir = make_run_dir(root, "_batch_summary")
    _write_summary(scenarios, outcomes, run_dirs, summary_dir,
                   {"BASE": base, "VARY": vary, "MODE": mode})

    print("-" * 78)
    print(f"{len(scenarios)} sweeps in {time.time() - t0:.1f} s")
    print(f"Per-scenario outputs : {root}")
    print(f"Batch summary        : {summary_dir}")
    return outcomes


def _write_summary(scenarios, outcomes, run_dirs, summary_dir: str,
                   batch_cfg: Dict) -> None:
    """Index table plus the cross-scenario comparison figures (each + CSV)."""
    header, rows = index_rows(scenarios, [o.summary for o in outcomes], run_dirs)
    write_rows_csv(os.path.join(summary_dir, "scenario_index.csv"), header, rows)

    labels = [sc.label(max_len=32) for sc in scenarios]
    temps = [o.T_C for o in outcomes]
    for attr, fname, title, ylabel in (
            ("X", "conversion_vs_T", "EGDA conversion vs temperature", "X EGDA (–)"),
            ("Y_egma", "egma_yield_vs_T", "EGMA yield vs temperature", "Y EGMA (–)"),
            ("Y_eg", "eg_yield_vs_T", "EG yield vs temperature", "Y EG (–)")):
        plot_scenario_curves(
            labels, temps, [getattr(o, attr) for o in outcomes],
            os.path.join(summary_dir, fname + ".png"),
            title + " - all scenarios", "temperature (°C)", ylabel)

    plot_scenario_bars(
        labels,
        {"Y EGMA max": [o.summary["Y_EGMA_max"] for o in outcomes]},
        os.path.join(summary_dir, "egma_optimum.png"),
        title="Best achievable EGMA yield per scenario",
        ylabel="Y EGMA at its optimum (–)")

    with open(os.path.join(summary_dir, "batch_config.json"), "w",
              encoding="utf-8") as fh:
        json.dump(batch_cfg, fh, indent=2, default=str)


def main() -> None:
    run_batch(BASE, VARY, mode=MODE, link_flows=LINK_FLOWS, outdir=OUTDIR,
              anchor=__file__)


if __name__ == "__main__":
    main()
