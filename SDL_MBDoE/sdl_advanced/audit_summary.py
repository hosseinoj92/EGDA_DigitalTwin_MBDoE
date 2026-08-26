"""
Run-level audit artifacts: convergence summaries that survive failed
campaigns, a run-integrity check, a reproducibility manifest, and the
parameter-domain report.

All of it is post-processing of files the benchmark has already written.

THE SURVIVORSHIP PROBLEM, and why every convergence number appears twice.
A campaign that pauses on a measurement fault stops producing rounds.  If
round-8 statistics are then computed over "whatever rows exist at round 8",
the paused campaigns quietly leave the sample, and the surviving ones are
exactly the ones that never hit trouble - the curve improves for a reason
that has nothing to do with the estimator.  Two summaries are therefore
written side by side for every (scenario, strategy, round, metric):

    basis="observed"  only the campaigns that actually reached this round.
                      Honest about what it measures, but the sample SHRINKS
                      down the x-axis; `n_observed` says by how much.
    basis="locf"      every campaign is carried to the full budget by
                      holding its LAST OBSERVED value (last observation
                      carried forward).  The sample size is constant at
                      `n_total`, so curves are comparable across rounds, at
                      the cost of assuming a paused campaign would not have
                      improved further - a conservative assumption, and the
                      one that cannot flatter the method.

Neither is "the" answer; reporting only one of them would be the error.
`n_total`, `n_observed` and `n_faulted_cumulative` are on every row so a
reader can see immediately which rows rest on a thinned sample.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from typing import Dict, List, Optional, Sequence

import numpy as np

from .efficiency import stable_seed

METRICS = ("param_err_pct", "blind_rmse_M", "max_rel_ci_pct", "p_correct",
           "model_entropy", "time_s", "egda_mol", "energy_kJ",
           "nmr_acquisitions", "spatial_samples")


def _boot_ci_median(x: np.ndarray, B: int = 2000, seed: int = 0):
    """Bootstrap CI of the median.

    Its own generator, seeded from a fixed constant: this runs after every
    campaign has finished, so it cannot perturb the campaign RNG streams,
    and the same input always gives the same interval."""
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if x.size < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    s = np.array([np.median(rng.choice(x, x.size)) for _ in range(B)])
    return float(np.quantile(s, 0.025)), float(np.quantile(s, 0.975))


# ------------------------------------------------------------------------- #
def convergence_summary_rows(rows: List[Dict], status: List[Dict],
                             budget: int) -> List[Dict]:
    out: List[Dict] = []
    scen_strats = sorted({(r["scenario"], r["strategy"]) for r in rows})
    for scen, strat in scen_strats:
        sel = [r for r in rows if r["scenario"] == scen
               and r["strategy"] == strat]
        st = [s for s in status if s["scenario"] == scen
              and s["strategy"] == strat]
        seeds = sorted({r["seed"] for r in sel})
        n_total = len(seeds)
        planned = max([int(s.get("rounds_planned", budget)) for s in st]
                      or [budget])
        max_round = max([int(r["round"]) for r in sel] + [planned])
        # per-seed round -> row, for the carry-forward
        by_seed: Dict[int, Dict[int, Dict]] = {}
        for r in sel:
            by_seed.setdefault(r["seed"], {})[int(r["round"])] = r
        fault_round = {}
        for s in st:
            if int(s.get("faulted", 0)):
                fault_round[s["seed"]] = int(s.get("rounds_completed", 0)) + 1
        for rnd in range(1, max_round + 1):
            obs = {sd: by_seed[sd][rnd] for sd in seeds
                   if rnd in by_seed.get(sd, {})}
            # LOCF: last available round <= rnd for every seed
            locf = {}
            for sd in seeds:
                have = [q for q in by_seed.get(sd, {}) if q <= rnd]
                if have:
                    locf[sd] = by_seed[sd][max(have)]
            n_fault_cum = sum(1 for sd, fr in fault_round.items()
                              if fr <= rnd)
            for metric in METRICS:
                for basis, sample in (("observed", obs), ("locf", locf)):
                    vals = np.array(
                        [float(r.get(metric, np.nan)) for r in sample.values()],
                        dtype=float)
                    fin = vals[np.isfinite(vals)]
                    lo, hi = _boot_ci_median(fin, seed=stable_seed(
                        (scen, strat, rnd, metric, basis)))
                    out.append({
                        "scenario": scen, "strategy": strat,
                        "round": rnd, "metric": metric, "basis": basis,
                        "n_total": n_total,
                        "n_observed": len(obs),
                        "n_in_summary": int(fin.size),
                        "n_faulted_cumulative": n_fault_cum,
                        "median": float(np.median(fin)) if fin.size
                        else float("nan"),
                        "q25": float(np.quantile(fin, 0.25)) if fin.size
                        else float("nan"),
                        "q75": float(np.quantile(fin, 0.75)) if fin.size
                        else float("nan"),
                        "mean": float(np.mean(fin)) if fin.size
                        else float("nan"),
                        "boot_ci_lo": lo, "boot_ci_hi": hi,
                    })
    return out


# ------------------------------------------------------------------------- #
def parameter_domain_check_rows(space_factory, scenarios: Sequence[str],
                                specs: Dict, check_fn) -> List[Dict]:
    """Truth vs candidate-parameter bounds, per scenario per parameter.

    Reads the hidden truth, which is legitimate here: this is benchmark
    construction, the same call `run_advanced_benchmark` already makes to
    refuse a scenario declared well-specified whose truth is outside the
    box.  A controller can never reach it."""
    out: List[Dict] = []
    for name in scenarios:
        spec = specs[name]
        space = space_factory()
        rep = check_fn(space, spec.truth)
        lo, hi = space.bounds()
        for q, key in enumerate(space.param_keys):
            d = rep["detail"].get(key)
            v = space.to_vector({**space.initial_guess, **spec.truth})[q]
            out.append({
                "scenario": name,
                "declared_well_specified": int(bool(spec.well_specified)),
                "scenario_ok": int(bool(rep["ok"])),
                "param": key,
                "truth_natural": float(spec.truth.get(key, float("nan"))),
                "truth_scaled": float(v),
                "bound_lo_scaled": float(lo[q]),
                "bound_hi_scaled": float(hi[q]),
                "dist_to_lo_scaled": float(v - lo[q]),
                "dist_to_hi_scaled": float(hi[q] - v),
                "inside": int(bool(d["inside"])) if d else -1,
                "margin_scaled": float(d["margin_scaled"]) if d
                else float("nan"),
                "enough_margin": int(bool(d["enough_margin"])) if d else -1,
                "is_estimated_param": int(d is not None),
            })
    return out


# ------------------------------------------------------------------------- #
def run_integrity_report(rows: List[Dict], status: List[Dict],
                         scenarios: Sequence[str], seeds: Sequence[int],
                         budget: int, specs: Dict) -> Dict:
    """Did the run actually produce what was asked for?

    Reports rather than raises: a faulted campaign is a legitimate outcome
    the framework is designed to surface, not a broken run.  `complete` is
    the single flag that says whether anything is MISSING as opposed to
    merely paused."""
    problems: List[str] = []
    per: List[Dict] = []
    seen_keys = set()
    dupes = 0
    for r in rows:
        k = (r["scenario"], r["strategy"], r["seed"], r["round"])
        if k in seen_keys:
            dupes += 1
        seen_keys.add(k)
    for scen in scenarios:
        spec = specs[scen]
        b = spec.budget_override or budget
        for strat in spec.strategies:
            st = [s for s in status if s["scenario"] == scen
                  and s["strategy"] == strat]
            got_seeds = sorted({s["seed"] for s in st})
            missing = sorted(set(seeds) - set(got_seeds))
            faulted = [s["seed"] for s in st if int(s.get("faulted", 0))]
            short = [{"seed": s["seed"],
                      "rounds_completed": int(s["rounds_completed"]),
                      "stop_reason": s.get("stop_reason", "")}
                     for s in st
                     if int(s["rounds_completed"]) < b]
            per.append({
                "scenario": scen, "strategy": strat,
                "seeds_expected": len(seeds), "seeds_completed": len(got_seeds),
                "seeds_missing": missing,
                "rounds_planned": b,
                "n_faulted": len(faulted), "faulted_seeds": faulted,
                "n_short_campaigns": len(short),
                "short_campaigns": short[:50],
            })
            if missing:
                problems.append(
                    f"{scen}/{strat}: {len(missing)} seed(s) produced no "
                    f"campaign at all: {missing}")
    if dupes:
        problems.append(f"{dupes} duplicate (scenario, strategy, seed, round) "
                        "row(s) in benchmark_rounds.csv")
    n_nan = sum(1 for r in rows
                if not np.isfinite(float(r.get("param_err_pct", np.nan))))
    return {
        "complete": not problems,
        "problems": problems,
        "n_round_rows": len(rows),
        "n_campaigns": len(status),
        "n_duplicate_round_rows": dupes,
        "n_rows_with_nonfinite_param_err": n_nan,
        "seeds_expected": list(seeds),
        "budget": budget,
        "by_scenario_strategy": per,
    }


# ------------------------------------------------------------------------- #
def _git_commit(repo_dir: str) -> Dict[str, str]:
    def run(*args):
        try:
            return subprocess.check_output(
                args, cwd=repo_dir, stderr=subprocess.DEVNULL,
                timeout=15).decode().strip()
        except Exception:
            return ""
    return {"commit": run("git", "rev-parse", "HEAD"),
            "branch": run("git", "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(run("git", "status", "--porcelain")),
            "describe": run("git", "describe", "--always", "--dirty")}


def _package_versions() -> Dict[str, str]:
    out = {"python": sys.version.split()[0]}
    for mod in ("numpy", "scipy", "matplotlib", "tqdm"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            out[mod] = "not installed"
    return out


def _checksums(outdir: str, max_bytes: int = 400 * 1024 * 1024) -> Dict:
    """SHA-256 of every produced file, so a reader can verify the tables
    they have are the tables this manifest describes."""
    sums, skipped = {}, []
    for root, _dirs, files in os.walk(outdir):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, outdir)
            if fn == "reproducibility_manifest.json":
                continue                     # cannot hash itself
            try:
                size = os.path.getsize(p)
                if size > max_bytes:
                    skipped.append(rel)
                    continue
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                sums[rel] = {"sha256": h.hexdigest(), "bytes": size}
            except OSError:
                skipped.append(rel)
    return {"files": sums, "skipped_too_large": skipped}


def reproducibility_manifest(outdir: str, repo_dir: str, cfg: Dict,
                             resolved: Dict, extra: Optional[Dict] = None
                             ) -> Dict:
    return {
        "git": _git_commit(repo_dir),
        "config_as_written": cfg,
        "config_resolved": resolved,
        "packages": _package_versions(),
        "platform": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python_build": " ".join(platform.python_build()),
        },
        "environment": {k: os.environ.get(k) for k in
                        ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                         "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                         "NUMEXPR_NUM_THREADS")},
        **(extra or {}),
        "checksums": _checksums(outdir),
    }
