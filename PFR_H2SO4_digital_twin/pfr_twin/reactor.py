"""
Steady-state, isothermal, 1D plug flow reactor model.

Governing equations (constant-density liquid, no axial dispersion), with
u = Q_total/(eps*A_cross) the INTERSTITIAL velocity (= superficial
Q/A for an unpacked tube) and residence coordinate
tau(x) = x / u.  The organic balances are catalyst-independent:

    u dC_EGDA/dx = -r1
    u dC_EGMA/dx = +r1 - r2
    u dC_EG  /dx = +r2
    u dC_AcOH/dx = +r1 + r2       (AcOH = total acetate pool)

The small-species balances depend on the route:

    H2SO4 (hydrolysis):     u dC_H2O/dx = -r1 - r2,   u dC_OH/dx = 0
    NaOH (saponification):  u dC_H2O/dx = 0,          u dC_OH/dx = -r1 - r2

r1, r2 are NET rates (acid reversible model: bilinear and negative when a
step runs in the esterification direction; alkaline model: bilinear in
[OH-][ester] with OH- self-depleting).  The system is mildly nonlinear and
non-stiff; LSODA at tight tolerances integrates it essentially to machine
precision.  In the acid irreversible limit the equations are exactly linear
and are verified against the closed-form solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from scipy.integrate import solve_ivp

from .analytical import equilibrium_state, reaction_quotients
from .kinetics import KineticModel
from .mixer import InletState
from .parameters import SPECIES, ReactorGeometry, SolverSettings

# Stoichiometric matrices, rows = SPECIES order, columns = (r1, r2)
NU_ACID = np.array([
    [-1.0,  0.0],   # EGDA
    [+1.0, -1.0],   # EGMA
    [ 0.0, +1.0],   # EG
    [+1.0, +1.0],   # AcOH (free acid)
    [-1.0, -1.0],   # H2O  (nucleophile)
    [ 0.0,  0.0],   # OH-  (absent on the acid route)
])
NU_BASE = np.array([
    [-1.0,  0.0],   # EGDA
    [+1.0, -1.0],   # EGMA
    [ 0.0, +1.0],   # EG
    [+1.0, +1.0],   # AcOH (acetate ion / NaOAc)
    [ 0.0,  0.0],   # H2O  (no net consumption: OH- is the nucleophile)
    [-1.0, -1.0],   # OH-  (consumed 1:1 with acetate released)
])
NU = NU_ACID        # backward-compatible alias (acid-route stoichiometry)


def nu_matrix(catalyst: str) -> np.ndarray:
    """Stoichiometric matrix of the chosen catalyst system."""
    return NU_BASE if catalyst == "NaOH" else NU_ACID


@dataclass
class PFRResult:
    """Axial profiles plus the scalars needed to interpret them."""
    x_m: np.ndarray
    tau_s: np.ndarray
    conc: Dict[str, np.ndarray]      # mol/L, keys = SPECIES
    inlet: InletState
    geometry: ReactorGeometry
    T_K: float
    u_m_s: float
    kappa1: float                    # k1(T)*c_cat0, 1/s (inlet time scale)
    kappa2: float                    # k2(T)*c_cat0, 1/s
    K1: float = math.inf             # hydrolysis Keq of step 1 at T (inf = irreversible)
    K2: float = math.inf             # hydrolysis Keq of step 2 at T
    eq_conc: Optional[Dict[str, float]] = None   # t->inf equilibrium composition
    catalyst: str = "H2SO4"

    # ---- derived metrics ----------------------------------------------------
    @property
    def conversion(self) -> np.ndarray:
        """Fractional EGDA conversion X(x)."""
        c0 = self.inlet.conc["EGDA"]
        return 1.0 - self.conc["EGDA"] / c0 if c0 > 0 else np.zeros_like(self.x_m)

    def yield_of(self, species: str) -> np.ndarray:
        """Yield of EGMA or EG on a diol-backbone basis: (C_i - C_i0)/C_EGDA0."""
        c0 = self.inlet.conc["EGDA"]
        if c0 <= 0:
            return np.zeros_like(self.x_m)
        return (self.conc[species] - self.inlet.conc[species]) / c0

    @property
    def selectivity_egma(self) -> float:
        """Outlet selectivity of EGMA among converted EGDA."""
        x_out = self.conversion[-1]
        return float(self.yield_of("EGMA")[-1] / x_out) if x_out > 1e-12 else float("nan")

    @property
    def residence_time_s(self) -> float:
        return float(self.tau_s[-1])

    # ---- reporting -----------------------------------------------------------
    @property
    def reversible(self) -> bool:
        return math.isfinite(self.K1)

    def outlet_conc(self) -> Dict[str, float]:
        return {sp: float(self.conc[sp][-1]) for sp in SPECIES}

    def summary_lines(self) -> List[str]:
        w0, w1 = self.inlet.conc["H2O"], self.conc["H2O"][-1]
        alkaline = self.catalyst == "NaOH"
        cat_sym = "[OH-]0" if alkaline else "[H+]"
        lines = [
            f"Catalyst system             : {self.catalyst} "
            + ("(saponification: OH- consumed stoichiometrically)" if alkaline
               else "(specific acid catalysis: [H+] constant)"),
            f"Temperature                 : {self.T_K - 273.15:7.2f} C ({self.T_K:.2f} K)",
            f"Interstitial velocity u     : {self.u_m_s * 1e3:7.3f} mm/s"
            + ("" if self.geometry.void_fraction >= 1.0
               else f"  (superficial {self.u_m_s * self.geometry.void_fraction * 1e3:.3f} mm/s)"),
            f"Residence time tau          : {self.residence_time_s:7.1f} s "
            f"({self.residence_time_s / 60.0:.2f} min)",
            f"kappa1 = k1{cat_sym:7s}       : {self.kappa1:.4e} 1/s"
            + ("  (inlet value; falls as OH- depletes)" if alkaline else ""),
            f"kappa2 = k2{cat_sym:7s}       : {self.kappa2:.4e} 1/s",
        ]
        if self.reversible:
            lines += [
                f"K1(T) hydrolysis Keq        : {self.K1:.4f} (-)",
                f"K2(T) hydrolysis Keq        : {self.K2:.4f} (-)",
            ]
        lines += ["", "Outlet composition (mol/L):"]
        for sp in SPECIES:
            if sp == "OH" and not alkaline:
                continue
            lines.append(f"  {sp:5s} in {self.inlet.conc[sp]:8.4f}  ->  out {self.conc[sp][-1]:8.4f}")
        lines += [
            "",
            f"EGDA conversion X           : {self.conversion[-1] * 100:6.2f} %",
            f"EGMA yield  Y_EGMA          : {self.yield_of('EGMA')[-1] * 100:6.2f} %",
            f"EG   yield  Y_EG            : {self.yield_of('EG')[-1] * 100:6.2f} %",
            f"EGMA selectivity  Y/X       : {self.selectivity_egma * 100:6.2f} %",
        ]
        if alkaline:
            oh0, oh1 = self.inlet.conc["OH"], self.conc["OH"][-1]
            used = (oh0 - oh1) / oh0 * 100.0 if oh0 > 0 else float("nan")
            cap = oh0 / max(2.0 * self.inlet.conc["EGDA"]
                            + self.inlet.conc["EGMA"], 1e-30)
            lines += [
                f"OH- consumed                : {used:6.2f} % of feed "
                f"({oh0:.4f} -> {oh1:.4f} M)",
                f"NaOH / acetate-group ratio  : {cap:6.3f} "
                + ("(sub-stoichiometric: OH- is the limiting reagent)"
                   if cap < 1.0 else "(stoichiometric excess)"),
                f"Water change                : {(w0 - w1) / w0 * 100:6.3f} %  "
                "(no net water consumption in saponification)",
            ]
        elif self.reversible:
            q1, q2 = reaction_quotients(self.outlet_conc())
            lines.append(
                f"Approach to equilibrium     : Q1/K1 = {q1 / self.K1:6.3f}, "
                f"Q2/K2 = {q2 / self.K2:6.3f}   (1.000 = equilibrated)")
            if self.eq_conc is not None:
                c0 = self.inlet.conc["EGDA"]
                if c0 > 0:
                    x_eq = 1.0 - self.eq_conc["EGDA"] / c0
                    y1_eq = (self.eq_conc["EGMA"] - self.inlet.conc["EGMA"]) / c0
                    y2_eq = (self.eq_conc["EG"] - self.inlet.conc["EG"]) / c0
                    lines.append(
                        f"Equilibrium limit (t->inf)  : X_eq = {x_eq * 100:6.2f} %, "
                        f"Y_EGMA_eq = {y1_eq * 100:6.2f} %, "
                        f"Y_EG_eq = {y2_eq * 100:6.2f} %")
            lines.append(
                f"Water depletion             : {(w0 - w1) / w0 * 100:6.3f} %  "
                "(water is an explicit reactant in the reversible rate law)")
        else:
            lines.append(
                f"Water depletion             : {(w0 - w1) / w0 * 100:6.3f} %  "
                f"(pseudo-order assumption {'OK' if (w0 - w1) / w0 < 0.05 else 'QUESTIONABLE'})")
        return lines

    def write_csv(self, path: str) -> None:
        header = ("x_m,tau_s," + ",".join(f"C_{sp}_mol_L" for sp in SPECIES)
                  + ",X_EGDA,Y_EGMA,Y_EG")
        table = np.column_stack(
            [self.x_m, self.tau_s]
            + [self.conc[sp] for sp in SPECIES]
            + [self.conversion, self.yield_of("EGMA"), self.yield_of("EG")]
        )
        np.savetxt(path, table, delimiter=",", header=header, comments="",
                   fmt="%.8e")


def simulate_pfr(inlet: InletState,
                 geometry: ReactorGeometry,
                 T_K: float,
                 model: KineticModel,
                 settings: SolverSettings = SolverSettings()) -> PFRResult:
    """Integrate the plug-flow balances from x = 0 to x = L.

    u is the INTERSTITIAL velocity Q / (epsilon A); for an unpacked tube
    (epsilon = 1, the default) it coincides with the superficial velocity
    Q/A and the result is unchanged.  Q/(eps A) must NOT be called
    'superficial velocity' when packing is enabled."""
    u = inlet.Q_total_m3_s / geometry.flow_area_m2     # m/s
    kappa1, kappa2 = model.effective_constants(T_K, inlet.c_cat0)
    nu = nu_matrix(model.params.catalyst)

    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        r1, r2 = model.rates(y, T_K, inlet.c_h_plus)
        return nu @ np.array([r1, r2]) / u

    y0 = np.array([inlet.conc[sp] for sp in SPECIES])
    x_eval = np.linspace(0.0, geometry.length_m, settings.n_points)

    sol = solve_ivp(rhs, (0.0, geometry.length_m), y0,
                    method=settings.method, t_eval=x_eval,
                    rtol=settings.rtol, atol=settings.atol)
    if not sol.success:
        raise RuntimeError(f"PFR integration failed: {sol.message}")

    conc = {sp: sol.y[i] for i, sp in enumerate(SPECIES)}
    if model.params.reversible:
        K1, K2 = model.K1(T_K), model.K2(T_K)
        eq_conc = equilibrium_state(inlet.conc, K1, K2)
    else:
        K1 = K2 = math.inf
        eq_conc = None
    return PFRResult(x_m=sol.t, tau_s=sol.t / u, conc=conc, inlet=inlet,
                     geometry=geometry, T_K=T_K, u_m_s=u,
                     kappa1=kappa1, kappa2=kappa2, K1=K1, K2=K2,
                     eq_conc=eq_conc, catalyst=model.params.catalyst)
