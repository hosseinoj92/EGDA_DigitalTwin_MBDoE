"""
Multi-model Bayesian kinetic inference:  p(M, theta | D)  via a Laplace
model ensemble.

Candidate family for the H2SO4-catalysed EGDA hydrolysis - a small,
scientifically interpretable set built entirely from EXISTING Layer 1
capabilities (no black-box models):

    M1  "rev-pitzer"   reversible hydrolysis, Pitzer H+ activity model
                       (the structure of the digital-twin truth)
    M2  "rev-dilute"   reversible, dilute-activity approximation (gamma = 1)
    M3  "irreversible" irreversible approximation (legacy twin; no Keq
                       parameters exist, so its theta is 4-dimensional)

Each candidate owns its OWN Layer1Bridge configuration, ParameterSpace,
prior and LaplacePosterior over the SHARED measurement stream.  Model
probabilities are the normalized Laplace evidences.  Particles for active
design are drawn model-by-model according to those probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from sdl.inference import InferenceModel
from sdl.layer1_bridge import Layer1Bridge, OperatingConditions, \
    literature_guess
from sdl.observation import Measurement, NoiseModel
from sdl.parameters import ParameterSpace, param_keys_for, ACID_PARAM_KEYS, \
    BASE_PARAM_KEYS

from .posterior import GaussianPrior, LaplacePosterior


@dataclass(frozen=True)
class AssumedTransfer:
    """INFERENCE-SIDE transfer knowledge: only COMMANDED / CALIBRATED
    quantities (nominal line volume, sampling flow, geometry model).  It is
    a deliberate approximation of the truth-side TransferConfig - mean delay
    only, no RTD realization, no carryover state, no hidden nuisances.

        tau(z) = V(z) / Q_sample,   V(z) = V_fixed (+ v_per_m * (L - z))

    enabled=False (or zero volume) reduces every prediction exactly to the
    Layer-1 reactor composition."""
    enabled: bool = False
    Q_sample_mL_min: float = 0.5
    V_fixed_mL: float = 0.0
    geometry: str = "constant"          # "constant" | "linear"
    v_per_m_mL: float = 0.0
    length_m: float = 0.0               # reactor length for the linear model

    @classmethod
    def from_scalar_tau(cls, tau_s: float) -> "AssumedTransfer":
        """Back-compatible constructor for a plain mean-delay correction."""
        if tau_s <= 0.0:
            return cls(enabled=False)
        return cls(enabled=True, Q_sample_mL_min=60.0, V_fixed_mL=tau_s)

    def tau_s(self, z_m: np.ndarray) -> np.ndarray:
        z = np.atleast_1d(np.asarray(z_m, dtype=float))
        if not self.enabled:
            return np.zeros_like(z)
        v = np.full_like(z, self.V_fixed_mL)
        if self.geometry == "linear":
            v = v + self.v_per_m_mL * np.maximum(self.length_m - z, 0.0)
        q = max(self.Q_sample_mL_min, 1e-9) / 60.0          # mL/s
        return v / q


class TransportAwareInference(InferenceModel):
    """InferenceModel whose expected-observation operator includes the
    COMMANDED/CALIBRATED mean transfer delay tau(z) (public knowledge), so
    the kinetic model is compared against what the NMR actually sees.  The
    truth's RTD dispersion and carryover remain unmodelled - a deliberate,
    realistic imperfection of the correction.

    Because ONLY predict_at is overridden, every consumer of the operator
    (estimation, sensitivities, FIM, spatial design, EIG, diagnostics)
    inherits the correction consistently.  With transfer disabled this class
    is exactly the base InferenceModel (asserted by test)."""

    def __init__(self, *args, assumed_transfer: Optional[AssumedTransfer]
                 = None, extra_tau_s: float = 0.0, **kwargs):
        super().__init__(*args, **kwargs)
        # extra_tau_s kept for back-compatibility (scalar mean delay)
        self.assumed_transfer = (assumed_transfer
                                 if assumed_transfer is not None
                                 else AssumedTransfer.from_scalar_tau(
                                     float(extra_tau_s)))

    def predict_at(self, theta_vec: np.ndarray, u: OperatingConditions,
                   z_m: np.ndarray, species) -> np.ndarray:
        nat = self.space.to_natural(theta_vec)
        z = np.asarray(z_m, dtype=float)
        tau = self.assumed_transfer.tau_s(z)
        if not np.any(tau > 0.0):
            return self.bridge.concentrations_at(nat, u, z, tuple(species))
        return self.bridge.concentrations_at(nat, u, z, tuple(species),
                                             extra_tau_s=tau)


@dataclass
class CandidateModel:
    name: str
    description: str
    bridge: Layer1Bridge
    space: ParameterSpace
    prior: GaussianPrior
    inference: InferenceModel = None
    posterior: LaplacePosterior = None
    log_prior_prob: float = 0.0            # uniform model prior by default

    def __post_init__(self):
        if self.inference is None:
            self.inference = InferenceModel(self.space, self.bridge,
                                            NoiseModel())
        if self.posterior is None:
            self.posterior = LaplacePosterior(self.inference, self.prior)

    # ------------------------------------------------------------------ #
    def predict_observation(self, theta_vec: np.ndarray,
                            u: OperatingConditions, z_m: np.ndarray,
                            species: Sequence[str]) -> np.ndarray:
        """The candidate's expected-observation operator - the ONE way any
        controller-side code predicts a measurement under this model."""
        return self.inference.predict_at(theta_vec, u, z_m, species)

    @property
    def theta_hat(self) -> np.ndarray:
        """Current MAP if fitted, else the initial guess (for pre-data
        design)."""
        if self.posterior.theta_map is not None:
            return self.posterior.theta_map
        return self.space.to_vector(self.space.initial_guess)


@dataclass
class Particle:
    model_index: int
    theta: np.ndarray                      # scaled space of ITS model
    log_weight: float = 0.0


class ModelEnsemble:
    def __init__(self, models: Sequence[CandidateModel]):
        if not models:
            raise ValueError("Need at least one candidate model.")
        self.models = list(models)
        self.log_evidence = np.full(len(self.models), -np.inf)
        self.probs = np.full(len(self.models), 1.0 / len(self.models))

    # ------------------------------------------------------------------ #
    def add_measurement(self, m: Measurement) -> None:
        for cm in self.models:
            cm.inference.add_measurement(m)

    def update(self) -> Dict[str, float]:
        stats = {}
        for j, cm in enumerate(self.models):
            fit = cm.posterior.fit_map()
            self.log_evidence[j] = cm.posterior.log_evidence \
                + cm.log_prior_prob
            stats[cm.name] = fit["cost"]
        le = self.log_evidence - np.max(self.log_evidence)
        w = np.exp(le)
        self.probs = w / np.sum(w)
        return stats

    # ------------------------------------------------------------------ #
    @property
    def best_index(self) -> int:
        return int(np.argmax(self.probs))

    @property
    def best(self) -> CandidateModel:
        return self.models[self.best_index]

    def prob_of(self, name: str) -> float:
        for j, cm in enumerate(self.models):
            if cm.name == name:
                return float(self.probs[j])
        return 0.0

    # ------------------------------------------------------------------ #
    def particles(self, n: int, rng: np.random.Generator) -> List[Particle]:
        """n joint (M, theta) posterior draws; model counts multinomial in
        the model probabilities, theta from each model's Laplace posterior."""
        counts = rng.multinomial(n, self.probs)
        out: List[Particle] = []
        for j, (cm, c) in enumerate(zip(self.models, counts)):
            if c == 0 or cm.posterior.theta_map is None:
                continue
            for th in cm.posterior.sample(int(c), rng):
                out.append(Particle(model_index=j, theta=th))
        return out

    def predict(self, particle: Particle, u: OperatingConditions,
                z_m: np.ndarray, species: Sequence[str]) -> np.ndarray:
        """Particle prediction through the candidate's expected-observation
        operator (NOT the bare reactor model), so EIG sees the same
        transport-corrected observable as estimation does."""
        cm = self.models[particle.model_index]
        return cm.predict_observation(particle.theta, u, z_m, species)


