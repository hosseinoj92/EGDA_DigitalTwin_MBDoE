"""
Forward-model adapter around the Layer 1 PFR digital twin.

This is the ONLY Layer 2 module that imports from `pfr_twin`.  Everything
else talks to Layer 1 through the `Layer1Bridge` class, which

  * maps an estimation parameter vector (reference-temperature form) onto
    Layer 1 `KineticParameters`,
  * maps an `OperatingConditions` record onto Layer 1 feed streams and the
    micromixer, and
  * returns concentrations at requested axial sampling positions.

Estimation parameterization
---------------------------
Fitting (A, Ea) directly is badly conditioned (A and Ea are almost perfectly
correlated over a narrow T window).  Layer 2 therefore estimates, on the
H2SO4 route,

    theta = (k1_ref, Ea1, k2_ref, Ea2, K1_ref, K2_ref)

    k_i(T) = k_i_ref * exp[-(Ea_i/R)(1/T - 1/T_ref)]
    K_i(T) = K_i_ref * exp[-(dH_i/R)(1/T - 1/T_ref)]

with T_ref inside the experimental window.  The bridge converts this to the
equivalent Layer 1 pre-exponential  A_i = k_i_ref * exp(+Ea_i / (R T_ref))
and to EquilibriumStep records referenced at T_ref.  The van 't Hoff slopes
dH_i are FIXED at their small literature values (near-athermal equilibria:
dH is not identifiable from a 30-90 C window and would only inflate the CIs
of the K_refs).

On the NaOH route (irreversible saponification, no Keq exists) the vector is
just (k1_ref, Ea1, k2_ref, Ea2), and the "C_cat_M" operating variable is the
NaOH stream molarity - a stoichiometric design dimension, since OH- can be
made limiting.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, Sequence

import numpy as np
from scipy.integrate import solve_ivp

_LAYER1_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "PFR_H2SO4_digital_twin"))
if _LAYER1_DIR not in sys.path:
    sys.path.insert(0, _LAYER1_DIR)

from pfr_twin import (                                   # noqa: E402
    ArrheniusStep, EquilibriumStep, KineticParameters, KineticModel,
    ReactorGeometry, SolverSettings, Stream, mix_streams, simulate_pfr,
    analytical_profiles, default_kinetics,
)
from pfr_twin.parameters import R_GAS, SPECIES           # noqa: E402
from pfr_twin.reactor import nu_matrix                   # noqa: E402

# Fixed van 't Hoff slopes of the two hydrolysis equilibria (J/mol), taken
# from the Layer 1 literature defaults; not estimated (see module docstring).
_LIT = KineticParameters()
DH1_J, DH2_J = _LIT.eq1.dH_J, _LIT.eq2.dH_J

# Dilute-solution stream-density slopes, g/L per mol/L of catalyst
_DENSITY_SLOPE = {"H2SO4": 60.0, "NaOH": 41.0}


@dataclass(frozen=True)
class OperatingConditions:
    """One experiment's controllable inputs (the vector u of the theory)."""
    T_C: float                 # reactor temperature, deg C
    Q1_mL_min: float           # EGDA stream flow, mL/min
    Q2_mL_min: float           # catalyst stream flow, mL/min
    C_EGDA_M: float            # EGDA molarity of stream 1, mol/L
    C_cat_M: float             # catalyst (H2SO4 or NaOH) molarity of stream 2

    def label(self) -> str:
        return (f"T={self.T_C:.1f}C Q={self.Q1_mL_min + self.Q2_mL_min:.1f}mL/min "
                f"EGDA={self.C_EGDA_M:.3f}M cat={self.C_cat_M:.3f}M")


