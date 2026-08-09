"""
Main EGDA advanced benchmark (corrected framework, v3 outputs).

Runs the scenario suite of sdl_advanced.benchmark in one of three modes
("smoke" seconds / "demo" default / "publication" many seeds), with
common-random-number seed lists shared across strategies, and writes a NEW
results directory (never silently overwriting the previous reference run):

  results_advanced_v3/benchmark/
    benchmark_rounds.csv          every per-round metric, every campaign
    benchmark_params.csv          per-parameter posterior rows (#13)
    strategy_table.csv/.txt       distributional summary (median/IQR/CI)
    paired_comparisons.csv        per-seed paired differences + P(better)
    governor_validation.json      measured FP rate + detection rounds
    quantification_validation.csv suites A/B/FID (bias/RMSE/coverage)
    figure_* ...                  the figure set (see FIGURES in README)
    benchmark_config.json         exact reproduction record

Parallelism: set CONFIG["n_workers"].  Campaigns are independent and each is
a pure function of (scenario, strategy, seed, budget), so they are spread
over processes and reassembled in submission order - every saved file is
identical to a one-core run except the wall-clock telemetry (per-campaign
`runtime_s`, per-scenario `runtimes_s`), which is what more cores are meant
to change.  Verified end to end by tests/test_parallel.py.  Works the same
on macOS (Apple Silicon included), Windows and Linux; see
sdl_advanced/parallel.py for how the identity is maintained.

IDE workflow: edit CONFIG and press Run.
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------- #
# Numerical threads are pinned BEFORE numpy/scipy are imported, because a
# BLAS backend reads these at import time and cannot be reconfigured
# afterwards.  One thread per process is what makes an N-worker run
# reproduce a one-core run digit for digit (a threaded BLAS reduction sums
# in a nondeterministic order), and it costs nothing here: the linear
# algebra is 6x6 parameter blocks.  Raising it is a deliberate,
# determinism-losing choice - see CONFIG["threads_per_worker"].
#
# The variable list is spelled out rather than imported from
# sdl_advanced.parallel because importing anything from that PACKAGE runs
# sdl_advanced/__init__.py, which imports numpy - too late.  The two lists
# are pinned equal by tests/test_parallel.py.
# --------------------------------------------------------------------- #
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import csv                                                       # noqa: E402
import dataclasses                                               # noqa: E402
import json                                                      # noqa: E402
import multiprocessing                                           # noqa: E402
import os                                                        # noqa: E402
import sys                                                       # noqa: E402
import time                                                      # noqa: E402

import numpy as np                                               # noqa: E402

try:                                    # progress bar (optional dependency)
    from tqdm.auto import tqdm
except ImportError:                     # pragma: no cover - fallback
    tqdm = None

from sdl_advanced import audit_export as aex                      # noqa: E402
from sdl_advanced import audit_summary as asum                   # noqa: E402
from sdl_advanced import benchmark as bm                         # noqa: E402
from sdl_advanced import nmr_examples as nex                     # noqa: E402
from sdl_advanced import parallel as par                         # noqa: E402
from sdl_advanced import reporting as rep                        # noqa: E402
from sdl_advanced import validation as val                       # noqa: E402
from sdl_advanced import observability as obs                    # noqa: E402

CONFIG = {
    "mode": "publication",                 # "smoke" | "demo" | "publication"
    # NEW directory: the v3 publication run stays exactly where it is, so
    # the results the README currently reports are never overwritten.
    "outdir": "results_advanced_v4/publication",
    # optional overrides of the mode defaults (None -> use MODES[mode]):
    "seeds": None,
    "budget": None,
    "scenarios": None,
    "governor_mc_seeds": None,      # default: seeds of the mode, min 12
    "run_quant_validation": True,
    "progress": True,          # overall tqdm bar with % done + ETA
    "verbose_rounds": False,   # per-round campaign lines (noisy under the bar)

    # ---- parallelism (identical results at any setting) ---------------- #
    # One campaign = one task.  Choose the number of PROCESSES:
    #   None / "auto" -> every core but one (recommended: keeps the laptop
    #                    responsive, and the OS still schedules the pool)
    #   0             -> every core
    #   1             -> serial, no multiprocessing machinery at all
    #   n             -> exactly n processes
    # On Apple Silicon os.cpu_count() counts performance + efficiency cores;
    # the pool is dynamically load-balanced, so the slower cores simply take
    # fewer campaigns.
    "n_workers": "auto",
    # BLAS threads INSIDE each worker.  Keep at 1: it prevents oversubscription
    # (n_workers x threads > cores, which is slower, not faster) and it is the
    # setting under which parallel output is bit-identical to serial output.
    "threads_per_worker": 1,

    # ---- publication audit trail --------------------------------------- #
    # Adds the long-form audit tables (design history, candidate scores,
    # model probabilities, governor diagnostics, blind predictions,
    # posterior covariances, per-acquisition NMR records, resource events,
    # timings) under audit/ in the output directory, plus the run-level
    # reports and the representative NMR examples.
    #
    # It is PURE REPORTING: recording draws no random numbers and evaluates
    # no objective, so the scientific results are identical with it on or
    # off - tests/test_audit_regression.py proves that for matched seeds.
    # It does cost disk: expect a few hundred MB for a 40-seed run, mostly
    # nmr_measurements_long.csv and posterior_covariance_long.csv.
    "audit": True,
    "audit_examples": True,     # the three representative NMR spectra
}

#: audit tables grouped into subdirectories so the trail stays navigable
AUDIT_LAYOUT = {
    "design": ("design_history", "design_candidate_scores"),
    "inference": ("model_probabilities_long", "posterior_covariance_long",
                  "identifiability_summary"),
    "governor": ("governor_diagnostics_long",),
    "measurement": ("nmr_measurements_long", "nmr_calibration_by_seed"),
    "resources": ("resource_events_long", "controller_timing"),
    "validation": ("blind_predictions_long",),
}


def resolve_outdir(outdir: str) -> str:
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              outdir)
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _write_rows(rows, path):
    if not rows:
        return
    keys = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"saved: {os.path.relpath(path)}")


def _mean_curves(rows, scenario, x_key="round"):
    out = {}
    sc_rows = [r for r in rows if r["scenario"] == scenario]
    metrics = ("param_err_pct", "max_rel_ci_pct", "p_correct",
               "model_entropy", "blind_rmse_M", "time_s", "egda_mol",
               "nmr_acquisitions", "energy_kJ", "capillary_travel_m",
               "spatial_samples")
    for strat in sorted({r["strategy"] for r in sc_rows}):
        s_rows = [r for r in sc_rows if r["strategy"] == strat]
        rounds = sorted({r["round"] for r in s_rows})
        cur = {x_key: []}
        for m in metrics:
            cur[m] = []
        for rnd in rounds:
            rr = [r for r in s_rows if r["round"] == rnd]
            cur[x_key].append(rnd)
            for m in metrics:
                vals = [r[m] for r in rr
                        if np.isfinite(r.get(m, np.nan))]
                cur[m].append(float(np.mean(vals)) if vals else float("nan"))
        out[strat] = cur
    return out


def _finals(rows, scenario):
    out = {}
    sc = [r for r in rows if r["scenario"] == scenario]
    for strat in sorted({r["strategy"] for r in sc}):
        fr = bm.last_valid_rows(rows, scenario, strat)   # keeps paused seeds
        agg = {}
        for k in fr[0]:
            vals = [r[k] for r in fr
                    if isinstance(r[k], (int, float)) and np.isfinite(r[k])]
            if vals:
                agg[k] = float(np.median(vals))
        agg["n_seeds"] = len(fr)
        out[strat] = agg
    return out


def main() -> None:
    cfg = dict(CONFIG)
    mode = bm.MODES[cfg["mode"]]
    seeds = cfg["seeds"] or mode["seeds"]
    budget = cfg["budget"] or mode["budget"]
    scenarios = cfg["scenarios"] or mode["scenarios"]
    outdir = resolve_outdir(cfg["outdir"])
    t0 = time.time()

    # ---- overall progress bar ------------------------------------------- #
    gov_seeds = cfg["governor_mc_seeds"] or list(seeds)
    if len(gov_seeds) < 12:
        gov_seeds = list(range(1, 13))
    total_units = bm.total_cost_units(scenarios, seeds, budget,
                                      len(gov_seeds))
    use_bar = bool(cfg.get("progress", True)) and tqdm is not None
    bar = (tqdm(total=round(total_units), unit="wu", dynamic_ncols=True,
                smoothing=0.05,
                bar_format="{l_bar}{bar}| {percentage:3.0f}% "
                           "[elapsed {elapsed} | remaining {remaining}]")
           if use_bar else None)
    say = (lambda msg: (tqdm.write(msg) if bar is not None else print(msg)))

    def _tick(scenario, strategy, seed, b):
        if bar is not None:
            bar.update(bm.campaign_cost_units(strategy, b))
            bar.set_description(f"{scenario}/{strategy} seed{seed}")

    # ---- parallel plan --------------------------------------------------- #
    # Children inherit the environment, so setting it here (before the pool
    # is created) configures every worker.  The parent was already pinned at
    # import time; they must agree for serial and parallel to match.
    threads = int(cfg.get("threads_per_worker", 1) or 1)
    par.pin_numerical_threads(threads)
    n_proc = par.resolve_workers(cfg.get("n_workers", "auto"))
    audit_on = bool(cfg.get("audit", False))

    say(f"=== advanced benchmark v3 | mode={cfg['mode']} | "
        f"{len(seeds)} seeds | budget {budget} ===")
    say(f"    parallelism: {par.describe_workers(cfg.get('n_workers', 'auto'))}"
        f", {threads} BLAS thread(s) each")
    if threads != 1:
        say("    WARNING: threads_per_worker != 1 - a threaded BLAS reduction "
            "sums in a nondeterministic order, so bit-identical agreement "
            "with a serial run is no longer guaranteed.")
    say(f"    audit trail: {'ON -> ' + os.path.join(outdir, 'audit') if audit_on else 'off'}")

    # ---- (0B) equilibrium-observability diagnostic, BEFORE any campaign - #
    # uses ASSUMED (literature) parameters only: firewall-clean
    from sdl import Layer1Bridge, OperatingConditions, literature_guess
    t_ref_K = bm.T_REF_C + 273.15
    guess = literature_guess(t_ref_K)
    diag_bridge = Layer1Bridge(bm.GEOMETRY, t_ref_K, activity_model="pitzer")
    scan_conds = [OperatingConditions(T, q / 2, q / 2, 1.0, c)
                  for T in (40.0, 100.0, 160.0)
                  for q in (0.5, 2.0, 8.0) for c in (0.5, 1.0)]
    scan = obs.domain_scan(diag_bridge, guess, scan_conds)
    obs.write_scan_csv(scan, os.path.join(outdir,
                                          "equilibrium_observability.csv"))
    verdict = obs.verdict(scan)
    print("\nEquilibrium observability over the admissible domain "
          f"(geometry {bm.GEOMETRY['length_m']*100:.0f} cm x "
          f"{bm.GEOMETRY['diameter_m']*1e3:.0f} mm ID, "
          f"V_liq={diag_bridge.geometry.liquid_volume_mL:.2f} mL):")
    print(f"  max phi1={verdict['max_phi1']:.3g}  max phi2="
          f"{verdict['max_phi2']:.3g}  "
          f"|dC/dlnK1|={verdict['max_dC_dlnK1']*1e3:.1f} mM "
          f"({verdict['snr_K1']:.2f} sigma)  "
          f"|dC/dlnK2|={verdict['max_dC_dlnK2']*1e3:.1f} mM "
          f"({verdict['snr_K2']:.2f} sigma)")
    for msg in verdict["messages"]:
        print("  " + msg)
    obs.plot_phi_profiles(
        diag_bridge, guess,
        [OperatingConditions(160.0, 0.25, 0.25, 1.0, 1.0),
         OperatingConditions(100.0, 0.25, 0.25, 1.0, 1.0),
         OperatingConditions(160.0, 4.0, 4.0, 1.0, 1.0)],
        os.path.join(outdir, "figure_equilibrium_observability.png"))

    # ---- well-specified scenarios: truth must lie inside the candidate box #
    for scen in scenarios:
        spec = bm.SCENARIOS[scen]
        if not getattr(spec, "well_specified", False):
            continue
        space = __import__("sdl").ParameterSpace(
            t_ref_K=t_ref_K, initial_guess=dict(guess))
        dom = bm.check_truth_in_domain(space, spec.truth)
        print(f"  domain check {scen}: ok={dom['ok']}  " +
              ", ".join(f"{k}:{'in' if v['inside'] else 'OUT'}"
                        f"/margin={v['margin_scaled']:.2f}"
                        for k, v in dom["detail"].items()))
        if not dom["ok"]:
            raise AssertionError(
                f"{scen} is declared well-specified but its truth is not "
                f"inside the candidate parameter domain: {dom['detail']}")

    # ==== COMPUTE PHASE (parallel) ======================================= #
    # Everything that runs campaigns happens here, under one pool; the
    # reporting phase below is serial and touches no laboratory.  The pool
    # is created once rather than per scenario so the process start-up cost
    # (a fresh interpreter importing numpy/scipy, under `spawn`) is paid a
    # single time.
    all_rows, all_prows, all_status, runtimes = [], [], [], {}
    audit_all = aex.empty_bundle() if audit_on else None
    executor = par.make_executor(cfg.get("n_workers", "auto"),
                                 initializer=bm.worker_init,
                                 initargs=(budget,))
    try:
        for scen in scenarios:
            spec = bm.SCENARIOS[scen]
            say(f"\n=== {scen}: {spec.description}")
            t_s = time.time()
            rows, prows, status, bundle = bm.run_scenario(
                spec, seeds, budget,
                verbose=bool(cfg.get("verbose_rounds", False)),
                progress=_tick, executor=executor, audit=audit_on)
            runtimes[scen] = time.time() - t_s
            all_rows.extend(rows)
            all_prows.extend(prows)
            all_status.extend(status)
            if audit_on:
                aex.merge(audit_all, bundle)
            say(f"    {scen} done in {runtimes[scen]:.0f} s")

        say(f"\n=== governor Monte Carlo validation ({len(gov_seeds)} seeds)")
        t_g = time.time()
        gov = bm.governor_mc_validation(gov_seeds, budget=budget,
                                        progress=_tick, executor=executor)
        gov["runtime_s"] = time.time() - t_g
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    # ==== REPORTING PHASE (serial) ======================================= #

    _write_rows(all_rows, os.path.join(outdir, "benchmark_rounds.csv"))
    _write_rows(all_prows, os.path.join(outdir, "benchmark_params.csv"))
    # campaign status: completion / fault / QC counts per strategy x seed,
    # so accuracy is always read next to completion rate (no survivorship)
    _write_rows(all_status, os.path.join(outdir, "campaign_status.csv"))
    for scen in scenarios:
        st = [s for s in all_status if s["scenario"] == scen]
        for strat in sorted({s["strategy"] for s in st}):
            ss = [s for s in st if s["strategy"] == strat]
            n_f = sum(s["faulted"] for s in ss)
            if n_f:
                print(f"    NOTE {scen}/{strat}: {n_f}/{len(ss)} campaigns "
                      f"paused on measurement fault (retained in stats via "
                      f"their last valid posterior)")

    # ---- (1) strategy table: distributional, no cherry-picking ---------- #
    table = []
    for scen in scenarios:
        table.extend(bm.summarize_final(all_rows, scen))
    text = rep.write_strategy_table(
        table, os.path.join(outdir, "strategy_table.csv"))
    print("\n" + text)

    # ---- paired comparisons (common random numbers) --------------------- #
    pairs = []
    for scen, a, b in (("S1_ideal", "F", "D"), ("S2_nmr", "F", "D"),
                       ("S3_transport", "F", "D"),
                       ("S3_transport", "F", "F-uncorr"),
                       ("S6_resources", "F-res-1x", "F")):
        if scen in scenarios:
            for metric in ("blind_rmse_M", "param_err_pct"):
                pc = bm.paired_comparison(all_rows, scen, a, b, metric)
                if pc:
                    pairs.append(pc)
    _write_rows(pairs, os.path.join(outdir, "paired_comparisons.csv"))

    # ---- (2,3,4) convergence vs round / acquisitions / time ------------- #
    for scen in scenarios:
        if scen not in {r["scenario"] for r in all_rows}:
            continue
        curves = _mean_curves(all_rows, scen)
        rep.figure_e_convergence(
            curves, "round",
            os.path.join(outdir, f"figure_conv_{scen}_per_round.png"))
        for x_key, tag in (("nmr_acquisitions", "per_acquisition"),
                           ("time_s", "per_time")):
            cur2 = {s: dict(c, **{x_key: c[x_key]})
                    for s, c in curves.items()}
            rep.figure_e_convergence(
                cur2, x_key,
                os.path.join(outdir, f"figure_conv_{scen}_{tag}.png"))

    # ---- (6) model probabilities / entropy vs round (S4a, S4b) ---------- #
    for scen in ("S4a_ambiguity", "S4b_identifiable",
                 "S4c_out_of_domain"):
        if scen not in scenarios:
            continue
        curves = _mean_curves(all_rows, scen)
        rep.figure_e_convergence(
            curves, "round",
            os.path.join(outdir, f"figure_model_probs_{scen}.png"),
            panels=(("p_correct", "P(correct model)"),
                    ("model_entropy", "model entropy / nats"),
                    ("param_err_pct", "parameter error / %"),
                    ("blind_rmse_M", "blind RMSE / M")))

    # ---- (7) parameter posterior evolution (#13) ------------------------ #
    for scen, strat in (("S1_ideal", "F"), ("S2_nmr", "F"),
                        ("S4b_identifiable", "F"), ("S3_transport", "F")):
        if scen in scenarios:
            rep.figure_param_evolution(
                all_prows, scen, strat,
                os.path.join(outdir, f"figure_params_{scen}_{strat}.png"))

    # ---- (11) governor diagnostics + MC validation ---------------------- #
    # (the campaigns themselves ran in the compute phase above)
    with open(os.path.join(outdir, "governor_validation.json"), "w") as fh:
        json.dump(gov, fh, indent=2)
    print(f"\ngovernor MC validation ({len(gov_seeds)} seeds): "
          f"false-inadequacy campaign rate = "
          f"{gov['false_inadequacy_campaign_rate']:.2f}, detection prob = "
          f"{gov['detection_probability']:.2f}, median detection round = "
          f"{gov['median_detection_round']}")
    if "S5_inadequacy" in scenarios:
        s5 = [r for r in all_rows if r["scenario"] == "S5_inadequacy"]
        seed0 = seeds[0]
        naive = [r for r in s5 if r["strategy"] == "D"
                 and r["seed"] == seed0]
        govd = [r for r in s5 if r["strategy"] == "F"
                and r["seed"] == seed0]
        if naive and govd:
            trip = next((r["round"] for r in govd
                         if r["gov_state"] == "MODEL_INADEQUATE"), None)
            rep.figure_f_inadequacy(
                [r["round"] for r in naive],
                [min(r["max_rel_ci_pct"], 1e4) for r in naive],
                [r["param_err_pct"] for r in naive],
                [g["gov_score"] for g in govd],
                [g["gov_state"] for g in govd], trip,
                os.path.join(outdir, "figure_governor_S5.png"))

    # ---- (12) resource Pareto (S6 lambda sweep) ------------------------- #
    if "S6_resources" in scenarios:
        finals6 = _finals(all_rows, "S6_resources")
        rep.figure_g_resources(
            {k: v for k, v in finals6.items() if "blind_rmse_M" in v},
            os.path.join(outdir, "figure_pareto_S6.png"))

    # ---- (13) transport ablation ---------------------------------------- #
    ab = {}
    for scen, label in (("S3ab_delay", "delay + reaction (plug)"),
                        ("S3ab_rtd", "+ RTD dispersion"),
                        ("S3_transport", "+ carryover (full)")):
        if scen in scenarios:
            f = _finals(all_rows, scen)
            ab[label] = {s: f[s]["blind_rmse_M"] for s in ("D", "F")
                         if s in f and "blind_rmse_M" in f[s]}
    if ab:
        rep.figure_transport_ablation(
            ab, os.path.join(outdir, "figure_transport_ablation.png"))

    # ---- (14) spatial-mode comparison (S7) ------------------------------ #
    if "S7_spatial_modes" in scenarios:
        curves = _mean_curves(all_rows, "S7_spatial_modes")
        rep.figure_e_convergence(
            curves, "nmr_acquisitions",
            os.path.join(outdir, "figure_spatial_modes_S7.png"),
            panels=(("param_err_pct", "parameter error / %"),
                    ("blind_rmse_M", "blind RMSE / M"),
                    ("spatial_samples", "axial samples used"),
                    ("time_s", "campaign time / s")))
        # (5) selected z/L by round comes from the demo runner's Figure B;
        # here the CSV carries the per-round z counts per mode

    # ---- (9,10) quantification validation + spectra --------------------- #
    if cfg["run_quant_validation"]:
        t_v = time.time()
        results = val.run_validation(bm.ACQ, bm.NMR_NUISANCE_TRUE,
                                     bm.GEOMETRY, bm.T_REF_C + 273.15,
                                     __import__("sdl").literature_guess(
                                         bm.T_REF_C + 273.15), seed=0)
        _write_rows(val.validation_rows(results),
                    os.path.join(outdir, "quantification_validation.csv"))
        print(f"quantification validation done in {time.time() - t_v:.0f} s")

    # ==== PUBLICATION AUDIT TRAIL ======================================== #
    # Pure reporting: everything below reads finished results.  No campaign
    # code runs, so nothing here can move a scientific number.
    if audit_on:
        adir = os.path.join(outdir, "audit")
        for sub, tables in AUDIT_LAYOUT.items():
            os.makedirs(os.path.join(adir, sub), exist_ok=True)
            for t in tables:
                _write_rows(audit_all.get(t, []),
                            os.path.join(adir, sub, f"{t}.csv"))
        # -- convergence summary: observed AND carried-forward ------------ #
        conv = asum.convergence_summary_rows(all_rows, all_status, budget)
        _write_rows(conv, os.path.join(adir, "convergence_summary.csv"))
        # -- scenario-level publication figures --------------------------- #
        fdir = os.path.join(adir, "figures")
        os.makedirs(fdir, exist_ok=True)
        for scen in scenarios:
            for basis in ("locf", "observed"):
                rep.figure_convergence_band(
                    conv, scen,
                    os.path.join(fdir, f"figure_band_{scen}_{basis}.png"),
                    basis=basis)
        for scen in ("S4a_ambiguity", "S4b_identifiable",
                     "S4c_out_of_domain"):
            if scen not in scenarios:
                continue
            spec = bm.SCENARIOS[scen]
            rep.figure_model_probability_reliability(
                audit_all.get("model_probabilities_long", []), scen,
                os.path.join(fdir, f"figure_model_probs_reliability_{scen}.png"),
                truth_in_family=bool(spec.well_specified),
                tracked=spec.track_correct_model or "")
        if "S6_resources" in scenarios:
            f6 = _finals(all_rows, "S6_resources")
            rep.figure_pareto_labeled(
                {k: v for k, v in f6.items() if "blind_rmse_M" in v},
                os.path.join(fdir, "figure_pareto_S6_labeled.png"))
        # -- domain checks ------------------------------------------------- #
        _write_rows(
            asum.parameter_domain_check_rows(
                lambda: __import__("sdl").ParameterSpace(
                    t_ref_K=t_ref_K, initial_guess=dict(guess)),
                scenarios, bm.SCENARIOS, bm.check_truth_in_domain),
            os.path.join(adir, "parameter_domain_checks.csv"))
        # -- representative NMR examples (own fixed seed, after the run) -- #
        if cfg.get("audit_examples", True):
            edir = os.path.join(adir, "nmr_examples")
            _write_rows(nex.generate(bm.ACQ, bm.NMR_NUISANCE_TRUE, edir),
                        os.path.join(edir, "nmr_examples_summary.csv"))
            rep.figure_nmr_examples(
                nex.spectra_for_plot(bm.ACQ, bm.NMR_NUISANCE_TRUE),
                os.path.join(fdir, "figure_nmr_examples.png"))
        # -- run integrity -------------------------------------------------- #
        integrity = asum.run_integrity_report(all_rows, all_status, scenarios,
                                              seeds, budget, bm.SCENARIOS)
        with open(os.path.join(adir, "run_integrity_report.json"), "w") as fh:
            json.dump(integrity, fh, indent=2, default=str)
        print(f"saved: {os.path.relpath(os.path.join(adir, 'run_integrity_report.json'))}")
        if not integrity["complete"]:
            print("  RUN INTEGRITY: " + "; ".join(integrity["problems"]))
        else:
            print(f"  run integrity OK: {integrity['n_campaigns']} campaigns, "
                  f"{integrity['n_round_rows']} round rows, no gaps")

    # ---- reproducibility record ----------------------------------------- #
    fp_rows = [r for r in all_rows
               if r["scenario"] in ("S1_ideal", "S2_nmr")
               and r["strategy"] == "F"]
    n_fp = sum(1 for r in fp_rows if r["gov_state"] == "MODEL_INADEQUATE")
    with open(os.path.join(outdir, "benchmark_config.json"), "w") as fh:
        json.dump({
            "framework_version": "v3",
            "CONFIG": {k: v for k, v in cfg.items()},
            "mode_resolved": {"seeds": list(seeds), "budget": budget,
                              "scenarios": list(scenarios)},
            # execution environment: affects WALL TIME only.  Every result
            # file is reassembled in submission order and every campaign is
            # seeded from its own (scenario, strategy, seed), so these
            # numbers do not enter any reported quantity.
            "execution": {"n_workers_resolved": n_proc,
                          "threads_per_worker": threads,
                          "cpu_count": os.cpu_count(),
                          "start_method": "spawn" if n_proc > 1 else "none",
                          "platform": sys.platform},
            "runtimes_s": runtimes,
            "per_round_false_inadequacy_S1_S2":
                (n_fp / len(fp_rows)) if fp_rows else None,
            "governor_validation": gov,
            "truth": bm.TRUTH, "geometry": bm.GEOMETRY, "design": bm.DESIGN,
            "scenarios": {k: dataclasses.asdict(v)
                          for k, v in bm.SCENARIOS.items()
                          if k in scenarios},
            "nmr_nuisance_true": dataclasses.asdict(bm.NMR_NUISANCE_TRUE),
            "acquisition": dataclasses.asdict(bm.ACQ),
            "transfer_true": dataclasses.asdict(bm.TRANSFER_TRUE),
        }, fh, indent=2, default=str)
    if audit_on:
        # LAST, so the checksums cover every file the run produced
        manifest = asum.reproducibility_manifest(
            outdir, os.path.dirname(os.path.abspath(__file__)),
            cfg, {"seeds": list(seeds), "budget": budget,
                  "scenarios": list(scenarios),
                  "governor_mc_seeds": list(gov_seeds),
                  "n_workers_resolved": n_proc,
                  "threads_per_worker": threads,
                  "nmr_example_seed": nex.EXAMPLE_SEED},
            {"runtimes_s": runtimes})
        mp_path = os.path.join(outdir, "audit",
                               "reproducibility_manifest.json")
        with open(mp_path, "w") as fh:
            json.dump(manifest, fh, indent=2, default=str)
        print(f"saved: {os.path.relpath(mp_path)}  "
              f"({len(manifest['checksums']['files'])} files checksummed)")

    if bar is not None:
        bar.n = bar.total          # snap to 100% (weights are estimates)
        bar.refresh()
        bar.close()
    print(f"\nBenchmark finished in {(time.time() - t0) / 60.0:.1f} min. "
          f"Outputs in: {os.path.relpath(outdir)}")


if __name__ == "__main__":
    # Required before any pool is created when this script is frozen into a
    # Windows executable; a no-op otherwise.  The __main__ guard itself is
    # what makes `spawn` safe on Windows and macOS.
    multiprocessing.freeze_support()
    main()