# --------------------------------------------------------------------------- #
def build_egda_family(geometry: Dict[str, float], t_ref_K: float,
                      include: Sequence[str] = ("rev-pitzer", "rev-dilute",
                                                "irreversible"),
                      h_plus_model: str = "equilibrium",
                      ka2_model: str = "tdep",
                      fixed: Optional[Dict[str, float]] = None,
                      noise_assumed: Optional[NoiseModel] = None,
                      assumed_extra_tau_s: float = 0.0,
                      assumed_transfer: Optional[AssumedTransfer] = None
                      ) -> List[CandidateModel]:
    """The interpretable EGDA/H2SO4 candidate family (see module docstring).
    `include` lets benchmark scenarios remove the correct structure
    (Scenario 5: model inadequacy).  `fixed` pins parameters (e.g. K1_ref
    from the identifiability screen) in the reversible models.
    `noise_assumed` is the fallback covariance for measurements that carry
    no cov_y (direct-observation ablations).  `assumed_transfer` (or the
    legacy scalar `assumed_extra_tau_s`) is the inference-side transfer
    correction, shared by all candidates."""
    guess = literature_guess(t_ref_K, "H2SO4")
    fixed = dict(fixed or {})
    noise = noise_assumed or NoiseModel()
    out: List[CandidateModel] = []

    def _space(keys: Tuple[str, ...]) -> ParameterSpace:
        keys = tuple(k for k in keys if k not in fixed)
        return ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess),
                              param_keys=keys, fixed=dict(fixed))

    def _model(name: str, desc: str, sp: ParameterSpace,
               **bridge_kw) -> CandidateModel:
        bridge = Layer1Bridge(geometry, t_ref_K, h_plus_model=h_plus_model,
                              ka2_model=ka2_model, **bridge_kw)
        return CandidateModel(
            name=name, description=desc, bridge=bridge, space=sp,
            prior=GaussianPrior.from_space(sp),
            inference=TransportAwareInference(
                sp, bridge, noise, assumed_transfer=assumed_transfer,
                extra_tau_s=assumed_extra_tau_s))

    if "rev-pitzer" in include:
        out.append(_model("rev-pitzer",
                          "reversible hydrolysis, Pitzer H+ activity",
                          _space(ACID_PARAM_KEYS), activity_model="pitzer"))
    if "rev-dilute" in include:
        out.append(_model("rev-dilute",
                          "reversible hydrolysis, dilute-activity (gamma=1)",
                          _space(ACID_PARAM_KEYS), activity_model="dilute"))
    if "irreversible" in include:
        sp = ParameterSpace(t_ref_K=t_ref_K, initial_guess=dict(guess),
                            param_keys=BASE_PARAM_KEYS)
        out.append(_model("irreversible",
                          "irreversible approximation (legacy twin)",
                          sp, activity_model="dilute", reversible=False))
    if not out:
        raise ValueError(f"No known candidate in include={include}.")
    return out
