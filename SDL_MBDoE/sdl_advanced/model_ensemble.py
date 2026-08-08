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


class TransportAwareInference(InferenceModel):
    """InferenceModel whose predictions include the COMMANDED/CALIBRATED
    mean transfer delay (V_transfer / Q_sample, public knowledge), so the
    kinetic model is compared against what the NMR actually sees.  The
    truth's RTD dispersion and carryover remain unmodelled - a deliberate,
    realistic imperfection of the correction.  extra_tau_s = 0 reduces this
    exactly to the base class."""

    def __init__(self, *args, extra_tau_s: float = 0.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_tau_s = float(extra_tau_s)

    def predict(self, theta_vec: np.ndarray, m: Measurement) -> np.ndarray:
        nat = self.space.to_natural(theta_vec)
        return self.bridge.concentrations_at(nat, m.u, m.z_m, m.species,
                                             extra_tau_s=self.extra_tau_s)


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
        cm = self.models[particle.model_index]
        nat = cm.space.to_natural(particle.theta)
        return cm.bridge.concentrations_at(nat, u, np.asarray(z_m, float),
                                           tuple(species))


# --------------------------------------------------------------------------- #
def build_egda_family(geometry: Dict[str, float], t_ref_K: float,
                      include: Sequence[str] = ("rev-pitzer", "rev-dilute",
                                                "irreversible"),
                      h_plus_model: str = "equilibrium",
                      ka2_model: str = "tdep",
                      fixed: Optional[Dict[str, float]] = None,
                      noise_assumed: Optional[NoiseModel] = None,
                      assumed_extra_tau_s: float = 0.0
                      ) -> List[CandidateModel]:
    """The interpretable EGDA/H2SO4 candidate family (see module docstring).
    `include` lets benchmark scenarios remove the correct structure
    (Scenario 5: model inadequacy).  `fixed` pins parameters (e.g. K1_ref
    from the identifiability screen) in the reversible models.
    `noise_assumed` is the fallback covariance for measurements that carry
    no cov_y (direct-observation ablations)."""
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
                sp, bridge, noise, extra_tau_s=assumed_extra_tau_s))

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
