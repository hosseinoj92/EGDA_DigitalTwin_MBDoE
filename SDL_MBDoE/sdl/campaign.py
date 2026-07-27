"""
Closed-loop campaign runner - the "self-driving" part.

For one strategy the loop is exactly the flowchart of the concept document:

    select operating condition -> run virtual PFR -> generate CPR-NMR data
    -> estimate kinetics and uncertainty -> evaluate candidates -> repeat

Strategies (the central showcase):

    A  outlet only      + fixed/predefined design
    B  spatial profile  + fixed/predefined design
    C  outlet only      + autonomous MBDoE
    D  spatial profile  + autonomous MBDoE

All strategies start from the same first experiment and the same initial
guess, and run the same experiment budget, so differences are attributable
to (i) measurement type and (ii) experiment selection only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .design import MBDoESelector
from .inference import InferenceModel, UncertaintyReport
from .layer1_bridge import OperatingConditions
from .truth import VirtualLaboratory

#                key : (spatial measurements, autonomous MBDoE)
STRATEGY_DEFS = {"A": (False, False), "B": (True, False),
                 "C": (False, True), "D": (True, True)}
STRATEGY_NAMES = {"A": "outlet + fixed design",
                  "B": "spatial + fixed design",
                  "C": "outlet + MBDoE",
                  "D": "spatial + MBDoE"}


@dataclass
class RoundRecord:
    round: int
    n_experiments: int
    n_data: int
    u: OperatingConditions
    theta_nat: Dict[str, float]
    report: UncertaintyReport
    fit_cost: float


@dataclass
class StrategyResult:
    key: str
    history: List[RoundRecord] = field(default_factory=list)
    inference: Optional[InferenceModel] = None
    stopped_early: bool = False
    stop_reason: str = "budget exhausted"


def run_strategy(key: str,
                 lab: VirtualLaboratory,
                 inference: InferenceModel,
                 fixed_design: List[OperatingConditions],
                 selector: Optional[MBDoESelector],
                 budget: int,
                 target_rel_ci_pct: Optional[float] = None,
                 verbose: bool = True) -> StrategyResult:
    spatial, autonomous = STRATEGY_DEFS[key]
    if not autonomous and len(fixed_design) < budget:
        raise ValueError(f"Fixed design has {len(fixed_design)} entries "
                         f"< budget {budget}.")
    result = StrategyResult(key=key, inference=inference)

    u_next = fixed_design[0]                 # common seed experiment for all
    for r in range(1, budget + 1):
        meas = lab.run_experiment(u_next, spatial=spatial)
        inference.add_measurement(meas)
        fit = inference.fit()
        rep = inference.uncertainty()
        result.history.append(RoundRecord(
            round=r, n_experiments=r, n_data=inference.n_data, u=u_next,
            theta_nat=inference.space.to_natural(inference.theta),
            report=rep, fit_cost=fit["cost"]))
        if verbose:
            nat = result.history[-1].theta_nat
            print(f"  [{key}] round {r}/{budget}  {u_next.label():34s} "
                  f"k1_ref={nat['k1_ref']:.3e}  Ea1={nat['Ea1_J'] / 1e3:5.1f}  "
                  f"maxCI={rep.max_rel_ci_pct:7.1f}%  "
                  f"logdetF={rep.logdet_F: .1f}")

        if (target_rel_ci_pct is not None and rep.well_posed
                and rep.max_rel_ci_pct <= target_rel_ci_pct):
            result.stopped_early = True
            result.stop_reason = (f"target reached: max 95% CI "
                                  f"{rep.max_rel_ci_pct:.1f}% <= "
                                  f"{target_rel_ci_pct:.1f}% after {r} experiments")
            break
        if r == budget:
            break
        u_next = selector.select() if autonomous else fixed_design[r]
    return result
