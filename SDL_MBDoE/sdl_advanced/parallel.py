"""
Cross-platform, determinism-preserving process parallelism for the benchmark.

Why processes and not threads
-----------------------------
Every campaign is CPU-bound Python (ODE solves, least squares, deconvolution)
under the GIL, so threads would not help.  Processes do, and each campaign is
already an INDEPENDENT, PURE function of (scenario, strategy, seed, budget):
`AdvancedVirtualLaboratory` seeds its own `default_rng(seed)`, the selector
seeds `default_rng(seed + offset)`, and nothing anywhere reads global RNG
state.  So the work splits with no coordination at all.

The three things that make parallel output IDENTICAL to serial output
---------------------------------------------------------------------
1. **Submission-order reassembly.**  `ordered_map` returns results indexed by
   the order tasks were SUBMITTED, never the order they finished.  Every
   downstream CSV row therefore appears in exactly the position it would have
   had in a one-core run, for any worker count.
2. **Pinned numerical threads.**  Multi-threaded BLAS can reorder floating-
   point reductions, which perturbs the last digits and can, through a long
   iterative campaign, diverge visibly.  `pin_numerical_threads(1)` fixes the
   reduction order, so the arithmetic is the same whether one campaign runs
   alone or ten run side by side.  It must be called BEFORE numpy is imported
   in the parent; children inherit it through the environment.
3. **The `spawn` start method everywhere.**  macOS (including Apple Silicon)
   and Windows already default to `spawn`; forcing it on Linux too means a
   worker is always a clean interpreter that re-imports the package rather
   than a fork inheriting parent state.  One behaviour, three platforms.

What legitimately still differs: wall-clock telemetry (`runtime_s` per
campaign, `runtimes_s` per scenario).  Those measure the run, not the
chemistry.  The simulated laboratory time `time_s` that the figures plot
against comes from `ResourceMeter`, not from the clock, and is unaffected.

This module is deliberately stdlib-only (no numpy import) so that the runner
can import it before numpy in order to pin threads.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, List, Optional, Sequence, Tuple

# Every BLAS/threading backend numpy and scipy may sit on.  VECLIB is the
# Apple Accelerate framework used by default on Apple Silicon wheels.
THREAD_ENV_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                   "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                   "NUMEXPR_NUM_THREADS")


def pin_numerical_threads(n_threads: int = 1) -> None:
    """Pin every numerical backend to `n_threads`.

    Call this BEFORE importing numpy/scipy for it to take effect in the
    current process; calling it later still configures any process spawned
    afterwards, because children inherit the environment.

    n_threads = 1 is the determinism-preserving setting and costs nothing
    here: the linear algebra in this framework is 6x6 parameter blocks and
    small spectral design matrices, well below the size where threading a
    single BLAS call pays for itself.
    """
    n = max(1, int(n_threads))
    for var in THREAD_ENV_VARS:
        os.environ[var] = str(n)


def resolve_workers(n_workers) -> int:
    """CONFIG value -> concrete process count.

        None / "auto"  ->  all cores but one (keeps the machine usable)
        0              ->  all cores
        n >= 1         ->  exactly n
    """
    cpus = os.cpu_count() or 1
    if n_workers is None or n_workers == "auto":
        return max(1, cpus - 1)
    n = int(n_workers)
    if n == 0:
        return max(1, cpus)
    return max(1, n)


def describe_workers(n_workers) -> str:
    n = resolve_workers(n_workers)
    cpus = os.cpu_count() or 1
    how = "serial (one process)" if n == 1 else f"{n} worker processes"
    return f"{how} on a {cpus}-core machine [{mp.get_start_method(allow_none=True) or 'spawn'}]"


def make_executor(n_workers, initializer: Optional[Callable] = None,
                  initargs: Tuple = ()) -> Optional[ProcessPoolExecutor]:
    """A spawn-based pool, or None when the resolved count is 1.

    Returning None for a single worker is deliberate: the caller then takes
    the plain in-process path, so a serial run has no multiprocessing
    machinery in it at all and stays byte-for-byte the previous behaviour.
    """
    n = resolve_workers(n_workers)
    if n <= 1:
        return None
    ctx = mp.get_context("spawn")           # macOS/Windows default; forced
    return ProcessPoolExecutor(max_workers=n, mp_context=ctx,
                               initializer=initializer, initargs=initargs)


def ordered_map(fn: Callable, arg_tuples: Sequence[Tuple],
                executor: Optional[ProcessPoolExecutor] = None,
                on_result: Optional[Callable[[int, Tuple, object],
                                             None]] = None) -> List:
    """Apply `fn(*args)` to every tuple, returning results in SUBMISSION order.

    `fn` must be a module-level function (picklable by qualified name) and
    both its arguments and its return value must be picklable primitives.

    `on_result(index, args, result)` is invoked in the PARENT process as each
    task lands - completion order when parallel, submission order when
    serial.  It is for progress reporting only; nothing that affects the
    saved results may depend on the order it fires in.
    """
    args = list(arg_tuples)
    out: List = [None] * len(args)
    if executor is None:                     # unchanged serial path
        for i, a in enumerate(args):
            out[i] = fn(*a)
            if on_result is not None:
                on_result(i, a, out[i])
        return out
    futures = {executor.submit(fn, *a): i for i, a in enumerate(args)}
    for fut in as_completed(futures):
        i = futures[fut]
        out[i] = fut.result()                # re-raises worker exceptions here
        if on_result is not None:
            on_result(i, args[i], out[i])
    return out
