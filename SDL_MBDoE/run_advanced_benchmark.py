"""
Main EGDA advanced benchmark: scenarios S1-S6, strategies A-F (+ ablations),
many random seeds, publication figures E-H, the strategy comparison table,
and the complete per-round metrics CSV.

IDE workflow: edit CONFIG below and press Run.
Runtime scales ~linearly in len(seeds); CONFIG["smoke"] = True runs a
1-seed, 3-round miniature for a quick end-to-end check.

Everything needed for exact reproduction (CONFIG, scenario specs, truth,
nuisance assumptions, seeds) is saved to <outdir>/benchmark_config.json.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import os
import time

import numpy as np

from sdl_advanced import benchmark as bm
from sdl_advanced import reporting as rep

CONFIG = {
    "seeds": [1, 2, 3, 4],
    "budget": 6,                    # reactor conditions per campaign
    "scenarios": ["S1_ideal", "S2_nmr", "S3_transport", "S4_ambiguity",
                  "S5_inadequacy", "S6_resources"],
    "outdir": "results_advanced/benchmark",
    "smoke": False,
}


def resolve_outdir(outdir: str) -> str:
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              outdir)
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _write_rows(rows, path):
    keys = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {path}")


def _mean_curves(rows, scenario, x_key="round"):
    """strategy -> {metric: [per-round mean over seeds]} for one scenario."""
    out = {}
    sc_rows = [r for r in rows if r["scenario"] == scenario]
    for strat in sorted({r["strategy"] for r in sc_rows}):
        s_rows = [r for r in sc_rows if r["strategy"] == strat]
        rounds = sorted({r["round"] for r in s_rows})
        cur = {x_key: []}
        metrics = ("param_err_pct", "max_rel_ci_pct", "p_correct",
                   "blind_rmse_M", "time_s", "egda_mol",
                   "nmr_acquisitions", "energy_kJ", "capillary_travel_m")
        for m in metrics:
            cur[m] = []
        for rnd in rounds:
            rr = [r for r in s_rows if r["round"] == rnd]
            cur[x_key].append(rnd)
            for m in metrics:
                vals = [r[m] for r in rr if np.isfinite(r.get(m, np.nan))]
                cur[m].append(float(np.mean(vals)) if vals else float("nan"))
        out[strat] = cur
    return out


def _final_rows(rows, scenario):
    """strategy -> dict of final-round seed-averaged metrics."""
    out = {}
    sc = [r for r in rows if r["scenario"] == scenario]
    for strat in sorted({r["strategy"] for r in sc}):
        s_rows = [r for r in sc if r["strategy"] == strat]
        last = max(r["round"] for r in s_rows)
        fr = [r for r in s_rows if r["round"] == last]
        agg = {}
        for k in fr[0]:
            if k in ("scenario", "strategy", "gov_state"):
                continue
            vals = [r[k] for r in fr
                    if isinstance(r[k], (int, float)) and np.isfinite(r[k])]
            agg[k] = float(np.mean(vals)) if vals else float("nan")
        agg["n_seeds"] = len(fr)
        out[strat] = agg
    return out


def main() -> None:
    cfg = dict(CONFIG)
    if cfg["smoke"]:
        cfg["seeds"], cfg["budget"] = [1], 3
    outdir = resolve_outdir(cfg["outdir"])
    t0 = time.time()

    all_rows = []
    runtimes = {}
    for scen_name in cfg["scenarios"]:
        spec = bm.SCENARIOS[scen_name]
        print(f"\n=== {scen_name}: {spec.description}")
        print(f"    strategies {spec.strategies} x seeds {cfg['seeds']}")
        t_s = time.time()
        rows = bm.run_scenario(spec, cfg["seeds"], cfg["budget"],
                               verbose=True)
        runtimes[scen_name] = time.time() - t_s
        all_rows.extend(rows)
        print(f"    {scen_name} done in {runtimes[scen_name]:.0f} s")

    _write_rows(all_rows, os.path.join(outdir, "benchmark_rounds.csv"))

    # ---- Figure E: learning curves (per condition AND per resource) ------ #
    for scen in cfg["scenarios"]:
        if scen not in {r["scenario"] for r in all_rows}:
            continue
        curves = _mean_curves(all_rows, scen)
        rep.figure_e_convergence(
            curves, "round",
            os.path.join(outdir, f"figure_E_{scen}_per_condition.png"))
        for strat in curves:            # resource-based x axis
            curves[strat]["time_s"] = curves[strat]["time_s"]
        rep.figure_e_convergence(
            curves, "time_s",
            os.path.join(outdir, f"figure_E_{scen}_per_time.png"))

    # ---- Figure F: inadequacy challenge (S5) ----------------------------- #
    if "S5_inadequacy" in cfg["scenarios"]:
        s5 = [r for r in all_rows if r["scenario"] == "S5_inadequacy"]
        seeds0 = cfg["seeds"][0]
        naive = [r for r in s5 if r["strategy"] == "D"
                 and r["seed"] == seeds0]
        govd = [r for r in s5 if r["strategy"] == "F" and r["seed"] == seeds0]
        if naive and govd:
            trip = next((r["round"] for r in govd
                         if r["gov_state"] == "MODEL_INADEQUATE"), None)
            rep.figure_f_inadequacy(
                [r["round"] for r in naive],
                [min(r["max_rel_ci_pct"], 1e4) for r in naive],
                [r["param_err_pct"] for r in naive],
                [g["gov_score"] for g in govd],
                [g["gov_state"] for g in govd], trip,
                os.path.join(outdir, "figure_F_inadequacy.png"))

    # ---- Figure G: resource efficiency (S6 if present, else S1) ---------- #
    scen_g = ("S6_resources" if "S6_resources" in cfg["scenarios"]
              else cfg["scenarios"][0])
    finals_g = _final_rows(all_rows, scen_g)
    rep.figure_g_resources(
        {k: v for k, v in finals_g.items()},
        os.path.join(outdir, f"figure_G_resources_{scen_g}.png"))

    # ---- Figure H: ablation ---------------------------------------------- #
    bars = {}
    def _grab(scen, strat, label):
        f = _final_rows(all_rows, scen) if scen in cfg["scenarios"] else {}
        if strat in f:
            bars[label] = {"param_err_pct": f[strat]["param_err_pct"],
                           "blind_rmse_M": f[strat]["blind_rmse_M"]}
    _grab("S1_ideal", "F", "ideal conc. (F)")
    _grab("S2_nmr", "D", "NMR, naive noise (D)")
    _grab("S2_nmr", "F", "NMR, Sigma-aware (F)")
    _grab("S3_transport", "F-uncorr", "NMR+transport, uncorrected")
    _grab("S3_transport", "F", "NMR+transport, modeled")
    if bars:
        rep.figure_h_ablation(bars,
                              os.path.join(outdir, "figure_H_ablation.png"))

    # ---- strategy comparison table (S1 = like-for-like) ------------------ #
    table_rows = []
    for scen in cfg["scenarios"]:
        for strat, f in _final_rows(all_rows, scen).items():
            table_rows.append({
                "scenario": scen, "strategy": strat,
                "param_err_pct": f["param_err_pct"],
                "max_rel_ci_pct": f["max_rel_ci_pct"],
                "p_correct": f["p_correct"],
                "blind_rmse_mM": f["blind_rmse_M"] * 1e3,
                "conditions": f["reactor_conditions"],
                "acquisitions": f["nmr_acquisitions"],
                "egda_mol": f["egda_mol"],
                "time_h": f["time_s"] / 3600.0,
                "travel_m": f["capillary_travel_m"],
                "energy_kJ": f["energy_kJ"],
                "n_seeds": f["n_seeds"],
            })
    text = rep.write_strategy_table(
        table_rows, os.path.join(outdir, "strategy_table.csv"))
    print("\n" + text)

    # ---- false-positive rate of the governor under the correct model ----- #
    fp_rows = [r for r in all_rows
               if r["scenario"] in ("S1_ideal", "S2_nmr")
               and r["strategy"] == "F"]
    n_fp = sum(1 for r in fp_rows if r["gov_state"] == "MODEL_INADEQUATE")
    fp_rate = n_fp / len(fp_rows) if fp_rows else float("nan")
    print(f"\nGovernor false-positive rate under correct model "
          f"(per round): {n_fp}/{len(fp_rows)} = {fp_rate:.1%}")

    # ---- reproducibility record ------------------------------------------ #
    with open(os.path.join(outdir, "benchmark_config.json"), "w") as fh:
        json.dump({
            "CONFIG": cfg, "runtimes_s": runtimes,
            "governor_false_positive_rate": fp_rate,
            "truth": bm.TRUTH, "geometry": bm.GEOMETRY, "design": bm.DESIGN,
            "scenarios": {k: dataclasses.asdict(v)
                          for k, v in bm.SCENARIOS.items()
                          if k in cfg["scenarios"]},
            "nmr_nuisance_true": dataclasses.asdict(bm.NMR_NUISANCE_TRUE),
            "acquisition": dataclasses.asdict(bm.ACQ),
            "transfer_true": dataclasses.asdict(bm.TRANSFER_TRUE),
        }, fh, indent=2, default=str)
    print(f"\nBenchmark finished in {(time.time() - t0) / 60.0:.1f} min. "
          f"Outputs in: {outdir}")


if __name__ == "__main__":
    main()
