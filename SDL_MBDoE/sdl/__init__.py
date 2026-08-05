"""
sdl - Layer 2: virtual self-driving laboratory for autonomous kinetic
discovery around the Layer 1 PFR digital twin (../PFR_H2SO4_digital_twin).

Architecture (strict truth/inference separation):

    truth.py      VirtualLaboratory  - hidden "true" parameters + observation
                                       model + synthetic CPR-NMR noise.
                                       Algorithms see ONLY its measurements.
    inference.py  InferenceModel     - parameter estimates, accumulated data,
                                       assumed covariance, sensitivities S,
                                       Fisher information F = S' Sigma^-1 S,
                                       parameter covariance V ~ F^-1.
    design.py     Experiment design  - fixed (predefined) designs and
                                       D-optimal MBDoE selection.
    campaign.py   Closed loop        - select -> run -> measure -> estimate
                                       -> repeat, for strategies A/B/C/D.
    layer1_bridge.py                 - the ONLY module that imports Layer 1.

Layer 1 is treated as an immutable high-fidelity simulator; nothing here
modifies it.
"""

__version__ = "1.0.0"

from .layer1_bridge import Layer1Bridge, OperatingConditions, literature_guess
from .parameters import ParameterSpace, PARAM_KEYS, param_keys_for
from .observation import NoiseModel, Measurement
from .truth import VirtualLaboratory
from .inference import InferenceModel, covariance_from_fim
from .design import build_candidates, build_fixed_design, MBDoESelector
from .campaign import run_strategy, STRATEGY_DEFS
from .identifiability import reference_design, screen, ScreenResult
