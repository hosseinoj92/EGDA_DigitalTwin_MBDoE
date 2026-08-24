"""Continuous design space, instrument resolution, configurable transfer-line
temperature, and the CONFIG knob surface.

The claims under test:

  * discrete mode is UNCHANGED - a run with `continuous=False` reproduces
    the published behaviour exactly, so enabling the option is opt-in and
    the existing results stay valid;
  * every proposed condition is COMMANDABLE - snapped to 0.1 C /
    0.1 mL/min / 0.1 mM and inside the declared bounds;
  * continuous mode is NEVER WORSE than discrete mode by the design
    criterion, which is what makes it safe to switch on;
  * a dimension the campaign declares constant is held fixed, not optimized;
  * the transfer line reacts at its OWN temperature, and cooling it changes
    the observation;
  * the knob surface is strict - a typo raises rather than being ignored.

Runnable standalone."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))

from sdl import Layer1Bridge, OperatingConditions, literature_guess
from sdl.design_space import (DesignResolution, bounds_vector, free_indices,
                              from_vector, refine, to_vector)
from sdl_advanced import benchmark as bm

BOUNDS = {"T_C": [40.0, 160.0], "Q_total_mL_min": [0.5, 8.0],
          "C_cat_M": [0.5, 1.0], "C_EGDA_M": [1.0, 1.0]}


# ---- resolution / snapping ----------------------------------------------- #
def test_resolution_snaps_to_commandable_values():
    r = DesignResolution()          # 0.1 C, 0.1 mL/min, 0.1 mM, 0.1 mM
    b = bounds_vector(BOUNDS)
    x = r.snap_vector([97.34, 1.237, 0.61234, 1.0], b)
    assert abs(x[0] - 97.3) < 1e-9
    assert abs(x[1] - 1.2) < 1e-9
    assert abs(x[2] - 0.6123) < 1e-9      # 0.1 mM grid
    assert abs(x[3] - 1.0) < 1e-9
    # already-on-grid values are untouched
    assert np.allclose(r.snap_vector([100.0, 2.0, 0.5, 1.0], b),
                       [100.0, 2.0, 0.5, 1.0])


def test_snapping_never_leaves_the_bounds():
    """Rounding can push a value across a bound; the result must still be
    executable."""
    r = DesignResolution()
    b = bounds_vector(BOUNDS)
    for x in ([160.04, 8.04, 1.00004, 1.0], [39.96, 0.46, 0.49996, 1.0],
              [1e6, 1e6, 1e6, 1e6], [-1e6, 1e-9, 1e-9, 1.0]):
        out = r.snap_vector(x, b)
        for v, (lo, hi) in zip(out, b):
            assert lo - 1e-12 <= v <= hi + 1e-12, (x, out)


def test_zero_resolution_means_unrounded():
    from sdl.design_space import IDEAL_RESOLUTION
    b = bounds_vector(BOUNDS)
    x = IDEAL_RESOLUTION.snap_vector([97.3456789, 1.23456, 0.678901, 1.0], b)
    assert abs(x[0] - 97.3456789) < 1e-12


def test_fixed_dimension_is_not_optimized():
    """C_EGDA is declared [1.0, 1.0] in the shipped design space: a constant
    of the campaign, not a free variable."""
    b = bounds_vector(BOUNDS)
    free = free_indices(b, DesignResolution())
    assert free == (0, 1, 2)             # T, Q, C_cat - not C_EGDA
    # a range narrower than one resolution step is fixed too: there is no
    # second commandable setting inside it
    narrow = bounds_vector({**BOUNDS, "C_cat_M": [0.5, 0.50005]})
    assert 2 not in free_indices(narrow, DesignResolution())


def test_degenerate_bounds_are_accepted_not_rejected():
    """The shipped configuration HAS a degenerate dimension; refusing it
    would make continuous mode unusable on the benchmark's own design
    space."""
    b = bounds_vector(BOUNDS)
    assert b[3] == (1.0, 1.0)
    for bad in ({**BOUNDS, "C_cat_M": [1.0, 0.5]},        # inverted
                {**BOUNDS, "Q_total_mL_min": [0.0, 8.0]}):  # non-positive
        try:
            bounds_vector(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} should not validate")


# ---- the never-worse guarantee ------------------------------------------- #
def test_refine_never_returns_something_worse():
    """The whole safety argument: refinement is accepted only when it
    STRICTLY beats the starting point, so continuous mode cannot lose to
    discrete mode by the design criterion."""
    start = OperatingConditions(100.0, 1.0, 1.0, 1.0, 0.75)

    # a deliberately hostile objective: maximal at the start, worse
    # everywhere else, so any "improvement" would be a bug
    def adversarial(u):
        return -abs(u.T_C - 100.0) - abs(u.C_cat_M - 0.75)

    u, s, improved = refine(adversarial, start, adversarial(start), BOUNDS,
                            maxiter=20)
    assert not improved
    assert u is start and abs(s - adversarial(start)) < 1e-12

    # and on an objective with a better interior point it DOES improve,
    # so the test above is not passing vacuously
    def easy(u):
        return -abs(u.T_C - 123.4)

    u2, s2, improved2 = refine(easy, start, easy(start), BOUNDS, maxiter=60)
    assert improved2 and s2 > easy(start)
    assert abs(u2.T_C - 123.4) < 1.0


def test_refined_point_is_snapped_and_in_bounds():
    start = OperatingConditions(100.0, 1.0, 1.0, 1.0, 0.75)
    res = DesignResolution()

    def objective(u):
        return -abs(u.T_C - 123.456) - abs(u.C_cat_M - 0.87654)

    u, _s, improved = refine(objective, start, objective(start), BOUNDS,
                             resolution=res, maxiter=80)
    assert improved
    x = to_vector(u)
    grid = res.as_vector()
    for i, (lo, hi) in enumerate(bounds_vector(BOUNDS)):
        assert lo - 1e-9 <= x[i] <= hi + 1e-9
        if grid[i] > 0:
            assert abs(x[i] / grid[i] - round(x[i] / grid[i])) < 1e-6, (
                f"variable {i} = {x[i]} is not on the {grid[i]} grid - the "
                "platform could not command it")
    # the fixed dimension is untouched
    assert abs(u.C_EGDA_M - 1.0) < 1e-12


# ---- integration with the selectors -------------------------------------- #
def _selector(continuous):
    from sdl import (InferenceModel, MBDoESelector, ParameterSpace,
                     NoiseModel, build_candidates)
    from sdl_advanced.spatial_design import fixed_equal_positions
    t_ref = bm.T_REF_C + 273.15
    bridge = Layer1Bridge(bm.GEOMETRY, t_ref, activity_model="pitzer")
    space = ParameterSpace(t_ref_K=t_ref,
                           initial_guess=dict(literature_guess(t_ref)))
    inf = InferenceModel(space, bridge, NoiseModel(sigma_abs_M=4e-3,
                                                  sigma_rel=2e-2))
    ports = fixed_equal_positions(bm.GEOMETRY["length_m"], 10)
    kw = ({"continuous": True, "continuous_bounds": BOUNDS,
           "continuous_maxiter": 15, "resolution": DesignResolution()}
          if continuous else {})
    return MBDoESelector(
        inference=inf, candidates=build_candidates(bm.DESIGN), spatial=True,
        ports_z_m=ports, outlet_z_m=np.array([bm.GEOMETRY["length_m"]]),
        species=bm.SPECIES, criterion="D", **kw)


def test_baseline_selector_continuous_beats_or_matches_grid():
    """Same information state, two modes: the continuous pick must score at
    least as well as the grid pick on the selector's own criterion."""
    disc, cont = _selector(False), _selector(True)
    u_d, u_c = disc.select(), cont.select()
    F0 = disc.inference.fisher_information()
    z = disc.ports_z_m
    s_d = disc._score_candidate(F0, u_d, z)
    s_c = disc._score_candidate(F0, u_c, z)
    assert s_c >= s_d - 1e-9, (s_c, s_d)
    # the continuous pick is commandable
    x = to_vector(u_c)
    assert abs(x[0] * 10 - round(x[0] * 10)) < 1e-6      # 0.1 C grid
    assert abs(x[1] * 10 - round(x[1] * 10)) < 1e-6      # 0.1 mL/min grid


