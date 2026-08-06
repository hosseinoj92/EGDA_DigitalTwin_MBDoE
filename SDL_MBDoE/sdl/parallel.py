"""
Parallel evaluation of the campaign's two heavy loops.

Where the time actually goes
----------------------------
A campaign is dominated by one operation repeated tens of thousands of times:
build the information matrix  M_u = S_u' Sigma_u^-1 S_u  of ONE candidate
operating condition, which costs (p+1) or (2p+1) Layer 1 PFR integrations.
It is called from exactly two places:

  * `identifiability.information_matrices` - once per candidate, before the
    campaign starts (central differences);
  * `design.MBDoESelector.select`          - once per candidate, in every
    autonomous round (forward differences).

On the default acid configuration that is ~4400 candidates x 7 integrations
per round: ~100 s for the grid sweep of a single `select()` call, and ~155 s
for the screen.  Everything else - the least-squares fits, the accumulated
FIM, the reporting - is a few seconds in total and is deliberately left
serial.

Two grains, because there are two shapes of work
------------------------------------------------
COARSE (`information_matrices`): thousands of independent candidates.  Chunk
the candidate list; each task is ~1 s of work, so dispatch cost vanishes.

FINE (`condition_information_fanned`): the continuous refinement that follows
the grid sweep.  Powell is strictly sequential - it proposes one design point,
waits for its score, then proposes the next - so there is no candidate list
left to chunk, and on the default config it is the LARGER half of a
`select()` call (~130 s of the ~230 s).  What is still independent there is
the finite-difference fan of the single point under evaluation: p+1
integrations at ~8 ms each, which is coarse enough to dispatch (measured
~7x on 16 cores).  Anything finer than one integration is not.

Why the results do not change
-----------------------------
Each M_u depends only on (bridge, parameter space, noise model, sampling
positions, species, theta, u).  There is no shared state, no accumulation,
and no RNG: the candidates are pure functions of their input.  This module
therefore

  * splits the candidate list into CONTIGUOUS chunks,
  * maps them with `Executor.map`, which yields results in submission order,
  * and concatenates them back in the original candidate order,

so the returned list is element-for-element the same object sequence the
serial loop produces.  The callers then reduce it exactly as before (a strict
`>` scan, i.e. first-maximum wins), which makes the selected experiment - and
hence every estimate, figure and CSV written afterwards - bit-identical for
any worker count, including 1.  `tests/self_test.py` asserts this.

Backends
--------
"process"  the useful one.  `solve_ivp` spends its time in a Python-level RHS
           closure, so the GIL is held throughout and only separate processes
           give real concurrency.
"thread"   provided for debugging (tracebacks and profilers stay in one
           process); it will NOT speed the campaign up, for the reason above.
"serial"   no pool at all - identical to workers=1.

There is deliberately no GPU backend.  The forward model is a single adaptive
LSODA integration of a 6-state, mildly nonlinear ODE with a Python right-hand
side; each solve is a long chain of sequential, data-dependent steps on ~50
numbers.  That is the shape of problem a GPU is worst at, and dispatching it
per candidate would be slower than the CPU is now.  A GPU only becomes useful
if the 4400 candidates are integrated SIMULTANEOUSLY as one batched system
with a fixed-step integrator - which means replacing Layer 1's adaptive
solver, changing the numbers it produces, and giving up the identical-output
guarantee above.  Process parallelism buys ~n_cores with none of that.
"""

from __future__ import annotations

import atexit
import os
import warnings
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.linalg import solve_triangular

from .layer1_bridge import Layer1Bridge, OperatingConditions
from .observation import NoiseModel
from .parameters import ParameterSpace

#: Windows waits on process handles with WaitForMultipleObjects, which caps
#: out at 64 handles; CPython refuses more than 61 pool workers there.
_MAX_PROCESS_WORKERS = 61

_BACKENDS = ("process", "thread", "serial")

#: Kept at one thread per worker: the linear algebra here is 6x6, so a
#: threaded BLAS only oversubscribes the cores the pool is already using.
#: Children inherit these at spawn, i.e. BEFORE they import numpy, which is
#: the only point at which the thread pools can still be sized.
_THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


