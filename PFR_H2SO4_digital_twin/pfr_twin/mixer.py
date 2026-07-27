"""
Ideal micromixer model.

Stream 1 (aqueous EGDA) and Stream 2 (aqueous catalyst: H2SO4 or NaOH) are
blended instantly and perfectly; the mixed composition is the inlet boundary
condition of the PFR at x = 0.  Assumptions:

  * isothermal mixing (both streams pre-heated to the reactor temperature),
  * negligible volume change of mixing (volumetric flows are additive),
  * H2SO4 route: first dissociation complete; second dissociation either
    solved from the HSO4-/SO4^2- equilibrium (default) or approximated
    stoichiometrically; acetic acid produced downstream (pKa 4.76)
    contributes negligible H+ against the strong-acid background, so [H+]
    is constant along x,
  * NaOH route: complete dissociation, [OH-] = [NaOH] at the inlet.  OH- is
    NOT constant downstream - it is consumed 1:1 with acetate released
    (saponification), which the reactor tracks as a state variable.  Feeding
    free AcOH together with NaOH is rejected: it would neutralize the base
    instantly and is not modelled.

Water molarity of each stream is reconstructed from the stream density minus
the solute mass:  [H2O] = (rho - sum_i C_i * M_i) / M_H2O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

from .parameters import MOLAR_MASS, SPECIES, KineticParameters


@dataclass
class Stream:
    """One feed stream to the micromixer.

    composition : mol/L of *solutes* (any of EGDA, EGMA, EG, AcOH, H2SO4,
                  NaOH).
    density_g_L : total solution density, used only to reconstruct [H2O]
                  and for the Reynolds-number diagnostics.
    """
    name: str
    Q_mL_min: float
    composition: Dict[str, float]
    density_g_L: float = 1000.0

    @property
    def Q_m3_s(self) -> float:
        return self.Q_mL_min * 1.0e-6 / 60.0

    def water_molarity(self) -> float:
        solute_mass = sum(c * MOLAR_MASS[sp] for sp, c in self.composition.items())
        c_w = (self.density_g_L - solute_mass) / MOLAR_MASS["H2O"]
        if c_w <= 0.0:
            raise ValueError(
                f"Stream '{self.name}': density {self.density_g_L} g/L is "
                f"inconsistent with the declared solute load."
            )
        return c_w


@dataclass
class InletState:
    """Mixed-cup state leaving the micromixer = PFR inlet (x = 0)."""
    conc: Dict[str, float]        # mol/L for every entry of SPECIES
    c_h2so4: float                # total sulfate molarity, mol/L (acid route)
    c_h_plus: float               # catalytic proton concentration, mol/L
    Q_total_m3_s: float
    density_g_L: float
    c_naoh: float = 0.0           # total NaOH molarity, mol/L (alkaline route)
    notes: List[str] = field(default_factory=list)

    @property
    def c_cat0(self) -> float:
        """Inlet concentration of the rate-driving species: [H+] on the acid
        route, [OH-] on the alkaline route."""
        return self.c_h_plus if self.c_naoh <= 0.0 else self.conc["OH"]


def bisulfate_equilibrium(c_total: float, ka2: float) -> float:
    """[H+] for H2SO4 of total molarity c_total.

    First dissociation complete:  H2SO4 -> H+ + HSO4-.
    Second dissociation extent x from  Ka2 = (c_total + x) x / (c_total - x):

        x^2 + (c_total + Ka2) x - Ka2 c_total = 0
    """
    if c_total <= 0.0:
        return 0.0
    b = c_total + ka2
    x = (-b + math.sqrt(b * b + 4.0 * ka2 * c_total)) / 2.0
    return c_total + x


def mix_streams(stream1: Stream, stream2: Stream,
                kinetics: KineticParameters) -> InletState:
    """Flow-weighted ideal blending of the two feed streams."""
    q1, q2 = stream1.Q_m3_s, stream2.Q_m3_s
    q_tot = q1 + q2
    if q_tot <= 0.0:
        raise ValueError("Total volumetric flow must be positive.")

    def blend(c1: float, c2: float) -> float:
        return (q1 * c1 + q2 * c2) / q_tot

    def blend_solute(sp: str) -> float:
        return blend(stream1.composition.get(sp, 0.0),
                     stream2.composition.get(sp, 0.0))

    conc = {}
    for sp in SPECIES:
        if sp == "H2O":
            conc[sp] = blend(stream1.water_molarity(), stream2.water_molarity())
        elif sp == "OH":
            conc[sp] = 0.0          # set below on the alkaline route
        else:
            conc[sp] = blend_solute(sp)

    c_h2so4 = blend_solute("H2SO4")
    c_naoh = blend_solute("NaOH")

    notes = []
    if kinetics.catalyst == "NaOH":
        if c_h2so4 > 0.0:
            raise ValueError(
                "catalyst='NaOH' but a feed stream declares H2SO4; "
                "acid/base cross-feeds (mutual neutralization) are not modelled.")
        if conc["AcOH"] > 0.0:
            raise ValueError(
                "Feeding free AcOH together with NaOH is not modelled: it "
                "would instantly neutralize an equivalent amount of OH-.")
        conc["OH"] = c_naoh          # complete dissociation of the strong base
        c_h = 0.0
        if c_naoh > 0.0:
            notes.append(
                f"[OH-] = [NaOH] = {c_naoh:.4f} M (complete dissociation; "
                "consumed 1:1 with acetate released - stoichiometric "
                "reagent, not a catalyst)")
    else:
        if c_naoh > 0.0:
            raise ValueError(
                "catalyst='H2SO4' but a feed stream declares NaOH; "
                "acid/base cross-feeds (mutual neutralization) are not modelled.")
        if kinetics.h_plus_model == "equilibrium":
            c_h = bisulfate_equilibrium(c_h2so4, kinetics.ka2)
            if c_h2so4 > 0.0:
                notes.append(
                    f"[H+] from HSO4- equilibrium (Ka2 = {kinetics.ka2:.3g} M): "
                    f"{c_h:.4f} M = {c_h / c_h2so4:.3f} protons per H2SO4"
                )
        elif kinetics.h_plus_model == "stoichiometric":
            c_h = kinetics.n_eff_protons * c_h2so4
            notes.append(
                f"[H+] stoichiometric: {kinetics.n_eff_protons:g} x "
                f"[H2SO4] = {c_h:.4f} M"
            )
        else:
            raise ValueError(f"Unknown h_plus_model '{kinetics.h_plus_model}'.")

    rho_mix = (q1 * stream1.density_g_L + q2 * stream2.density_g_L) / q_tot

    return InletState(conc=conc, c_h2so4=c_h2so4, c_h_plus=c_h,
                      Q_total_m3_s=q_tot, density_g_L=rho_mix,
                      c_naoh=c_naoh, notes=notes)