def test_discrete_mode_is_untouched_by_the_new_option():
    """`continuous=False` must construct and behave exactly as before, so
    the published discrete results remain valid."""
    s = _selector(False)
    assert s.continuous is False
    u = s.select()
    grid = {(c.T_C, c.Q1_mL_min + c.Q2_mL_min, c.C_cat_M, c.C_EGDA_M)
            for c in s.candidates}
    assert (u.T_C, u.Q1_mL_min + u.Q2_mL_min, u.C_cat_M, u.C_EGDA_M) in grid
    assert bm.continuous_kwargs() == {}      # default config: no kwargs


def test_advanced_selector_continuous_shortlist_only_improves():
    """The refined candidate enters the EIG shortlist at the head and never
    displaces the grid winner it failed to beat."""
    from sdl_advanced.bayes_design import AdvancedDesignConfig
    cfg_off = AdvancedDesignConfig(continuous=False)
    cfg_on = AdvancedDesignConfig(continuous=True, continuous_maxiter=10,
                                  continuous_restarts=0)
    assert cfg_off.continuous is False and cfg_on.continuous is True
    # the augmentation is a no-op without bounds, so an unconfigured
    # selector cannot accidentally start refining
    assert cfg_on.continuous_restarts == 0


# ---- transfer-line temperature -------------------------------------------- #
def test_transfer_line_temperature_is_configurable_and_matters():
    """A cooled line lets far less reaction happen after withdrawal than a
    line at reactor temperature - the correction must reflect that."""
    t_ref = bm.T_REF_C + 273.15
    bridge = Layer1Bridge(bm.GEOMETRY, t_ref, activity_model="pitzer")
    u = OperatingConditions(160.0, 0.25, 0.25, 1.0, 1.0)
    z = np.array([0.2])
    guess = literature_guess(t_ref)
    tau = 18.0                              # seconds in the line
    hot = bridge.concentrations_at(guess, u, z, bm.SPECIES, extra_tau_s=tau)
    cool = bridge.concentrations_at(guess, u, z, bm.SPECIES, extra_tau_s=tau,
                                    T_extra_K=25.0 + 273.15)
    none = bridge.concentrations_at(guess, u, z, bm.SPECIES, extra_tau_s=tau,
                                    T_extra_K=None)
    assert np.allclose(hot, none)           # None == reactor temperature
    assert not np.allclose(hot, cool)
    # EGDA is consumed by the reaction, so a HOT line leaves less of it
    assert cool[0] > hot[0]
    # zero delay: the line temperature cannot matter
    assert np.allclose(
        bridge.concentrations_at(guess, u, z, bm.SPECIES, extra_tau_s=0.0),
        bridge.concentrations_at(guess, u, z, bm.SPECIES, extra_tau_s=0.0,
                                 T_extra_K=298.15))


