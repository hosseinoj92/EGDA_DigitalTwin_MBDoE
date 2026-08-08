"""Tests of the common expected-observation operator (predict_at) and its
use by every controller-side prediction path.  Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import (Layer1Bridge, OperatingConditions, ParameterSpace,
                 NoiseModel, InferenceModel, literature_guess)
from sdl_advanced.model_ensemble import (AssumedTransfer,
                                         TransportAwareInference,
                                         build_egda_family, ModelEnsemble)

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
U0 = OperatingConditions(T_C=90.0, Q1_mL_min=0.5, Q2_mL_min=0.5,
                         C_EGDA_M=1.0, C_cat_M=1.0)
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")
Z = np.array([0.1, 0.3, 0.5])


def _space_theta():
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K))
    return space, space.to_vector(space.initial_guess)


def test_disabled_transfer_reduces_to_layer1():
    """Required invariant: transfer correction off -> predict_at is exactly
    the Layer-1 reactor prediction."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space, th = _space_theta()
    inf = TransportAwareInference(space, bridge, NoiseModel(),
                                  assumed_transfer=AssumedTransfer(
                                      enabled=False))
    y_op = inf.predict_at(th, U0, Z, SPECIES)
    y_l1 = bridge.concentrations_at(space.to_natural(th), U0, Z, SPECIES)
    assert np.array_equal(y_op, y_l1)
    # base InferenceModel.predict_at is the Layer-1 prediction by definition
    base = InferenceModel(space, bridge, NoiseModel())
    assert np.array_equal(base.predict_at(th, U0, Z, SPECIES), y_l1)


def test_constant_mean_delay_matches_scalar_extra_tau():
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space, th = _space_theta()
    tau = 40.0
    inf = TransportAwareInference(
        space, bridge, NoiseModel(),
        assumed_transfer=AssumedTransfer(enabled=True, Q_sample_mL_min=0.6,
                                         V_fixed_mL=0.4))   # 0.4/0.01 = 40 s
    y_op = inf.predict_at(th, U0, Z, SPECIES)
    y_ref = bridge.concentrations_at(space.to_natural(th), U0, Z, SPECIES,
                                     extra_tau_s=tau)
    assert np.max(np.abs(y_op - y_ref)) < 1e-10
    # and the correction must actually matter at these conditions
    y_l1 = bridge.concentrations_at(space.to_natural(th), U0, Z, SPECIES)
    assert np.max(np.abs(y_op - y_l1)) > 1e-4


def test_position_dependent_delay_changes_predictions():
    """A linear transfer geometry (longer path from deeper positions) must
    give a LARGER correction at small z than at the outlet."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space, th = _space_theta()
    at = AssumedTransfer(enabled=True, Q_sample_mL_min=0.6, V_fixed_mL=0.1,
                         geometry="linear", v_per_m_mL=0.6,
                         length_m=GEOM["length_m"])
    tau = at.tau_s(Z)
    assert tau[0] > tau[-1] > 0.0            # inlet-most sample delayed most
    inf = TransportAwareInference(space, bridge, NoiseModel(),
                                  assumed_transfer=at)
    y_lin = inf.predict_at(th, U0, Z, SPECIES)
    inf_c = TransportAwareInference(
        space, bridge, NoiseModel(),
        assumed_transfer=AssumedTransfer(enabled=True, Q_sample_mL_min=0.6,
                                         V_fixed_mL=0.1))
    y_const = inf_c.predict_at(th, U0, Z, SPECIES)
    d = np.abs(y_lin - y_const).reshape(len(SPECIES), len(Z))
    # the constant part matches at the outlet; the difference grows inward
    assert np.max(d[:, 0]) > np.max(d[:, -1])


def test_all_ensemble_paths_share_the_operator():
    """ModelEnsemble.predict / CandidateModel.predict_observation /
    inference.predict must all agree (single operator, no bypass)."""
    at = AssumedTransfer(enabled=True, Q_sample_mL_min=0.6, V_fixed_mL=0.3)
    fam = build_egda_family(GEOM, T_REF_K, include=("rev-dilute",),
                            noise_assumed=NoiseModel(), assumed_transfer=at)
    ens = ModelEnsemble(fam)
    cm = fam[0]
    th = cm.space.to_vector(cm.space.initial_guess)
    from sdl.observation import Measurement
    from sdl_advanced.model_ensemble import Particle
    y1 = cm.predict_observation(th, U0, Z, SPECIES)
    y2 = ens.predict(Particle(model_index=0, theta=th), U0, Z, SPECIES)
    m = Measurement(u=U0, z_m=Z, species=SPECIES,
                    y=np.zeros(len(Z) * len(SPECIES)))
    y3 = cm.inference.predict(th, m)
    assert np.array_equal(y1, y2) and np.array_equal(y1, y3)
    # and it differs from the bare reactor state (transfer correction live)
    y_l1 = cm.bridge.concentrations_at(cm.space.to_natural(th), U0, Z,
                                       SPECIES)
    assert np.max(np.abs(y1 - y_l1)) > 1e-5


def test_candidate_information_uses_operator():
    """The baseline FIM candidate scoring must also flow through
    predict_at, so design and estimation stay consistent."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    space, th = _space_theta()
    at = AssumedTransfer(enabled=True, Q_sample_mL_min=0.6, V_fixed_mL=0.6)
    inf_t = TransportAwareInference(space, bridge, NoiseModel(),
                                    assumed_transfer=at)
    inf_0 = InferenceModel(space, bridge, NoiseModel())
    F_t = inf_t.candidate_information(U0, Z, SPECIES)
    F_0 = inf_0.candidate_information(U0, Z, SPECIES)
    assert not np.allclose(F_t, F_0)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} observation-operator tests passed.")
