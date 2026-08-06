"""Pre-campaign identifiability screen.

Before a single experiment is spent, ask the question the FIM was always able
to answer but the campaign never asked: *which parameters can this measurement
setup identify anywhere in this design box?*

A structurally unidentifiable parameter left inside theta does real damage:

  * it contributes a flat direction, so F is rank-deficient and `log det F`
    collapses to -inf, which makes the D-criterion useless as a design score;
  * the bounded least-squares fit walks it to a box bound and parks it there,
    so the reported "estimate" is the constraint, not the data;
  * it then dominates any unweighted error metric averaged over theta.

On the acid route K1_ref is the textbook case.  Step 1 is
EGDA + H2O <-> EGMA + AcOH with water at ~55 M, so Q1 is driven hard to the
right and the step runs effectively to completion for any K1 near unity: the
observables barely move.  This is the same argument layer1_bridge already
makes for the van 't Hoff slopes dH1/dH2 - which it correctly holds fixed.

The screen answers it with a *reference campaign*: at the initial guess, score
every candidate in the design grid, then greedily assemble the D-optimal
`budget`-experiment design from them.  That is the best campaign this platform
could run inside these bounds, so a parameter still undetermined under it is
undetermined under any strategy being compared - drop it, and repeat, since
removing one flat direction can rescue another that was merely aliased with it.

A fixed reference design (box corners, a temperature ladder) is NOT a valid
substitute: it is just one design, and a poor one.  Screening on corners
wrongly condemns k2_ref, which the D-optimal design pins down to ~10 %.

Cost is one sensitivity pass over the candidate grid.  The per-candidate
information matrices are built once at full parameter count and sub-indexed as
parameters drop, because fixing theta_j removes its column from S but leaves
every other column untouched - so the iteration itself is free.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .inference import covariance_from_fim
from .layer1_bridge import Layer1Bridge, OperatingConditions
from .observation import NoiseModel
from .parallel import FIMSpec, ParallelConfig
from .parallel import information_matrices as _sweep
from .parameters import ParameterSpace

#: design variables of the reference box, in OperatingConditions order
_BOX_KEYS = ("T_C", "Q_total_mL_min", "C_cat_M", "C_EGDA_M")


@dataclass
class ScreenResult:
    space: ParameterSpace                 # reduced space (theta actually fit)
    dropped: Tuple[str, ...]              # keys moved to `fixed`, in drop order
    rel_ci_pct: Dict[str, float]          # best achievable 95% rel CI, per key
    n_candidates: int
    budget: int

    def summary_lines(self, threshold_pct: float) -> List[str]:
        out = [f"Identifiability screen: best achievable 95% CI under the "
               f"D-optimal {self.budget}-experiment",
               f"  design drawn from {self.n_candidates} candidates "
               f"(drop threshold {threshold_pct:g} %)"]
        for k, ci in self.rel_ci_pct.items():
            mark = "   DROPPED - held fixed" if k in self.dropped else ""
            ci_txt = "inf" if not np.isfinite(ci) else f"{ci:.4g}"
            out.append(f"    {k:8s}: {ci_txt:>12s} %{mark}")
        if self.dropped:
            out.append("  theta reduced to: " + ", ".join(self.space.param_keys))
        else:
            out.append("  all parameters identifiable - theta unchanged.")
        return out


def reference_design(dcfg: Dict,
                     include_centre: bool = True) -> List[OperatingConditions]:
    """Corners (plus centre) of the admissible box - the most informative
    design the campaign could ever be allowed to run."""
    box = dcfg["continuous_bounds"]
    levels = [tuple(float(v) for v in box[k]) for k in _BOX_KEYS]
    points = list(itertools.product(*levels))
    if include_centre:
        points.append(tuple(0.5 * (lo + hi) for lo, hi in levels))
    return [OperatingConditions(T_C=t, Q1_mL_min=q / 2.0, Q2_mL_min=q / 2.0,
                                C_cat_M=cat, C_EGDA_M=egda)
            for t, q, cat, egda in points]


def information_matrices(space: ParameterSpace, bridge: Layer1Bridge,
                         noise: NoiseModel,
                         conditions: Sequence[OperatingConditions],
                         z_m: np.ndarray, species: Sequence[str],
                         theta_vec: Optional[np.ndarray] = None,
                         parallel: Optional[ParallelConfig] = None
                         ) -> List[np.ndarray]:
    """Per-condition information M_e = S_e' Sigma_e^-1 S_e at `theta_vec`
    (default: the initial guess).  Central differences, matching
    InferenceModel.sensitivity.

    This is the whole cost of the screen - (2p+1) PFR integrations per
    candidate - and the conditions are independent, so `parallel` spreads
    them over the machine without changing the returned list (see
    sdl/parallel.py)."""
    th = space.to_vector(space.initial_guess) if theta_vec is None else theta_vec
    spec = FIMSpec(bridge=bridge, space=space, noise=noise,
                   z_m=np.asarray(z_m, dtype=float), species=tuple(species),
                   difference="central")
    return _sweep(spec, th, conditions, parallel)


def _logdet_floored(F: np.ndarray, floor: float = 1e-12) -> float:
    """log det F with eigenvalues floored, so a rank-deficient F still ranks
    sensibly in the early greedy rounds instead of collapsing to -inf."""
    return float(np.sum(np.log(np.maximum(np.linalg.eigvalsh(F), floor))))


def greedy_d_optimal(mats: Sequence[np.ndarray], budget: int) -> np.ndarray:
    """FIM of the greedy D-optimal `budget`-experiment design over `mats`."""
    p = mats[0].shape[0]
    F = np.zeros((p, p))
    for _ in range(budget):
        scores = [_logdet_floored(F + M) for M in mats]
        F = F + mats[int(np.argmax(scores))]
    return F


def screen(space: ParameterSpace, bridge: Layer1Bridge, noise: NoiseModel,
           candidates: Sequence[OperatingConditions], z_m: np.ndarray,
           species: Sequence[str], budget: int,
           max_rel_ci_pct: float = 200.0,
           parallel: Optional[ParallelConfig] = None) -> ScreenResult:
    """Iteratively hold fixed every parameter that even the best affordable
    design in this box cannot determine."""
    # Full-parameter information, computed once.  Fixing theta_j deletes its
    # column from S and leaves the others unchanged, so every reduced-space
    # information matrix is a submatrix of these.
    mats_full = information_matrices(space, bridge, noise, candidates, z_m,
                                     species, parallel=parallel)
    keys = list(space.param_keys)
    live = list(range(len(keys)))            # indices into `keys` still in theta
    guess_full = space.to_vector(space.initial_guess)
    dropped: List[str] = []
    best_ci: Dict[str, float] = {}

    while True:
        ix = np.ix_(live, live)
        F = greedy_d_optimal([M[ix] for M in mats_full], budget)
        sig = np.sqrt(np.maximum(np.diag(covariance_from_fim(F)), 0.0))
        sub = space.holding_fixed([keys[q] for q in range(len(keys))
                                   if q not in live]) if len(live) < len(keys) \
            else space
        ci = sub.rel_ci_percent(guess_full[live], sig)
        for j, q in enumerate(live):
            best_ci[keys[q]] = float(ci[j])
        worst = int(np.argmax(ci))
        if ci[worst] <= max_rel_ci_pct or len(live) <= 1:
            break
        dropped.append(keys[live[worst]])
        live.pop(worst)

    reduced = space.holding_fixed(dropped) if dropped else space
    return ScreenResult(space=reduced, dropped=tuple(dropped),
                        rel_ci_pct={k: best_ci[k] for k in keys},
                        n_candidates=len(candidates), budget=budget)
