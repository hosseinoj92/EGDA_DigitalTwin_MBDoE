"""
Layer 2 self-tests.  Pytest-compatible (plain test_* functions with asserts),
but also runnable standalone from the IDE or shell:

    python tests/self_test.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdl import (
    Layer1Bridge, OperatingConditions, ParameterSpace, NoiseModel,
    VirtualLaboratory, InferenceModel, MBDoESelector,
    build_candidates, build_fixed_design, literature_guess, run_strategy,
)

T_REF_K = 333.15
GEOM = {"length_m": 0.5, "diameter_m": 0.018}
SPECIES = ("EGDA", "EGMA", "EG", "AcOH")
TRUTH = {"k1_ref": 3.3e-3, "Ea1_J": 58_500.0,
         "k2_ref": 8.5e-4, "Ea2_J": 52_000.0,
         "K1_ref": 0.80, "K2_ref": 0.12}
TRUTH_NAOH = {"k1_ref": 2.20, "Ea1_J": 44_000.0,
              "k2_ref": 0.60, "Ea2_J": 50_000.0}
U0 = OperatingConditions(T_C=70.0, Q1_mL_min=5.0, Q2_mL_min=5.0,
                         C_EGDA_M=1.0, C_cat_M=1.0)
DESIGN = {"T_C_levels": [40, 60, 80, 90], "Q_total_mL_min_levels": [4.0, 10.0],
          "C_cat_M_levels": [0.3, 1.0],
          "C_EGDA_M_levels": [0.75, 1.0], "C_EGDA_M": 1.0,
          "fixed_design_T_C": [40, 60, 80, 90],
          "nominal_Q_total_mL_min": 10.0, "nominal_C_cat_M": 1.0}


def _ports(bridge, n=6):
    L = bridge.geometry.length_m
    return L * np.arange(1, n + 1) / n


def _make_loop(noise_kw, seed=1, engine="ode"):
    bridge = Layer1Bridge(GEOM, T_REF_K, engine=engine)
    ports = _ports(bridge)
    lab = VirtualLaboratory(TRUTH, bridge, NoiseModel(**noise_kw),
                            ports, SPECIES, seed=seed)
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K))
    inference = InferenceModel(space, bridge, NoiseModel(**noise_kw))
    selector = MBDoESelector(inference=inference,
                             candidates=build_candidates(DESIGN),
                             spatial=True, ports_z_m=ports,
                             outlet_z_m=np.array([GEOM["length_m"]]),
                             species=SPECIES)
    return bridge, ports, lab, inference, selector


def test_bridge_engines_agree():
    """ODE and analytical forward engines must match in the irreversible
    limit (there Layer 1 is exactly linear with a closed form)."""
    z = np.array([0.1, 0.3, 0.5])
    y = {}
    for engine in ("ode", "analytical"):
        b = Layer1Bridge(GEOM, T_REF_K, engine=engine, reversible=False)
        y[engine] = b.concentrations_at(TRUTH, U0, z, SPECIES)
    assert np.max(np.abs(y["ode"] - y["analytical"])) < 1e-6


def test_thermodynamic_consistency():
    """Net rates must vanish exactly at the coupled-equilibrium composition
    (microscopic reversibility built into the rate law)."""
    from pfr_twin import KineticModel
    from pfr_twin.analytical import equilibrium_state
    from pfr_twin.parameters import SPECIES as ALL_SPECIES

    bridge = Layer1Bridge(GEOM, T_REF_K)
    kin = bridge.kinetics_from_theta(TRUTH)
    model = KineticModel(kin)
    T_K = U0.T_C + 273.15
    inlet = bridge._inlet(U0, kin)
    eq = equilibrium_state(inlet.conc, model.K1(T_K), model.K2(T_K))
    r_eq = model.rates([eq[sp] for sp in ALL_SPECIES], T_K, inlet.c_h_plus)
    r_in = model.rates([inlet.conc[sp] for sp in ALL_SPECIES], T_K,
                       inlet.c_h_plus)
    scale = max(abs(r_in[0]), abs(r_in[1]))
    assert max(abs(r_eq[0]), abs(r_eq[1])) < 1e-10 * scale


def test_reversible_long_residence_reaches_equilibrium():
    """At long residence time the reversible PFR must (i) conserve the three
    linear invariants and (ii) approach the algebraic equilibrium state."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    u_slow = OperatingConditions(T_C=90.0, Q1_mL_min=0.25, Q2_mL_min=0.25,
                                 C_EGDA_M=1.0, C_cat_M=1.0)
    res = bridge.full_profiles(TRUTH, u_slow)
    backbone = res.conc["EGDA"] + res.conc["EGMA"] + res.conc["EG"]
    acetate = 2.0 * res.conc["EGDA"] + res.conc["EGMA"] + res.conc["AcOH"]
    water_ac = res.conc["H2O"] + res.conc["AcOH"]
    c_ref = res.inlet.conc["EGDA"]
    for inv in (backbone, acetate, water_ac):
        assert np.ptp(inv) / c_ref < 1e-7
    assert res.eq_conc is not None
    for sp in SPECIES:
        assert abs(res.conc[sp][-1] - res.eq_conc[sp]) < 2e-3, sp
    # reversibility must actually bind: equilibrium leaves residual EGMA
    assert res.eq_conc["EGMA"] > 0.01
    assert res.eq_conc["EGDA"] > 0.0


