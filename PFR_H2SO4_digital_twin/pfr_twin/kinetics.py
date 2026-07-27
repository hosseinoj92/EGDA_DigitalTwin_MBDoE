"""
Kinetic model of the two-step series ester cleavage, per catalyst system.

Acid route (catalyst = "H2SO4"), REVERSIBLE hydrolysis/esterification:

    step 1:  EGDA + H2O <-> EGMA + AcOH
    step 2:  EGMA + H2O <-> EG   + AcOH

Acid catalysis (A-AC2 forward, Fischer esterification reverse) accelerates
both directions through the same protonation pre-equilibrium, so [H+]
multiplies the NET rate.  With C_w_ref = C_WATER_REF (55.34 M, the dilute
aqueous reference at which k1, k2 are calibrated):

    r1 = k1(T) [H+] ( [EGDA] [H2O] - [EGMA][AcOH] / K1(T) ) / C_w_ref
    r2 = k2(T) [H+] ( [EGMA] [H2O] - [EG]  [AcOH] / K2(T) ) / C_w_ref

K1, K2 are the dimensionless concentration-based hydrolysis equilibrium
constants (van 't Hoff in T).  The reverse rate constants are implied,

    k_i,rev(T) = k_i(T) / (K_i(T) C_w_ref)      [L^2 mol^-2 s^-1],

which enforces r_i = 0 exactly at Q_i = K_i: the model cannot violate
thermodynamics regardless of parameter values (microscopic reversibility).
[H+] is constant along the reactor (true catalyst, not consumed).

With reversible = False the legacy irreversible pseudo-first-order law
(r_i = k_i [H+] [ester], water lumped into k) is used instead; that limit is
linear, has a closed-form solution, and remains the solver-verification
reference.

Alkaline route (catalyst = "NaOH"), IRREVERSIBLE saponification (B-AC2):

    step 1:  EGDA + OH- -> EGMA + AcO-
    step 2:  EGMA + OH- -> EG   + AcO-

    r1 = k1(T) [OH-] [EGDA]
    r2 = k2(T) [OH-] [EGMA]

[OH-] is a STATE VARIABLE, not a constant: hydroxide is consumed 1:1 with
acetate released (the leaving group is the carboxylate), so the reaction
self-quenches when NaOH is sub-stoichiometric.  ~1000x faster than the acid
route per mole of catalyst (k_OH(25 C) ~ 0.1 L/(mol s) vs ~1e-4).
"""

from __future__ import annotations

from typing import Sequence, Tuple

from .parameters import KineticParameters

# indices into the SPECIES-ordered state vector
_I_EGDA, _I_EGMA, _I_EG, _I_ACOH, _I_H2O, _I_OH = range(6)


class KineticModel:
    def __init__(self, params: KineticParameters):
        self.params = params

    # -- Arrhenius rate constants, L/(mol s) ---------------------------------
    def k1(self, T_K: float) -> float:
        return self.params.step1.k(T_K)

    def k2(self, T_K: float) -> float:
        return self.params.step2.k(T_K)

    # -- equilibrium constants, dimensionless --------------------------------
    def K1(self, T_K: float) -> float:
        return self.params.eq1.K(T_K)

    def K2(self, T_K: float) -> float:
        return self.params.eq2.K(T_K)

    # -- pseudo-first-order forward constants, 1/s ---------------------------
    def effective_constants(self, T_K: float, c_cat: float) -> Tuple[float, float]:
        """kappa_i = k_i(T) * c_cat, the forward time-scale constants.
        c_cat is [H+] on the acid route (constant along x) or the INLET
        [OH-] on the alkaline route (initial time scale only: OH- depletes)."""
        return self.k1(T_K) * c_cat, self.k2(T_K) * c_cat

    # -- volumetric NET rates, mol/(L s) --------------------------------------
    def rates(self, c: Sequence[float], T_K: float,
              c_h_plus: float) -> Tuple[float, float]:
        """Net rates (positive = ester-cleavage direction) for the state
        vector c in SPECIES order [EGDA, EGMA, EG, AcOH, H2O, OH].
        c_h_plus is used on the acid route only; the alkaline route reads
        the dynamic [OH-] from the state vector."""
        c_egda = max(float(c[_I_EGDA]), 0.0)
        c_egma = max(float(c[_I_EGMA]), 0.0)

        if self.params.catalyst == "NaOH":
            c_oh = max(float(c[_I_OH]), 0.0)
            r1 = self.k1(T_K) * c_oh * c_egda
            r2 = self.k2(T_K) * c_oh * c_egma
            return r1, r2

        if not self.params.reversible:
            r1 = self.k1(T_K) * c_h_plus * c_egda
            r2 = self.k2(T_K) * c_h_plus * c_egma
            return r1, r2

        c_eg = max(float(c[_I_EG]), 0.0)
        c_acoh = max(float(c[_I_ACOH]), 0.0)
        c_h2o = max(float(c[_I_H2O]), 0.0)
        cw_ref = self.params.c_water_ref
        r1 = (self.k1(T_K) * c_h_plus / cw_ref
              * (c_egda * c_h2o - c_egma * c_acoh / self.K1(T_K)))
        r2 = (self.k2(T_K) * c_h_plus / cw_ref
              * (c_egma * c_h2o - c_eg * c_acoh / self.K2(T_K)))
        return r1, r2