@dataclass(frozen=True)
class ParallelConfig:
    """How to spread the candidate sweeps over the machine.

    workers            "auto" (or 0/None) = every logical core; 1 = serial.
    backend            "process" | "thread" | "serial" (see module docstring).
    chunks_per_worker  How finely the candidate list is cut.  More chunks
                       balance uneven per-candidate cost (a hot, fast-reacting
                       condition needs more integration steps than a cold one)
                       at the price of more dispatches; 4 keeps a chunk at
                       ~1 s of work on the default grid.
    """
    workers: Union[int, str, None] = 1
    backend: str = "process"
    chunks_per_worker: int = 4

    def __post_init__(self) -> None:
        if self.backend not in _BACKENDS:
            raise ValueError(f"Unknown parallel backend '{self.backend}'; "
                             f"expected one of {_BACKENDS}.")
        if int(self.chunks_per_worker) < 1:
            raise ValueError("chunks_per_worker must be at least 1.")
        self.n_workers          # validates `workers`

    @property
    def n_workers(self) -> int:
        """Resolved worker count (>= 1)."""
        if self.backend == "serial":
            return 1
        spec = self.workers
        if spec is None or spec == 0 or (isinstance(spec, str)
                                         and spec.lower() == "auto"):
            n = os.cpu_count() or 1
        else:
            n = int(spec)
            if n < 1:
                raise ValueError(f"workers must be >= 1 or 'auto', got {spec!r}.")
        return min(n, _MAX_PROCESS_WORKERS) if self.backend == "process" else n

    @property
    def enabled(self) -> bool:
        return self.backend != "serial" and self.n_workers > 1

    def describe(self) -> str:
        if not self.enabled:
            return "serial (1 worker)"
        return f"{self.n_workers} {self.backend} workers"


# ---------------------------------------------------------------------- #
# One long-lived pool.  Rebuilding it per round would pay the Windows spawn
# cost (a fresh numpy/scipy import per worker) on every MBDoE selection.
_POOL: Optional[Executor] = None
_POOL_KEY: Optional[Tuple[str, int]] = None


def _get_executor(cfg: ParallelConfig) -> Executor:
    global _POOL, _POOL_KEY
    key = (cfg.backend, cfg.n_workers)
    if _POOL is not None and _POOL_KEY == key:
        return _POOL
    shutdown_pool()
    if cfg.backend == "process":
        for var in _THREAD_ENV:
            os.environ.setdefault(var, "1")
        _POOL = ProcessPoolExecutor(max_workers=cfg.n_workers)
    else:
        _POOL = ThreadPoolExecutor(max_workers=cfg.n_workers)
    _POOL_KEY = key
    return _POOL


def shutdown_pool() -> None:
    """Release the worker pool.  Safe to call when there is none."""
    global _POOL, _POOL_KEY
    if _POOL is not None:
        _POOL.shutdown(wait=True)
    _POOL, _POOL_KEY = None, None


atexit.register(shutdown_pool)


# ---------------------------------------------------------------------- #
@dataclass(frozen=True, eq=False)
class FIMSpec:
    """Everything a worker needs to build one candidate's information matrix.

    Small and picklable by construction: the bridge holds only its geometry
    and solver settings, and the parameter space only its guess and bounds.
    """
    bridge: Layer1Bridge
    space: ParameterSpace
    noise: NoiseModel
    z_m: np.ndarray                    # axial sampling positions
    species: Tuple[str, ...]
    difference: str = "forward"        # "forward" | "central"

    def __post_init__(self) -> None:
        if self.difference not in ("forward", "central"):
            raise ValueError(f"Unknown difference scheme '{self.difference}'.")


def _fd_vectors(spec: FIMSpec, theta: np.ndarray) -> List[np.ndarray]:
    """The parameter vectors one candidate's sensitivity pass needs, in the
    order `_information_from` expects: the base point, then per parameter
    either (+h,) or (+h, -h)."""
    vecs = [theta]
    for q in range(spec.space.n_params):
        h = spec.space.fd_steps[q]
        tp = theta.copy()
        tp[q] += h
        vecs.append(tp)
        if spec.difference == "central":
            tm = theta.copy()
            tm[q] -= h
            vecs.append(tm)
    return vecs


def _information_from(spec: FIMSpec, ys: Sequence[np.ndarray]) -> np.ndarray:
    """Assemble M = S' Sigma^-1 S from the predictions of `_fd_vectors`."""
    y0 = ys[0]
    central = spec.difference == "central"
    S = np.empty((len(y0), spec.space.n_params))
    for q in range(spec.space.n_params):
        h = spec.space.fd_steps[q]
        if central:
            S[:, q] = (ys[1 + 2 * q] - ys[2 + 2 * q]) / (2.0 * h)
        else:
            S[:, q] = (ys[1 + q] - y0) / h
    chol = np.linalg.cholesky(
        spec.noise.covariance(y0, spec.species, len(spec.z_m)))
    Sw = solve_triangular(chol, S, lower=True)
    return Sw.T @ Sw


def predict(spec: FIMSpec, theta: np.ndarray,
            u: OperatingConditions) -> np.ndarray:
    """One Layer 1 integration: the atom of every cost in this module."""
    return spec.bridge.concentrations_at(spec.space.to_natural(theta), u,
                                         spec.z_m, spec.species)