def literature_guess(t_ref_K: float, catalyst: str = "H2SO4") -> Dict[str, float]:
    """Initial estimates = Layer 1's literature-anchored kinetics for the
    chosen catalyst, expressed in reference-temperature form.  This is
    public knowledge, not the truth."""
    lit = default_kinetics(catalyst)
    guess = {
        "k1_ref": lit.step1.k(t_ref_K), "Ea1_J": lit.step1.Ea,
        "k2_ref": lit.step2.k(t_ref_K), "Ea2_J": lit.step2.Ea,
    }
    if catalyst == "H2SO4":
        guess["K1_ref"] = lit.eq1.K(t_ref_K)
        guess["K2_ref"] = lit.eq2.K(t_ref_K)
    return guess


class Layer1Bridge:
    """Configured gateway to the Layer 1 simulator."""

    def __init__(self, geometry: Dict[str, float], t_ref_K: float,
                 h_plus_model: str = "equilibrium",
                 engine: str = "ode", n_points: int = 101,
                 reversible: bool = True, catalyst: str = "H2SO4",
                 ka2_model: str = "tdep", activity_model: str = "dilute"):
        if engine not in ("ode", "analytical"):
            raise ValueError(f"Unknown forward engine '{engine}'.")
        if catalyst not in ("H2SO4", "NaOH"):
            raise ValueError(f"Unknown catalyst '{catalyst}'.")
        if catalyst == "NaOH":
            reversible = False          # saponification is irreversible
        if engine == "analytical" and (reversible or catalyst == "NaOH"):
            raise ValueError(
                "engine='analytical' is exact only for the acid route's "
                "irreversible limit; use engine='ode' otherwise (the NaOH "
                "route has a depleting reagent and no closed form).")
        self.geometry = ReactorGeometry(**geometry)
        self.t_ref_K = t_ref_K
        self.h_plus_model = h_plus_model
        self.engine = engine
        self.reversible = reversible
        self.catalyst = catalyst
        self.ka2_model = ka2_model
        self.activity_model = activity_model
        self.settings = SolverSettings(n_points=n_points, rtol=1e-8, atol=1e-11)

    # ------------------------------------------------------------------ #
    def kinetics_from_theta(self, theta_nat: Dict[str, float]) -> KineticParameters:
        a1 = theta_nat["k1_ref"] * np.exp(theta_nat["Ea1_J"] / (R_GAS * self.t_ref_K))
        a2 = theta_nat["k2_ref"] * np.exp(theta_nat["Ea2_J"] / (R_GAS * self.t_ref_K))
        step1 = ArrheniusStep(A=float(a1), Ea=float(theta_nat["Ea1_J"]))
        step2 = ArrheniusStep(A=float(a2), Ea=float(theta_nat["Ea2_J"]))
        if self.catalyst == "NaOH":
            return KineticParameters(step1=step1, step2=step2,
                                     catalyst="NaOH", reversible=False)
        return KineticParameters(
            step1=step1, step2=step2,
            eq1=EquilibriumStep(K_ref=float(theta_nat.get("K1_ref", _LIT.eq1.K_ref)),
                                dH_J=DH1_J, T_ref_K=self.t_ref_K),
            eq2=EquilibriumStep(K_ref=float(theta_nat.get("K2_ref", _LIT.eq2.K_ref)),
                                dH_J=DH2_J, T_ref_K=self.t_ref_K),
            reversible=self.reversible,
            h_plus_model=self.h_plus_model,
            ka2_model=self.ka2_model,
            activity_model=self.activity_model,
        )

    def _inlet(self, u: OperatingConditions, kin: KineticParameters):
        # stream densities: linear dilute-solution estimates consistent with
        # the Layer 1 defaults (1005 g/L at 1 M EGDA, 1060 g/L at 1 M H2SO4,
        # 1041 g/L at 1 M NaOH).  Speciation at the experiment temperature.
        s1 = Stream("aq EGDA", u.Q1_mL_min, {"EGDA": u.C_EGDA_M},
                    density_g_L=1000.0 + 5.0 * u.C_EGDA_M)
        s2 = Stream(f"aq {self.catalyst}", u.Q2_mL_min,
                    {self.catalyst: u.C_cat_M},
                    density_g_L=1000.0
                    + _DENSITY_SLOPE[self.catalyst] * u.C_cat_M)
        return mix_streams(s1, s2, kin, T_K=u.T_C + 273.15)

    # ------------------------------------------------------------------ #
    def concentrations_at(self, theta_nat: Dict[str, float],
                          u: OperatingConditions,
                          z_m: np.ndarray, species: Sequence[str],
                          extra_tau_s=0.0) -> np.ndarray:
        """Concentrations (mol/L) at axial positions z_m, flattened
        species-major:  y[i*Nz + k] = C_{species i}(z_k).

        extra_tau_s > 0 lets the sample keep reacting for that long after
        withdrawal (transfer-line effect).  It may be a SCALAR (same delay at
        every position - the legacy behaviour) or an ARRAY of len(z_m)
        (position-dependent transfer geometry, e.g. a capillary whose internal
        path lengthens toward the inlet)."""
        kin = self.kinetics_from_theta(theta_nat)
        model = KineticModel(kin)
        inlet = self._inlet(u, kin)
        T_K = u.T_C + 273.15
        # INTERSTITIAL velocity Q/(eps*A) (equals the superficial Q/A
        # only for an unpacked tube)
        u_vel = inlet.Q_total_m3_s / self.geometry.flow_area_m2
        kappa1, kappa2 = model.effective_constants(T_K, inlet.c_cat0)

        z_m = np.asarray(z_m, dtype=float)
        tau_extra = np.broadcast_to(np.asarray(extra_tau_s, dtype=float),
                                    z_m.shape).copy()
        if self.engine == "analytical":
            tau = z_m / u_vel + tau_extra
            prof = analytical_profiles(inlet, kappa1, kappa2, tau)
        else:
            res = simulate_pfr(inlet, self.geometry, T_K, model, self.settings)
            prof = {sp: np.interp(z_m, res.x_m, res.conc[sp]) for sp in res.conc}
            if np.any(tau_extra > 0.0):
                prof = self._advance_batch(prof, model, T_K, inlet.c_h_plus,
                                           tau_extra)
        return np.concatenate([np.atleast_1d(prof[sp]) for sp in species])

    def _advance_batch(self, port_conc: Dict[str, np.ndarray],
                       model: KineticModel, T_K: float, c_h_plus: float,
                       dt_s) -> Dict[str, np.ndarray]:
        """Advance each position's composition by dt_s of batch reaction (the
        batch time evolution of this network equals its PFR tau evolution).
        dt_s: scalar, or array with one entry per position.  Integrates the
        full (reversible) batch ODEs per position."""
        n = len(np.atleast_1d(port_conc[SPECIES[0]]))
        dt = np.broadcast_to(np.asarray(dt_s, dtype=float), (n,))
        out = {sp: np.empty(n) for sp in SPECIES}
        nu = nu_matrix(model.params.catalyst)

        def rhs(t: float, y: np.ndarray) -> np.ndarray:
            r1, r2 = model.rates(y, T_K, c_h_plus)
            return nu @ np.array([r1, r2])

        for k in range(n):
            y0 = np.array([float(np.atleast_1d(port_conc[sp])[k])
                           for sp in SPECIES])
            if dt[k] <= 0.0:
                for i, sp in enumerate(SPECIES):
                    out[sp][k] = y0[i]
                continue
            sol = solve_ivp(rhs, (0.0, float(dt[k])), y0,
                            method=self.settings.method,
                            rtol=self.settings.rtol, atol=self.settings.atol)
            if not sol.success:
                raise RuntimeError(f"Batch advance failed: {sol.message}")
            for i, sp in enumerate(SPECIES):
                out[sp][k] = sol.y[i, -1]
        return out

    # ------------------------------------------------------------------ #
    def full_profiles(self, theta_nat: Dict[str, float], u: OperatingConditions):
        """Complete PFRResult (used for validation plots only)."""
        kin = self.kinetics_from_theta(theta_nat)
        inlet = self._inlet(u, kin)
        return simulate_pfr(inlet, self.geometry, u.T_C + 273.15,
                            KineticModel(kin), self.settings)
