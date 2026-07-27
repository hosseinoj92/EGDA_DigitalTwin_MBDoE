"""
Run-output plumbing: self-describing result folders and plot-paired CSVs.

Two conventions are enforced package-wide:

  1. EVERY figure has a sibling CSV holding exactly the plotted data, written
     by the plotting functions themselves (`plotting._save_with_data`), so a
     figure can always be re-drawn or re-analyzed without re-running the
     simulation.  Same basename, `.csv` instead of `.png`.

  2. EVERY run writes into a folder whose NAME encodes the hyperparameters
     that produced it (`run_tag`), so scenarios never overwrite each other
     and a directory listing is a readable experiment index, e.g.

         results/
           base_case__cat-H2SO4_rev_T70C_L200mm_ID18.0mm_EGDA0.50M_cat1.00M_Q5.0+5.0/
           base_case__cat-NaOH_T40C_L200mm_ID18.0mm_EGDA0.50M_cat0.75M_Q5.0+5.0/

     A `run_config.json` written next to the outputs carries the FULL config
     (the folder name is a readable summary, the JSON is the exact record).
"""

from __future__ import annotations

import json
import os
from typing import Dict, Iterable, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Folder naming
# ---------------------------------------------------------------------------
def _num(value: float, digits: int = 2) -> str:
    """Compact fixed-point number, trailing FRACTIONAL zeros trimmed
    ('0.50' -> '0.5', '150.00' -> '150' -- never '15')."""
    txt = f"{value:.{digits}f}"
    if "." in txt:
        txt = txt.rstrip("0").rstrip(".")
    return txt if txt not in ("", "-") else "0"


def sanitize(text: str) -> str:
    """Make a string safe for a directory name on Windows and POSIX."""
    bad = '<>:"/\\|?*'
    out = "".join("-" if ch in bad else ch for ch in str(text))
    return out.strip().strip(".").replace(" ", "-") or "unnamed"


def run_tag(cfg: Dict, *, prefix: str = "", sweep: bool = False) -> str:
    """Folder name encoding the hyperparameters of one run.

    Fields (omitted when not applicable):
        cat-<catalyst>[_rev|_irr]   catalyst system and reversibility
        T<t>C  or  T<lo>-<hi>C-<n>pts   temperature (single or swept)
        L<len>mm_ID<dia>mm          reactor geometry
        EGDA<c>M_cat<c>M            feed molarities
        Q<q1>+<q2>                  stream flow rates, mL/min
    """
    s1, s2 = cfg["stream1"], cfg["stream2"]
    geo, cat = cfg["reactor"], cfg["catalyst"]

    parts = [f"cat-{sanitize(cat)}"]
    if cat == "H2SO4":
        parts.append("rev" if cfg.get("equilibrium", {}).get("reversible", True)
                     else "irr")
    if sweep:
        parts.append(f"T{_num(cfg['T_min_C'], 0)}-{_num(cfg['T_max_C'], 0)}C"
                     f"-{cfg['n_points']}pts")
    else:
        parts.append(f"T{_num(cfg['temp_C'], 0)}C")
    parts.append(f"L{_num(geo['length_m'] * 1e3, 0)}mm"
                 f"_ID{_num(geo['diameter_m'] * 1e3)}mm")
    parts.append(f"EGDA{_num(s1['C_EGDA_M'])}M_cat{_num(s2['C_cat_M'])}M")
    parts.append(f"Q{_num(s1['Q_mL_min'])}+{_num(s2['Q_mL_min'])}")

    tag = "_".join(parts)
    return f"{sanitize(prefix)}__{tag}" if prefix else tag


def resolve_root(outdir: str, anchor_file: str) -> str:
    """Absolute output root; relative paths resolve next to `anchor_file`."""
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.path.dirname(os.path.abspath(anchor_file)),
                              outdir)
    os.makedirs(outdir, exist_ok=True)
    return outdir


def make_run_dir(root: str, tag: str) -> str:
    """Create (or reuse) the tagged run folder under `root`."""
    path = os.path.join(root, tag)
    os.makedirs(path, exist_ok=True)
    return path


def write_run_config(run_dir: str, cfg: Dict, extra: Dict = None) -> str:
    """Persist the exact configuration that produced this folder."""
    payload = {"config": cfg}
    if extra:
        payload.update(extra)
    path = os.path.join(run_dir, "run_config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------
def write_columns_csv(path: str, columns: Dict[str, Sequence[float]],
                      fmt: str = "%.8e") -> str:
    """Write named equal-length numeric columns as a headed CSV."""
    names = list(columns)
    if not names:
        raise ValueError(f"No columns to write for '{path}'.")
    data = [np.asarray(columns[n], dtype=float).ravel() for n in names]
    n = len(data[0])
    for name, col in zip(names, data):
        if len(col) != n:
            raise ValueError(f"Column '{name}' has length {len(col)}, "
                             f"expected {n} (file '{path}').")
    np.savetxt(path, np.column_stack(data), delimiter=",",
               header=",".join(names), comments="", fmt=fmt)
    return path


def write_rows_csv(path: str, header: Sequence[str],
                   rows: Iterable[Sequence]) -> str:
    """Write heterogeneous rows (numbers and strings) as a headed CSV."""
    import csv

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(header))
        writer.writerows(rows)
    return path


def csv_beside(png_path: str) -> str:
    """CSV path paired with a figure path ('foo.png' -> 'foo.csv')."""
    base, _ = os.path.splitext(png_path)
    return base + ".csv"