def test_naoh_much_faster_than_acid():
    """Per mole of catalyst, saponification must be orders of magnitude
    faster.  Compare (i) the second-order rate constants themselves and
    (ii) conversion at a SHORT residence time, where neither the acid route
    (slow) nor the base route (OH- exhaustion) is endpoint-limited."""
    from pfr_twin import KineticModel
    b_acid = Layer1Bridge(GEOM, T_REF_K)
    b_base = Layer1Bridge(GEOM, T_REF_K, catalyst="NaOH")
    T_K = 313.15
    k1_acid = KineticModel(b_acid.kinetics_from_theta(TRUTH)).k1(T_K)
    k1_base = KineticModel(b_base.kinetics_from_theta(TRUTH_NAOH)).k1(T_K)
    assert k1_base / k1_acid > 100.0, (k1_acid, k1_base)

    u = OperatingConditions(T_C=40.0, Q1_mL_min=38.0, Q2_mL_min=38.0,
                            C_EGDA_M=1.0, C_cat_M=1.0)   # tau ~ 100 s
    x_acid = Layer1Bridge(GEOM, T_REF_K).full_profiles(TRUTH, u).conversion[-1]
    x_base = b_base.full_profiles(TRUTH_NAOH, u).conversion[-1]
    assert x_acid < 0.10, x_acid
    assert x_base > 0.60, x_base


def test_naoh_limiting_reagent_and_invariants():
    """Sub-stoichiometric NaOH: acetate released must equal the OH- consumed,
    the reaction must self-quench (residual esters), and the saponification
    invariants must hold to solver precision."""
    u = OperatingConditions(T_C=50.0, Q1_mL_min=5.0, Q2_mL_min=5.0,
                            C_EGDA_M=1.0, C_cat_M=1.0)   # OH/acetate = 0.5
    res = Layer1Bridge(GEOM, T_REF_K, catalyst="NaOH").full_profiles(
        TRUTH_NAOH, u)
    c0 = res.inlet.conc
    backbone = res.conc["EGDA"] + res.conc["EGMA"] + res.conc["EG"]
    acetate = 2.0 * res.conc["EGDA"] + res.conc["EGMA"] + res.conc["AcOH"]
    oh_acetate = res.conc["OH"] + res.conc["AcOH"]
    for inv in (backbone, acetate, oh_acetate, res.conc["H2O"]):
        assert np.ptp(inv) / c0["EGDA"] < 1e-7
    # OH- exhausted, acetate release capped at the OH- feed
    assert res.conc["OH"][-1] < 1e-6
    assert abs(res.conc["AcOH"][-1] - c0["OH"]) < 1e-6
    # self-quench leaves unconverted ester behind
    assert res.conc["EGDA"][-1] + res.conc["EGMA"][-1] > 0.05
    # and no equilibrium metrics exist on this route
    assert res.eq_conc is None and not res.reversible