def condition_information(spec: FIMSpec, theta: np.ndarray,
                          u: OperatingConditions) -> np.ndarray:
    """M_u = S_u' Sigma_u^-1 S_u for one operating condition, at `theta`.

    The single definition of the sensitivity pass: `InferenceModel`
    (forward differences, for candidate scoring) and the identifiability
    screen (central differences, matching `InferenceModel.sensitivity`) both
    route through here, so the serial and parallel paths cannot drift apart.

    Deliberately serial - this is what a worker runs, and nesting a pool
    inside a pool would deadlock or fork-bomb.  To spread ONE condition over
    workers, call `condition_information_fanned` from the parent instead."""
    theta = np.asarray(theta, dtype=float)
    return _information_from(
        spec, [predict(spec, v, u) for v in _fd_vectors(spec, theta)])


def _chunk_information(payload) -> List[np.ndarray]:
    """Worker entry point - module level so it pickles by reference."""
    spec, theta, conditions = payload
    return [condition_information(spec, theta, u) for u in conditions]


def _predict_one(payload) -> np.ndarray:
    """Worker entry point for the fine grain (one integration per task)."""
    spec, theta, u = payload
    return predict(spec, theta, u)


def condition_information_fanned(spec: FIMSpec, theta: np.ndarray,
                                 u: OperatingConditions,
                                 parallel: Optional[ParallelConfig] = None
                                 ) -> np.ndarray:
    """`condition_information` with the FINITE-DIFFERENCE FAN parallelised.

    For the continuous MBDoE refinement there is no candidate list to chunk:
    Powell proposes one point, waits for its score, and only then proposes the
    next.  The one thing still independent inside that step is the fan itself -
    the p+1 (or 2p+1) integrations that build S - and at ~8 ms each it is a
    coarse enough grain to be worth dispatching.

    The predictions are pure and are reassembled in fixed order, so this
    returns exactly the matrix the serial routine returns."""
    cfg = parallel if parallel is not None else ParallelConfig()
    theta = np.asarray(theta, dtype=float)
    vecs = _fd_vectors(spec, theta)
    if not cfg.enabled:
        return _information_from(spec, [predict(spec, v, u) for v in vecs])
    payloads = [(spec, v, u) for v in vecs]
    try:
        ys = list(_get_executor(cfg).map(_predict_one, payloads))
    except BrokenProcessPool as exc:
        shutdown_pool()
        warnings.warn(f"Parallel worker pool broke ({exc}); scoring this "
                      f"design point serially. Set workers=1 to avoid the "
                      f"retry.", RuntimeWarning, stacklevel=2)
        ys = [predict(spec, v, u) for v in vecs]
    return _information_from(spec, ys)


def _contiguous_chunks(items: Sequence, n_chunks: int) -> List[List]:
    """Split into <= n_chunks contiguous, near-equal, order-preserving parts."""
    n_chunks = max(1, min(int(n_chunks), len(items)))
    edges = np.linspace(0, len(items), n_chunks + 1).round().astype(int)
    return [list(items[a:b]) for a, b in zip(edges[:-1], edges[1:]) if b > a]


def information_matrices(spec: FIMSpec, theta: np.ndarray,
                         conditions: Sequence[OperatingConditions],
                         parallel: Optional[ParallelConfig] = None
                         ) -> List[np.ndarray]:
    """Per-condition information matrices, IN INPUT ORDER.

    The order guarantee is what keeps the campaign reproducible: callers rank
    the result with a strict `>` scan, so identical ordering means an
    identical winner regardless of how many workers produced it.
    """
    conditions = list(conditions)
    cfg = parallel if parallel is not None else ParallelConfig()
    if not cfg.enabled or len(conditions) < 2:
        return [condition_information(spec, theta, u) for u in conditions]

    payloads = [(spec, theta, chunk) for chunk in _contiguous_chunks(
        conditions, cfg.n_workers * int(cfg.chunks_per_worker))]
    try:
        out: List[np.ndarray] = []
        for part in _get_executor(cfg).map(_chunk_information, payloads):
            out.extend(part)
        return out
    except BrokenProcessPool as exc:
        # A worker died (out of memory, a killed child, an interpreter crash).
        # Since every chunk is a pure function of its input, recomputing the
        # whole sweep in-process is exact - it costs time, not correctness.
        shutdown_pool()
        warnings.warn(f"Parallel worker pool broke ({exc}); recomputing this "
                      f"sweep serially. Set workers=1 to avoid the retry.",
                      RuntimeWarning, stacklevel=2)
        return [condition_information(spec, theta, u) for u in conditions]
