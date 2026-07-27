"""
Sulfuric acid speciation: temperature-dependent bisulfate dissociation and
optional activity-coefficient (Pitzer) treatment.

Why this module exists
----------------------
The catalytic [H+] of the acid route comes from

    H2SO4  ->  H+ + HSO4-        (complete)
    HSO4-  <->  H+ + SO4^2-      (Ka2)

and BOTH refinements the dilute 25 C treatment misses are strong:

  * Temperature.  Bisulfate dissociation is exothermic with a large negative
    heat capacity change (dH ~ -22 kJ/mol, dCp ~ -260 J K-1 mol-1; Hovey &
    Hepler, J. Chem. Soc. Faraday Trans. 1990, 86, 2831).  Ka2 therefore
    falls by ~2 orders of magnitude between 25 and 150 C - the second
    dissociation essentially switches off in a hot reactor.
  * Non-ideality.  At molar acid concentrations the ionic strength is >> 1
    and gamma(SO4^2-) << 1, so the *apparent* dissociation is much larger
    than the dilute formula predicts (Raman/EMF data give ~15-25% sulfate at
    1 mol/kg vs ~1% from the dilute quadratic).

Two Ka2 models and two activity models are provided; they combine as:

  activity_model = "dilute"  (gamma = 1, molarity basis)
      ka2_model = "constant" : legacy behaviour, Ka2 = params.ka2 (25 C)
      ka2_model = "tdep"     : Clarke-Glew (constant-dCp) Ka2(T), anchored
                               at params.ka2 at 25 C with dH0 = -21.9 kJ/mol
                               (NBS-consistent) and dCp0 = -258 J K-1 mol-1
                               (Hovey & Hepler 1990 range -258..-280).
                               Reproduces accepted pK2 within ~0.1 units to
                               250 C (pK2 = 1.99 / 3.07 / 3.85 / 5.41 at
                               25 / 100 / 150 / 250 C).

  activity_model = "pitzer"  (molality basis, concentrated solutions)
      Uses the Pitzer-Roy-Silvester temperature-dependent parameter PACKAGE
      (J. Am. Chem. Soc. 1977, 99, 4930; T-functions as tabulated e.g. in
      Begar et al., JOTCSA 2023, 10, 521, and refit over 0-170 C by Sippola
      & Taskinen, J. Chem. Eng. Data 2014, 59, 2389):

          K2(T)          = exp(-14.0321 + 2825.2/T)     [mol/kg basis]
          beta0(H,HSO4)  =  0.05584 +  46.040/T
          beta1(H,HSO4)  = -0.65758 + 336.514/T
          beta0(H,SO4)   = -0.32806 +  98.607/T
          Cphi(H,SO4)    =  0.25333 -  63.124/T
          beta1(H,SO4) = 0,  C(H,HSO4) = 0

      IMPORTANT: this K2(T) was co-fitted WITH these interaction parameters;
      it is an operational pair and must not be mixed with the
      infinite-dilution Clarke-Glew constant (they differ by ~5x at 150 C by
      construction - the difference is absorbed in the gammas).  For that
      reason the Pitzer route ignores ka2_model and always uses its own K2.

      Debye-Huckel slope Aphi(T) interpolated from Bradley & Pitzer
      (J. Phys. Chem. 1979, 83, 1599; saturation pressure).

Validity: dilute route ~0-250 C at low ionic strength; Pitzer route
0-200 C and total sulfate up to ~6 mol/kg.  The rate laws consume the
CONCENTRATION [H+] produced here; Hammett-acidity corrections to the rate
law itself in very concentrated acid are not modelled.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np
from scipy.optimize import brentq

from .parameters import MOLAR_MASS, R_GAS

T_REF_K = 298.15

# Clarke-Glew anchors for the infinite-dilution (dilute-route) Ka2(T)
DH_KA2_J = -21_900.0        # dissociation enthalpy at 25 C, J/mol
DCP_KA2_J = -258.0          # dissociation heat capacity change, J/(mol K)

# Pitzer-Roy-Silvester temperature functions (see module docstring)
_PRS_LNK2_A, _PRS_LNK2_B = -14.0321, 2825.2

# Debye-Huckel slope for the osmotic coefficient, Bradley & Pitzer (1979),
# saturation pressure; linear interpolation between entries.
_APHI_T_C = np.array([0.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 200.0])
_APHI = np.array([0.3767, 0.3915, 0.4103, 0.4325, 0.4602,
                  0.4922, 0.5298, 0.5730, 0.6230])

_PITZER_B_COEF = 1.2        # Pitzer b, (kg/mol)^0.5
_PITZER_ALPHA = 2.0         # Pitzer alpha for 1-1 / 1-2 electrolytes


# ---------------------------------------------------------------------------
# Ka2 temperature models
# ---------------------------------------------------------------------------
def ka2_clarke_glew(T_K: float, ka2_25C: float) -> float:
    """Infinite-dilution Ka2(T) by the constant-dCp Clarke-Glew equation,
    anchored to the 25 C value `ka2_25C` (dilute route only)."""
    t0 = T_REF_K
    ln_k = (math.log(ka2_25C)
            - DH_KA2_J / R_GAS * (1.0 / T_K - 1.0 / t0)
            + DCP_KA2_J / R_GAS * (t0 / T_K - 1.0 + math.log(T_K / t0)))
    return math.exp(ln_k)


def ka2_prs(T_K: float) -> float:
    """Operational K2(T) of the Pitzer-Roy-Silvester package, mol/kg basis.
    Only meaningful together with the PRS interaction parameters."""
    return math.exp(_PRS_LNK2_A + _PRS_LNK2_B / T_K)


def aphi(T_K: float) -> float:
    """Debye-Huckel slope A_phi(T), interpolated Bradley & Pitzer values."""
    return float(np.interp(T_K - 273.15, _APHI_T_C, _APHI))


# ---------------------------------------------------------------------------
# Dilute-route speciation (gamma = 1)
# ---------------------------------------------------------------------------
def bisulfate_dilute(c_total: float, ka2: float) -> float:
    """[H+] (mol/L) for total sulfate molarity c_total with ideal activities.

    First dissociation complete; extent x of the second solves
        Ka2 = (c_total + x) x / (c_total - x)
    i.e.  x^2 + (c_total + Ka2) x - Ka2 c_total = 0.
    """
    if c_total <= 0.0:
        return 0.0
    b = c_total + ka2
    x = (-b + math.sqrt(b * b + 4.0 * ka2 * c_total)) / 2.0
    return c_total + x


# ---------------------------------------------------------------------------
# Pitzer-route speciation (molality basis)
# ---------------------------------------------------------------------------
def _g(x: float) -> float:
    """Pitzer g(x) = 2[1 - (1+x)e^-x]/x^2."""
    if x < 1e-12:
        return 1.0
    return 2.0 * (1.0 - (1.0 + x) * math.exp(-x)) / (x * x)


def _ln_gamma_ratio(m_h: float, m_hso4: float, m_so4: float,
                    T_K: float) -> float:
    """ln( gamma_H * gamma_SO4 / gamma_HSO4 ) from the PRS Pitzer model.

    Standard Pitzer single-ion expressions for the 3-ion system reduce
    (using electroneutrality m_H = m_HSO4 + 2 m_SO4) to

        ln Gamma = 4 F + 2(m1 - mH) B_H1 + 2(m2 + mH) beta0_H2
                   + 2(2 m2 + mH) mH C_H2
        F = f_gamma + mH m1 B'_H1
    """
    I = 0.5 * (m_h + m_hso4 + 4.0 * m_so4)
    if I <= 0.0:
        return 0.0
    sqrt_i = math.sqrt(I)
    b = _PITZER_B_COEF
    f_gamma = -aphi(T_K) * (sqrt_i / (1.0 + b * sqrt_i)
                            + (2.0 / b) * math.log(1.0 + b * sqrt_i))

    beta0_h1 = 0.05584 + 46.040 / T_K
    beta1_h1 = -0.65758 + 336.514 / T_K
    beta0_h2 = -0.32806 + 98.607 / T_K
    cphi_h2 = 0.25333 - 63.124 / T_K
    c_h2 = cphi_h2 / (2.0 * math.sqrt(2.0))        # C_MX = Cphi/(2 sqrt|zM zX|)

    x = _PITZER_ALPHA * sqrt_i
    b_h1 = beta0_h1 + beta1_h1 * _g(x)
    # B' = dB/dI = -beta1 [1 - (1 + x + x^2/2) e^-x] / (2 I^2)
    bp_h1 = (-beta1_h1 * (1.0 - (1.0 + x + 0.5 * x * x) * math.exp(-x))
             / (2.0 * I * I))

    f_big = f_gamma + m_h * m_hso4 * bp_h1
    return (4.0 * f_big
            + 2.0 * (m_hso4 - m_h) * b_h1
            + 2.0 * (m_so4 + m_h) * beta0_h2
            + 2.0 * (2.0 * m_so4 + m_h) * m_h * c_h2)


def bisulfate_pitzer(m_total: float, T_K: float) -> Dict[str, float]:
    """Speciation of m_total mol/kg total sulfate with PRS Pitzer activities.

    Solves  K2 = (m_H m_SO4 / m_HSO4) * Gamma(m)  for the sulfate molality
    x = m_SO4 in [0, m_total] (Brent; the residual is bracketed because it is
    negative at x=0 and positive as x -> m_total).  Returns molalities, the
    ionic strength, the activity-coefficient ratio and K2 used.
    """
    if not (273.15 <= T_K <= 473.15):
        raise ValueError(
            f"Pitzer speciation is parameterized for 0-200 C; got "
            f"{T_K - 273.15:.1f} C. Use activity_model='dilute' outside it.")
    k2 = ka2_prs(T_K)
    if m_total <= 0.0:
        return {"m_H": 0.0, "m_HSO4": 0.0, "m_SO4": 0.0, "I": 0.0,
                "gamma_ratio": 1.0, "K2": k2}

    def residual(x: float) -> float:
        m_h, m1, m2 = m_total + x, m_total - x, x
        gam = math.exp(_ln_gamma_ratio(m_h, m1, m2, T_K))
        return m_h * x * gam - k2 * m1

    hi = m_total * (1.0 - 1e-12)
    x = brentq(residual, 0.0, hi, xtol=1e-14, rtol=8.9e-16)
    m_h, m1, m2 = m_total + x, m_total - x, x
    return {"m_H": m_h, "m_HSO4": m1, "m_SO4": m2,
            "I": 0.5 * (m_h + m1 + 4.0 * m2),
            "gamma_ratio": math.exp(_ln_gamma_ratio(m_h, m1, m2, T_K)),
            "K2": k2}


# ---------------------------------------------------------------------------
# Entry point used by the mixer
# ---------------------------------------------------------------------------
def h_plus_concentration(c_h2so4_M: float, c_h2o_M: float, T_K: float,
                         params) -> Tuple[float, List[str]]:
    """Catalytic [H+] in mol/L for the configured Ka2/activity models,
    with human-readable notes for the run report.

    params : KineticParameters (fields ka2, ka2_model, activity_model).
    """
    notes: List[str] = []
    if c_h2so4_M <= 0.0:
        return 0.0, notes

    if params.activity_model == "pitzer":
        # kg of water per liter of solution, from the tracked water molarity
        w_kg_L = c_h2o_M * MOLAR_MASS["H2O"] / 1000.0
        spec = bisulfate_pitzer(c_h2so4_M / w_kg_L, T_K)
        c_h = spec["m_H"] * w_kg_L
        notes.append(
            f"[H+] from PRS Pitzer speciation at {T_K - 273.15:.1f} C: "
            f"K2(T) = {spec['K2']:.3e} m, I = {spec['I']:.3f} mol/kg, "
            f"gamma_H*gamma_SO4/gamma_HSO4 = {spec['gamma_ratio']:.4f}")
        notes.append(
            f"[H+] = {c_h:.4f} M = {c_h / c_h2so4_M:.3f} protons per H2SO4 "
            f"(SO4^2- fraction {spec['m_SO4'] / (spec['m_SO4'] + spec['m_HSO4']):.3f})")
        return c_h, notes

    if params.activity_model != "dilute":
        raise ValueError(f"Unknown activity_model '{params.activity_model}'.")

    if params.ka2_model == "tdep":
        ka2 = ka2_clarke_glew(T_K, params.ka2)
        ka2_txt = (f"Ka2({T_K - 273.15:.1f} C) = {ka2:.3e} M "
                   "(Clarke-Glew, dH=-21.9 kJ/mol, dCp=-258 J/mol/K)")
    elif params.ka2_model == "constant":
        ka2 = params.ka2
        ka2_txt = f"Ka2 = {ka2:.3g} M (constant, 25 C value)"
    else:
        raise ValueError(f"Unknown ka2_model '{params.ka2_model}'.")

    c_h = bisulfate_dilute(c_h2so4_M, ka2)
    notes.append(
        f"[H+] from HSO4- equilibrium, dilute activities: {ka2_txt}; "
        f"{c_h:.4f} M = {c_h / c_h2so4_M:.3f} protons per H2SO4")
    return c_h, notes