def test_bisulfate_speciation_temperature_and_activity():
    """Bisulfate speciation: (i) Ka2(T) anchored at 25 C and collapsing with
    temperature (Hovey & Hepler thermochemistry), (ii) the Pitzer route
    reproduces the known non-ideality at 1 mol/kg, (iii) it reduces to the
    dilute limit at low concentration."""
    import math
    from pfr_twin.parameters import KA2_HSO4, default_kinetics
    from pfr_twin.speciation import (bisulfate_pitzer, h_plus_concentration,
                                     ka2_clarke_glew, ka2_prs)

    # anchored at 25 C, ~2 orders of magnitude down by 150 C
    assert abs(ka2_clarke_glew(298.15, KA2_HSO4) / KA2_HSO4 - 1.0) < 1e-12
    for t_c, pk in ((100.0, 3.07), (150.0, 3.85), (250.0, 5.41)):
        assert abs(-math.log10(ka2_clarke_glew(t_c + 273.15, KA2_HSO4)) - pk) < 0.15
    assert abs(ka2_prs(298.15) - 0.0105) < 2e-4

    # PRS Pitzer at 1 mol/kg, 25 C: sulfate fraction in the Raman/EMF band
    sp = bisulfate_pitzer(1.0, 298.15)
    assert 0.05 < sp["m_SO4"] < 0.45
    assert sp["m_H"] > 1.05                     # >> dilute prediction (1.01)
    q = sp["m_H"] * sp["m_SO4"] / sp["m_HSO4"] * sp["gamma_ratio"]
    assert abs(q / sp["K2"] - 1.0) < 1e-9       # equilibrium exactly closed

    # dilute limit: both activity models agree at 1e-4 M
    kin_p = default_kinetics("H2SO4", activity_model="pitzer")
    kin_d = default_kinetics("H2SO4", ka2_model="constant")
    c_p, _ = h_plus_concentration(1e-4, 55.3, 298.15, kin_p)
    c_d, _ = h_plus_concentration(1e-4, 55.3, 298.15, kin_d)
    assert abs(c_p / c_d - 1.0) < 0.02

    # hot reactor: second dissociation switches off for dilute acid
    kin_t = default_kinetics("H2SO4")
    c25, _ = h_plus_concentration(0.01, 55.3, 298.15, kin_t)
    c150, _ = h_plus_concentration(0.01, 51.0, 423.15, kin_t)
    assert c25 / 0.01 > 1.3 and c150 / 0.01 < 1.1


def test_speciation_follows_experiment_temperature():
    """The bridge must speciate at each experiment's own temperature: with
    the default T-dependent Ka2, the same feed gives a (slightly) different
    [H+] at 30 C than at 90 C."""
    bridge = Layer1Bridge(GEOM, T_REF_K)
    kin = bridge.kinetics_from_theta(TRUTH)
    u30 = OperatingConditions(T_C=30.0, Q1_mL_min=5.0, Q2_mL_min=5.0,
                              C_EGDA_M=1.0, C_cat_M=0.3)
    u90 = OperatingConditions(T_C=90.0, Q1_mL_min=5.0, Q2_mL_min=5.0,
                              C_EGDA_M=1.0, C_cat_M=0.3)
    h30 = bridge._inlet(u30, kin).c_h_plus
    h90 = bridge._inlet(u90, kin).c_h_plus
    assert h30 > h90 > 0.0                      # Ka2 falls with temperature


def test_naoh_parameter_space_is_4d():
    from sdl import param_keys_for
    keys = param_keys_for("NaOH")
    assert keys == ("k1_ref", "Ea1_J", "k2_ref", "Ea2_J")
    space = ParameterSpace(t_ref_K=T_REF_K,
                           initial_guess=literature_guess(T_REF_K, "NaOH"),
                           param_keys=keys)
    vec = space.to_vector(space.initial_guess)
    assert vec.shape == (4,)
    nat = space.to_natural(vec)
    for k in keys:
        assert abs(nat[k] / space.initial_guess[k] - 1.0) < 1e-12
    lo, hi = space.bounds()
    assert lo.shape == hi.shape == (4,) and np.all(lo < hi)


def test_truth_firewall():
    """The closed loop must never read the hidden parameters."""
    _, _, lab, inference, selector = _make_loop(
        {"sigma_abs_M": 0.004, "sigma_rel": 0.02, "rho_overlap": 0.3})
    run_strategy("D", lab, inference, build_fixed_design(DESIGN), selector,
                 budget=3, verbose=False)
    assert lab.n_truth_reveals == 0
    assert lab.n_experiments_run == 3


def test_fim_positive_definite():
    _, _, lab, inference, selector = _make_loop(
        {"sigma_abs_M": 0.004, "sigma_rel": 0.02, "rho_overlap": 0.0}, seed=2)
    run_strategy("D", lab, inference, build_fixed_design(DESIGN), selector,
                 budget=2, verbose=False)
    F = inference.fisher_information()
    eig = np.linalg.eigvalsh(F)
    assert eig[0] > 0.0
    rep = inference.uncertainty()
    assert rep.well_posed
    assert np.isfinite(rep.d_criterion)