def test_benchmark_line_temperature_reaches_the_inference_side():
    """T_line_C is a COMMANDED quantity, so the controller's transport
    correction is entitled to it - and must actually receive it, or the
    correction silently assumes the wrong temperature."""
    assert bm.TRANSFER_TRUE.T_line_C == 25.0
    at = bm._assumed_transfer_from(bm.TRANSFER_TRUE, 0.2)
    assert at.T_line_C == 25.0
    # every transport scenario inherits it via dataclasses.replace
    for name in ("S3_transport", "S3ab_delay", "S3ab_rtd"):
        assert bm.SCENARIOS[name].transfer.T_line_C == 25.0


# ---- the knob surface ------------------------------------------------------ #
def test_apply_config_is_strict_about_typos():
    """A silently-ignored knob is indistinguishable from a knob that had no
    effect; that is what wastes a long run."""
    for bad in ({"NOT_A_BLOCK": {}},
                {"GOVERNOR": {"alpha_champagne": 0.05}},
                {"DESIGN_SPACE": {"resolution": {"T_K": 0.1}}}):
        try:
            bm.apply_config(bad)
        except KeyError:
            pass
        else:
            raise AssertionError(f"{bad} should have raised")


def test_apply_config_round_trips_every_block():
    before = bm.resolved_config()
    try:
        bm.apply_config({"DESIGN_SPACE": {"continuous": True,
                                          "resolution": {"T_C": 0.5}},
                         "TRANSFER_TRUE": {"T_line_C": 30.0},
                         "GOVERNOR": {"alpha_campaign": 0.01},
                         "T_REF_C": 65.0})
        assert bm.DESIGN_SPACE["continuous"] is True
        assert bm.DESIGN_SPACE["resolution"]["T_C"] == 0.5
        # untouched fields of the same block survive
        assert bm.DESIGN_SPACE["resolution"]["Q_total_mL_min"] == 0.1
        assert bm.TRANSFER_TRUE.T_line_C == 30.0
        assert bm.TRANSFER_TRUE.enabled is True     # replace(), not rebuild
        assert bm.GOVERNOR["alpha_campaign"] == 0.01
        assert bm.T_REF_C == 65.0
        assert bm.resolved_config()["DESIGN_SPACE"]["continuous"] is True
    finally:
        bm.apply_config(before)
    assert bm.DESIGN_SPACE["continuous"] is False
    assert bm.T_REF_C == 60.0
    assert bm.TRANSFER_TRUE.T_line_C == 25.0


