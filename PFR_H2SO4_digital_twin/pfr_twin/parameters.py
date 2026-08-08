"""
Single source of truth for every physical, chemical, and operational parameter.

Units convention (used consistently across the whole package)
-------------------------------------------------------------
length        m           concentration   mol/L  (= kmol/m^3)
time          s           rate constant   L/(mol s)   (2nd order: ester + H+)
temperature   K           volumetric flow m^3/s internally, mL/min at the CLI
energy        J/mol       density         g/L (= kg/m^3)

Kinetic parameter provenance
----------------------------
The specific acid-catalyzed hydrolysis of simple acetate esters in aqueous
solution (A-AC2 mechanism, water in vast excess) is one of the classic systems
of physical organic chemistry.  Benchmark values for ethyl acetate + HCl(aq):

    k_cat(25 C) ~ 1.1e-4 L mol^-1 s^-1   (rate = k_cat [ester][H+])
    Ea          ~ 54-65 kJ/mol

(e.g. Bell, "Acid-Base Catalysis"; Kirby in "Comprehensive Chemical Kinetics"
Vol. 10; classic data of Guggenheim / Smith on acetate ester hydrolysis.)

EGDA carries two chemically equivalent acetate groups, so step 1 gains a
statistical factor of ~2 relative to a mono-ester, while step 2 (EGMA, one
remaining group, slightly deactivated by the free hydroxyl) is taken close to
the mono-ester benchmark.  The defaults below reproduce:

    k1(25 C) = 2.27e-4 L/(mol s)     k1/k2 (25 C) ~ 2.2
    k2(25 C) = 1.03e-4 L/(mol s)     k1/k2 (70 C) ~ 2.0

Equilibrium (reverse esterification) provenance
-----------------------------------------------
Ester hydrolysis is NOT irreversible: acid catalysis accelerates the forward
and reverse (Fischer esterification) reactions identically, so the same H+
that drives hydrolysis also drives EGMA + AcOH -> EGDA + H2O and
EG + AcOH -> EGMA + H2O.  The classic benchmark (Berthelot & Pean de
Saint-Gilles; every physical-chemistry text since) for acetate esters is

    K_est = [ester][H2O] / ([AcOH][alcohol]) ~ 4      (per ester group)

for AcOH + EtOH <-> EtOAc + H2O.  Because the reaction is mole-conserving
(delta n = 0), the mole-fraction and molar-concentration constants coincide,
so the hydrolysis-direction constant per acetate group is

    K_g = 1 / K_est ~ 0.25          (dimensionless, concentration basis)

Statistical factors for the diol system (same logic as for k1/k2 above):
step 1 hydrolyses one of TWO equivalent EGDA esters and its reverse
esterifies the SINGLE EGMA hydroxyl -> K1 = 2*K_g = 0.50; step 2 hydrolyses
the single EGMA ester while its reverse esterifies one of TWO equivalent EG
hydroxyls -> K2 = K_g/2 = 0.125.  (Their product K1*K2 = K_g^2 is then the
statistically consistent overall EGDA + 2 H2O <-> EG + 2 AcOH constant.)
Esterification is nearly thermoneutral (K_est ~ const over 25-80 C), so the
hydrolysis dH is small and positive; +5 kJ/mol is used as the default van 't
Hoff slope.

With water at ~50 M the equilibria still lie far to the hydrolysis side
(equilibrium EGDA conversion > 95% for a 0.5 M feed), but the reverse terms
(i) cap the ultimate conversion below 100%, (ii) slow the net rate as AcOH
accumulates, and (iii) let the twin handle concentrated / low-water feeds
and even esterification-direction operation correctly.

Alkaline (NaOH) route provenance
--------------------------------
The twin also supports NaOH as the "catalyst" option.  Chemically this is a
DIFFERENT reaction, saponification (B-AC2):

    ester + OH-  ->  alcohol + AcO-        (per acetate group)

Three consequences, all modelled explicitly:

  * MUCH faster: for ethyl acetate + NaOH the classic benchmark is
    k_OH(25 C) ~ 0.11 L mol^-1 s^-1 with Ea ~ 46-48 kJ/mol (conductometric
    kinetics, countless student/lab replications), i.e. ~1000x the
    acid-catalyzed constant per mole of catalyst.
  * NOT catalytic: the leaving carboxylate is the conjugate base of AcOH
    (pKa 4.76 << 15.7), so one OH- is consumed irreversibly per acetate
    group released; OH- is a stoichiometric reagent that can run out and
    stop the reaction (limiting-reagent behaviour).
  * Effectively IRREVERSIBLE: the carboxylate carbonyl is not electrophilic
    enough for re-esterification and the acid-base step is ~10^9 downhill,
    so no equilibrium terms apply on the alkaline route.

Statistical factor 2 for EGDA's two equivalent acetate groups as on the acid
route (the inductive effect of the second acetoxy group may raise k1 further;
recalibrate).  The defaults below reproduce

    k1_OH(25 C) = 0.226 L/(mol s)      k2_OH(25 C) = 0.101 L/(mol s)

Under NaOH the tracked "AcOH" pool is the TOTAL acetate (present as AcO-/
NaOAc), and net water consumption is zero (OH- is the nucleophile).

These are literature-ANCHORED estimates, mathematically consistent and of the
right order of magnitude; recalibrate A, Ea, K_ref, dH against your own lab
data (PFR_lab_scale_results) before using the twin quantitatively.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict

# ----------------------------------------------------------------------------
# Physical constants
# ----------------------------------------------------------------------------
R_GAS = 8.314462618          # J/(mol K)

# Species tracked along the reactor (order = ODE state-vector order).
# "AcOH" is the TOTAL acetate pool (free acid under H2SO4, acetate ion /
# NaOAc under NaOH); "OH" is free hydroxide (identically 0 on the acid route,
# a consumed stoichiometric reagent on the alkaline route).
SPECIES = ["EGDA", "EGMA", "EG", "AcOH", "H2O", "OH"]

# Supported catalyst systems
CATALYSTS = ("H2SO4", "NaOH")

MOLAR_MASS: Dict[str, float] = {   # g/mol
    "EGDA":  146.14,
    "EGMA":  104.10,
    "EG":     62.07,
    "AcOH":   60.05,
    "H2SO4":  98.08,
    "NaOH":   39.997,
    "H2O":    18.015,
    "OH":     17.008,
}

# Second dissociation constant of H2SO4 (HSO4- <-> H+ + SO4^2-), 25 C, mol/L.
# First dissociation is treated as complete.  NOTE: Ka2 is STRONGLY
# temperature dependent (exothermic dissociation, dH ~ -22 kJ/mol, with a
# large negative dCp ~ -260 J/mol/K; Hovey & Hepler, JCS Faraday Trans. 1990,
# 86, 2831): it falls ~2 orders of magnitude from 25 to 150 C.  This constant
# is only the 25 C anchor; see KineticParameters.ka2_model and speciation.py
# for the temperature dependence and the activity-coefficient (Pitzer)
# option for concentrated acid.
KA2_HSO4 = 1.02e-2

# Molarity of pure water at 25 C, mol/L.  Reference water concentration at
# which the pseudo-order catalytic constants k1, k2 were calibrated (dilute
# aqueous ester hydrolysis); the reversible rate law scales the forward term
# with C_H2O / C_WATER_REF so k1, k2 keep their literature meaning and units.
C_WATER_REF = 55.34

# Molecular diffusivity used for the plug-flow validity diagnostics, m^2/s
# (typical small organic solute in water at ~25-70 C, order of magnitude).
DIFFUSIVITY_LIQ = 1.0e-9


# ----------------------------------------------------------------------------
# Kinetics
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class ArrheniusStep:
    """k(T) = A * exp(-Ea / (R T)) with A in L/(mol s) and Ea in J/mol."""
    A: float
    Ea: float

    def k(self, T_K: float) -> float:
        return self.A * math.exp(-self.Ea / (R_GAS * T_K))


@dataclass(frozen=True)
class EquilibriumStep:
    """Concentration-based hydrolysis equilibrium constant of one step,

        K(T) = ( [ester product / alcohol] [AcOH] / ([ester] [H2O]) )_eq

    dimensionless (delta n = 0), with van 't Hoff temperature dependence

        K(T) = K_ref * exp[ -(dH_J / R) (1/T - 1/T_ref_K) ].

    dH_J is the standard reaction enthalpy of the HYDROLYSIS direction
    (small and positive for acetate esters: esterification is mildly
    exothermic, so K rises weakly with temperature).
    """
    K_ref: float
    dH_J: float
    T_ref_K: float = 298.15

    def K(self, T_K: float) -> float:
        return self.K_ref * math.exp(-self.dH_J / R_GAS
                                     * (1.0 / T_K - 1.0 / self.T_ref_K))


# Literature-anchored defaults for the alkaline (saponification) route:
# k1_OH(25 C) = 0.226 L/(mol s), k2_OH(25 C) = 0.101 L/(mol s)
STEP1_NAOH = ArrheniusStep(A=2.6e7, Ea=46_000.0)
STEP2_NAOH = ArrheniusStep(A=2.6e7, Ea=48_000.0)


@dataclass(frozen=True)
class KineticParameters:
    """
    Acid route (catalyst = "H2SO4"), reversible rate laws (first order in
    each participant, specific acid catalysis identical forward and reverse;
    C_w_ref = C_WATER_REF):

        r1 = k1(T) [H+] ( [EGDA] [H2O] - [EGMA][AcOH] / K1(T) ) / C_w_ref
        r2 = k2(T) [H+] ( [EGMA] [H2O] - [EG]  [AcOH] / K2(T) ) / C_w_ref

    Both vanish exactly at chemical equilibrium (Q_i = K_i), and the implied
    reverse rate constants  k_i,rev = k_i / (K_i C_w_ref)  are DERIVED from
    the equilibrium constants, so the model is thermodynamically consistent
    by construction (microscopic reversibility).  At [H2O] = C_w_ref the
    forward term reduces to the legacy pseudo-first-order law, so k1, k2
    keep their literature calibration.

    reversible = False recovers the legacy irreversible model

        r1 = k1(T) [H+] [EGDA],   r2 = k2(T) [H+] [EGMA]

    (water lumped into k), which has a closed-form solution and is used for
    solver verification and back-compatibility studies.

    Alkaline route (catalyst = "NaOH"), saponification -- irreversible,
    second order, with OH- a CONSUMED stoichiometric reagent (its dynamic
    concentration is a state variable, not a constant):

        r1 = k1(T) [OH-] [EGDA]
        r2 = k2(T) [OH-] [EGMA]

    Here step1/step2 hold the alkaline constants (use `default_kinetics`),
    eq1/eq2/reversible/h_plus_model are meaningless and reversible must be
    False (saponification is pulled ~10^9-fold downhill by the acid-base
    step; there is no back reaction to represent).

    h_plus_model (acid route only):
        "equilibrium"    - complete 1st dissociation + HSO4- equilibrium (Ka2)
        "stoichiometric" - [H+] = n_eff_protons * [H2SO4]

    ka2_model (acid route, h_plus_model = "equilibrium" only):
        "tdep"     - temperature-dependent Ka2(T) (Clarke-Glew anchored at
                     `ka2` at 25 C; Hovey & Hepler 1990 thermochemistry).
                     Default: Ka2 falls ~2 orders of magnitude 25 -> 150 C,
                     which matters whenever the reactor is not at ~25 C.
        "constant" - legacy 25 C value at all temperatures.

    activity_model (acid route, h_plus_model = "equilibrium" only):
        "dilute" - ideal activities (gamma = 1); adequate for dilute acid.
        "pitzer" - Pitzer-Roy-Silvester activity model with its own co-fitted
                   K2(T) (ka2_model is then ignored); preferable at molar
                   acid concentrations, where non-ideality raises the true
                   [H+] well above the dilute prediction.  See speciation.py.
    """
    step1: ArrheniusStep = ArrheniusStep(A=1.0e6, Ea=55_000.0)
    step2: ArrheniusStep = ArrheniusStep(A=1.0e6, Ea=57_000.0)
    eq1: EquilibriumStep = EquilibriumStep(K_ref=0.50, dH_J=5_000.0)
    eq2: EquilibriumStep = EquilibriumStep(K_ref=0.125, dH_J=5_000.0)
    reversible: bool = True
    catalyst: str = "H2SO4"
    c_water_ref: float = C_WATER_REF
    h_plus_model: str = "equilibrium"
    n_eff_protons: float = 1.0       # used only by the stoichiometric model
    ka2: float = KA2_HSO4
    ka2_model: str = "tdep"          # "tdep" | "constant"
    activity_model: str = "dilute"   # "dilute" | "pitzer"

    def __post_init__(self):
        if self.catalyst not in CATALYSTS:
            raise ValueError(f"Unknown catalyst '{self.catalyst}'; "
                             f"supported: {CATALYSTS}.")
        if self.catalyst == "NaOH" and self.reversible:
            raise ValueError(
                "catalyst='NaOH' requires reversible=False: saponification "
                "is irreversible (the released acetate is instantly "
                "deprotonated; no re-esterification path exists). "
                "Use default_kinetics('NaOH') for consistent defaults.")
        if self.ka2_model not in ("tdep", "constant"):
            raise ValueError(f"Unknown ka2_model '{self.ka2_model}'.")
        if self.activity_model not in ("dilute", "pitzer"):
            raise ValueError(f"Unknown activity_model '{self.activity_model}'.")


def default_kinetics(catalyst: str = "H2SO4", *, reversible: bool = True,
                     **overrides) -> KineticParameters:
    """Literature-anchored KineticParameters for the chosen catalyst system.

    For "H2SO4": the reversible acid-catalyzed defaults (set reversible=False
    for the legacy irreversible twin).  For "NaOH": the saponification
    constants with reversible forced False (the `reversible` argument is
    ignored on this route).  Any dataclass field can be overridden by
    keyword (e.g. step1=..., h_plus_model=...).
    """
    if catalyst == "H2SO4":
        return KineticParameters(reversible=reversible, **overrides)
    if catalyst == "NaOH":
        overrides.setdefault("step1", STEP1_NAOH)
        overrides.setdefault("step2", STEP2_NAOH)
        return KineticParameters(catalyst="NaOH", reversible=False,
                                 **overrides)
    raise ValueError(f"Unknown catalyst '{catalyst}'; supported: {CATALYSTS}.")


# ----------------------------------------------------------------------------
# Reactor geometry
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class ReactorGeometry:
    """Straight cylindrical tube, optionally filled with INERT packing.

    Defaults match the 200 mm x 18 mm ID lab PFR and an OPEN (unpacked)
    tube.  Packing is an optional physical configuration of one reactor,
    never a global assumption of the framework:

        packing_enabled = False  ->  epsilon = 1,  tau = A L / Q
        packing_enabled = True   ->  tau = epsilon_b A L / Q

    `bed_void_fraction` (epsilon_b) is the fraction of reactor volume
    occupied by FLOWING interstitial liquid.  It is deliberately NOT
    identified with particle/internal porosity: stagnant liquid inside
    porous inert particles only joins the residence time through a
    mass-transfer/holdup model that this twin does not claim to have.
    `particle_porosity` is therefore carried as metadata only and does not
    enter any calculation."""
    length_m: float = 0.200
    diameter_m: float = 0.018
    packing_enabled: bool = False
    bed_void_fraction: float = 1.0
    particle_porosity: float = 0.0        # metadata only; see docstring

    def __post_init__(self):
        if self.packing_enabled and not (0.0 < self.bed_void_fraction <= 1.0):
            raise ValueError(
                "bed_void_fraction must lie in (0, 1] when packing is "
                f"enabled; got {self.bed_void_fraction}.")

    @property
    def void_fraction(self) -> float:
        """epsilon actually used by the hydrodynamics (1 when unpacked)."""
        return float(self.bed_void_fraction) if self.packing_enabled else 1.0

    @property
    def area_m2(self) -> float:
        """Empty-tube cross-section (geometric)."""
        return math.pi * self.diameter_m ** 2 / 4.0

    @property
    def flow_area_m2(self) -> float:
        """Cross-section carrying flowing liquid; sets the INTERSTITIAL
        velocity u = Q / flow_area, hence the residence time."""
        return self.area_m2 * self.void_fraction

    @property
    def volume_m3(self) -> float:
        """Total (empty-tube) reactor volume."""
        return self.area_m2 * self.length_m

    @property
    def liquid_volume_m3(self) -> float:
        """Flowing-liquid holdup: epsilon * V_tube."""
        return self.volume_m3 * self.void_fraction

    @property
    def volume_mL(self) -> float:
        return self.volume_m3 * 1.0e6

    @property
    def liquid_volume_mL(self) -> float:
        return self.liquid_volume_m3 * 1.0e6

    def residence_time_s(self, Q_total_m3_s: float) -> float:
        """tau = epsilon A L / Q  (= A L / Q for an unpacked tube)."""
        return self.liquid_volume_m3 / max(Q_total_m3_s, 1e-30)


# ----------------------------------------------------------------------------
# Numerics
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class SolverSettings:
    method: str = "LSODA"
    rtol: float = 1.0e-9
    atol: float = 1.0e-12
    n_points: int = 201          # saved profile resolution along x