def test_low_noise_recovery():
    """With nearly noise-free spatial data + MBDoE, the hidden parameters
    (now including both equilibrium constants) must be recovered accurately
    despite the offset initial guess."""
    _, _, lab, inference, selector = _make_loop(
        {"sigma_abs_M": 1e-4, "sigma_rel": 0.002, "rho_overlap": 0.0}, seed=3)
    res = run_strategy("D", lab, inference, build_fixed_design(DESIGN),
                       selector, budget=4, verbose=False)
    nat = res.history[-1].theta_nat
    for k in TRUTH:
        rel = abs(nat[k] / TRUTH[k] - 1.0)
        assert rel < 0.05, f"{k}: rel error {rel:.3%}"


def test_measurement_shapes_and_noise():
    bridge = Layer1Bridge(GEOM, T_REF_K, engine="ode")
    ports = _ports(bridge)
    lab = VirtualLaboratory(TRUTH, bridge,
                            NoiseModel(sigma_abs_M=0.004, sigma_rel=0.02,
                                       rho_overlap=0.3),
                            ports, SPECIES, seed=5)
    m_sp = lab.run_experiment(U0, spatial=True)
    m_out = lab.run_experiment(U0, spatial=False)
    assert m_sp.size == len(SPECIES) * len(ports)
    assert m_out.size == len(SPECIES)
    # spatial outlet block must sit near the outlet-only values (same truth)
    outlet_from_spatial = m_sp.y[len(ports) - 1::len(ports)]
    assert np.max(np.abs(outlet_from_spatial - m_out.y)) < 0.05


def test_candidate_grid_varies_egda_concentration():
    candidates = build_candidates(DESIGN)
    egda = sorted({u.C_EGDA_M for u in candidates})
    expected = (len(DESIGN["T_C_levels"])
                * len(DESIGN["Q_total_mL_min_levels"])
                * len(DESIGN["C_cat_M_levels"])
                * len(DESIGN["C_EGDA_M_levels"]))
    assert len(candidates) == expected
    assert egda == DESIGN["C_EGDA_M_levels"]
    # Fixed campaigns retain the explicitly configured nominal EGDA feed.
    assert all(u.C_EGDA_M == DESIGN["C_EGDA_M"]
               for u in build_fixed_design(DESIGN))
    legacy = dict(DESIGN)
    legacy.pop("C_EGDA_M_levels")
    assert {u.C_EGDA_M for u in build_candidates(legacy)} == {1.0}


def test_continuous_design_refines_inside_bounds():
    """The hybrid selector must improve on its coarse seed without leaving
    the user-supplied admissible region."""
    target = np.array([57.3, 7.4, 0.64, 0.68])
    scales = np.array([30.0, 6.0, 0.7, 0.5])

    class SmoothInformationSurface:
        def fisher_information(self):
            return np.array([[1.0]])

        def candidate_information(self, u, z, species):
            x = np.array([u.T_C, u.Q1_mL_min + u.Q2_mL_min,
                          u.C_cat_M, u.C_EGDA_M])
            value = 100.0 - float(np.sum(((x - target) / scales) ** 2))
            return np.array([[max(value, 1e-6)]])

    cfg = {
        "T_C_levels": [40.0, 70.0],
        "Q_total_mL_min_levels": [4.0, 10.0],
        "C_cat_M_levels": [0.3, 1.0],
        "C_EGDA_M_levels": [0.5, 1.0],
        "C_EGDA_M": 1.0,
    }
    bounds = {
        "T_C": [30.0, 90.0],
        "Q_total_mL_min": [4.0, 20.0],
        "C_cat_M": [0.3, 1.0],
        "C_EGDA_M": [0.5, 1.0],
    }
    inference = SmoothInformationSurface()
    common = dict(
        inference=inference, candidates=build_candidates(cfg), spatial=False,
        ports_z_m=np.array([0.5]), outlet_z_m=np.array([0.5]),
        species=SPECIES)
    coarse = MBDoESelector(**common).select()
    refined = MBDoESelector(
        **common, continuous=True, continuous_bounds=bounds,
        continuous_maxiter=80).select()

    coarse_x = MBDoESelector._to_vector(coarse)
    refined_x = MBDoESelector._to_vector(refined)
    assert np.linalg.norm((refined_x - target) / scales) < np.linalg.norm(
        (coarse_x - target) / scales)
    for value, key in zip(refined_x, MBDoESelector._VARIABLES):
        assert bounds[key][0] <= value <= bounds[key][1]

    bad_bounds = dict(bounds)
    bad_bounds["T_C"] = [50.0, 90.0]  # excludes the 40 C coarse candidates
    try:
        MBDoESelector(**common, continuous_bounds=bad_bounds)
    except ValueError as exc:
        assert "continuous_bounds" in str(exc)
    else:
        raise AssertionError("Out-of-bounds coarse candidate was accepted.")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} self-tests passed.")