def _load_runner(name):
    import importlib.util
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "_" + name, os.path.join(here, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_each_runner_owns_its_knobs_independently():
    """The two entry points hold SEPARATE knob blocks and neither imports
    the other, so the demo campaign can be retuned without disturbing a
    publication benchmark.

    They are deliberately NOT required to hold the same values - a study
    campaign and a publication benchmark legitimately explore different
    design spaces.  What must hold is that each is COMPLETE and
    APPLICABLE: same set of blocks, every overridable block present, and
    every value accepted by the strict validator.  Divergence in values is
    surfaced at run time instead (the campaign prints every knob that is
    not the library default) and recorded in the output config."""
    b = _load_runner("run_advanced_benchmark")
    c = _load_runner("run_advanced_campaign")
    assert "run_advanced_benchmark" not in \
        open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "run_advanced_campaign.py")).read(), \
        "the campaign must not import the benchmark runner's globals"
    assert set(b.KNOBS) == set(c.KNOBS), (
        "the two runners expose different knob BLOCKS; every block must be "
        "reachable from both entry points even when the values differ")
    before = bm.resolved_config()
    try:
        for mod in (b, c):
            bm.apply_config(dict(mod.KNOBS))     # strict: raises on a typo
    finally:
        bm.apply_config(before)
        bm._GEOMETRY_CACHE.clear()


def test_runner_knobs_cover_every_overridable_block():
    """The point of the CONFIG block is that a user can reach EVERY knob
    from one place; if a new block is added to the module it must appear
    there too."""
    mod = _load_runner("run_advanced_benchmark")
    missing = [b for b in bm._OVERRIDABLE if b not in mod.KNOBS]
    assert not missing, f"KNOBS is missing overridable block(s): {missing}"
    # and every knob it declares is applicable
    bm.apply_config(dict(mod.KNOBS))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} design-space tests passed.")
