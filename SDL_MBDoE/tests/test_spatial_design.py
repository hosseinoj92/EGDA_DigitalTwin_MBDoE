"""Tests of optimal spatial sampling (sdl_advanced.spatial_design).
Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import (Layer1Bridge, OperatingConditions, ParameterSpace,
                 NoiseModel, literature_guess)
from sdl_advanced.spatial_design import (SensitivityField,
                                         SpatialDesignConfig,
                                         SpatialDesigner,
                                         fixed_equal_positions)

T_REF_K = 333.15
U0 = OperatingConditions(T_C=80.0, Q1_mL_min=1.0, Q2_mL_min=1.0,
                         C_EGDA_M=1.0, C_cat_M=1.0)
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")
NOISE = NoiseModel(sigma_abs_M=0.004, sigma_rel=0.02)


def _field_and_designer(length_m: float, cfg: SpatialDesignConfig):
    geom = {"length_m": length_m, "diameter_m": 0.018}
    bridge = Layer1Bridge(geom, T_REF_K)
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K))
    theta = space.to_vector(space.initial_guess)

    def predict(th, z):
        return bridge.concentrations_at(space.to_natural(th), U0, z, SPECIES)

    designer = SpatialDesigner(
        cfg, length_m,
        lambda y_pos: NOISE.covariance(y_pos, SPECIES, 1))
    field = SensitivityField(predict, theta, space.fd_steps,
                             designer.candidate_grid(), len(SPECIES))
    return field, designer, space


def test_fixed_equal_reproduces_legacy_layout():
    """Acceptance criterion 3: fixed_equal == L * arange(1..N)/N."""
    for L, n in ((0.06, 10), (0.5, 6), (1.2, 4)):
        legacy = L * np.arange(1, n + 1) / n
        assert np.allclose(fixed_equal_positions(L, n), legacy)


def test_reactor_length_rescales_designs():
    """Acceptance criterion 4: designs live in z/L fractions."""
    cfg = SpatialDesignConfig(mode="optimized", n_positions=4,
                              candidate_grid_size=41,
                              continuous_refinement=False)
    for L in (0.25, 1.0):
        field, designer, space = _field_and_designer(L, cfg)
        p = space.n_params
        zs = designer.positions(field, np.zeros((p, p)))
        assert np.all(zs >= cfg.z_min_fraction * L - 1e-12)
        assert np.all(zs <= cfg.z_max_fraction * L + 1e-12)
    assert np.allclose(fixed_equal_positions(1.0, 5) / 1.0,
                       fixed_equal_positions(0.25, 5) / 0.25)


def test_optimized_positions_bounds_spacing_deterministic():
    """Acceptance criterion 5: bounds, min spacing, no duplicates,
    deterministic."""
    cfg = SpatialDesignConfig(mode="optimized", n_positions=5,
                              candidate_grid_size=61,
                              min_spacing_fraction=0.05,
                              continuous_refinement=True)
    field, designer, space = _field_and_designer(0.5, cfg)
    p = space.n_params
    z1 = designer.positions(field, np.zeros((p, p)))
    z2 = designer.positions(field, np.zeros((p, p)))
    assert np.array_equal(z1, z2)                     # deterministic
    assert len(z1) == 5 and len(np.unique(z1)) == 5   # no duplicates
    assert np.all(np.diff(np.sort(z1)) >= 0.05 * 0.5 - 1e-9)
    lo, hi = designer.z_bounds
    assert np.all((z1 >= lo - 1e-12) & (z1 <= hi + 1e-12))


def test_optimized_differs_from_equal_and_is_more_informative():
    cfg = SpatialDesignConfig(mode="optimized", n_positions=5,
                              candidate_grid_size=81,
                              continuous_refinement=True)
    field, designer, space = _field_and_designer(0.5, cfg)
    p = space.n_params
    F0 = np.zeros((p, p))
    z_opt = designer.positions(field, F0)
    z_eq = fixed_equal_positions(0.5, 5)

    def logdet_of(zs):
        F = F0.copy()
        for z in zs:
            F = F + designer._fim_at(field, float(z))
        w = np.maximum(np.linalg.eigvalsh(F), 1e-12)
        return float(np.sum(np.log(w)))

    assert logdet_of(z_opt) >= logdet_of(z_eq) - 1e-9
    assert not np.allclose(np.sort(z_opt), z_eq)


def test_force_outlet_and_adaptive_gains_decrease():
    cfg = SpatialDesignConfig(mode="adaptive_sequential", n_positions=6,
                              candidate_grid_size=61, force_outlet=True,
                              continuous_refinement=False)
    field, designer, space = _field_and_designer(0.5, cfg)
    p = space.n_params
    zs = designer.positions(field, np.zeros((p, p)))
    assert np.isclose(np.max(zs), designer.z_bounds[1])
    # sequential mode from a well-posed prior state: marginal log-det gains
    # are non-increasing (submodularity of the D-criterion), so the
    # controller's stop-when-gain-small rule is sound
    F = np.eye(p) * 10.0
    chosen, gains = [], []
    for _ in range(4):
        z, g = designer.next_position(field, F, chosen)
        chosen.append(z)
        gains.append(g)
        F = F + designer._fim_at(field, z)
    assert all(g >= 0.0 for g in gains)
    assert gains[0] >= gains[-1] - 1e-9


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} spatial-design tests passed.")
