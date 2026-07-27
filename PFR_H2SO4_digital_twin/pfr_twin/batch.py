"""
Batch-study plumbing: turn lists of parameter values into a list of configs.

A batch is declared as a base CONFIG plus a `VARY` dictionary mapping
DOTTED PARAMETER PATHS to lists of values, e.g.

    VARY = {
        "temp_C":              [70, 100, 130],
        "reactor.length_m":    [0.06, 0.20],
        "stream2.C_cat_M":     [0.5, 1.5],
    }

Two expansion modes:

  "grid" (default) - full factorial: every combination of every list, so the
      example above yields 3 x 2 x 2 = 12 scenarios.  Use it to map a design
      space.
  "zip" - paired lists walked together (all lists must share one length), so
      the example would need 3-long lists and yield 3 scenarios.  Use it for
      hand-picked scenarios such as (cold + long tube), (hot + short tube).

Each scenario carries the overrides that produced it, which become both the
folder name suffix and the columns of the batch index CSV.
"""

from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple


@dataclass
class Scenario:
    """One point of a batch: a complete config plus the overrides applied."""
    index: int
    config: Dict
    overrides: Dict[str, Any]

    def label(self, max_len: int = 48) -> str:
        """Compact human-readable label, e.g. 'temp_C=100, length_m=0.06'."""
        if not self.overrides:
            return f"scenario {self.index}"
        parts = [f"{path.split('.')[-1]}={_fmt(v)}"
                 for path, v in self.overrides.items()]
        text = ", ".join(parts)
        return text if len(text) <= max_len else text[:max_len - 1] + "…"


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        txt = f"{value:g}"
        return txt
    return str(value)


def get_path(cfg: Dict, path: str) -> Any:
    """Read a dotted path out of a nested config ('stream1.C_EGDA_M')."""
    node = cfg
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"Config has no parameter path '{path}'.")
        node = node[key]
    return node


def set_path(cfg: Dict, path: str, value: Any) -> None:
    """Write a dotted path into a nested config, in place."""
    keys = path.split(".")
    node = cfg
    for key in keys[:-1]:
        if key not in node or not isinstance(node[key], dict):
            raise KeyError(f"Config has no parameter path '{path}'.")
        node = node[key]
    if keys[-1] not in node:
        raise KeyError(f"Config has no parameter path '{path}'.")
    node[keys[-1]] = value


def expand(base: Dict, vary: Dict[str, Sequence[Any]],
           mode: str = "grid") -> List[Scenario]:
    """Expand a base config and per-parameter value lists into scenarios."""
    if mode not in ("grid", "zip"):
        raise ValueError(f"Unknown batch mode '{mode}'; use 'grid' or 'zip'.")
    if not vary:
        return [Scenario(index=0, config=copy.deepcopy(base), overrides={})]

    paths = list(vary)
    for path in paths:                      # fail fast on typos
        get_path(base, path)
    value_lists = [list(vary[p]) for p in paths]
    for path, values in zip(paths, value_lists):
        if not values:
            raise ValueError(f"Parameter '{path}' has an empty value list.")

    if mode == "grid":
        combos: Iterable[Tuple] = itertools.product(*value_lists)
    else:
        lengths = {len(v) for v in value_lists}
        if len(lengths) != 1:
            raise ValueError(
                "mode='zip' requires equal-length value lists; got "
                + ", ".join(f"{p}:{len(v)}" for p, v in zip(paths, value_lists)))
        combos = zip(*value_lists)

    scenarios = []
    for i, combo in enumerate(combos):
        cfg = copy.deepcopy(base)
        overrides = {}
        for path, value in zip(paths, combo):
            set_path(cfg, path, value)
            overrides[path] = value
        scenarios.append(Scenario(index=i, config=cfg, overrides=overrides))
    return scenarios


def index_rows(scenarios: Sequence[Scenario],
               metrics: Sequence[Dict[str, float]],
               run_dirs: Sequence[str]) -> Tuple[List[str], List[List]]:
    """Header and rows of the batch index table: overrides + metrics + folder."""
    import os

    var_cols = list(scenarios[0].overrides) if scenarios else []
    metric_cols: List[str] = []
    for m in metrics:
        for key in m:
            if key not in metric_cols:
                metric_cols.append(key)
    header = ["scenario", "label"] + var_cols + metric_cols + ["run_dir"]
    rows = []
    for sc, m, d in zip(scenarios, metrics, run_dirs):
        row = [sc.index, sc.label()]
        row += [sc.overrides.get(c, "") for c in var_cols]
        row += [m.get(c, "") for c in metric_cols]
        row.append(os.path.basename(d))
        rows.append(row)
    return header, rows
