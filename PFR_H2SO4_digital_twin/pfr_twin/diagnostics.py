"""
Plug-flow validity diagnostics.

A digital twin should say when its own idealization is trustworthy.  For a
liquid-phase tubular reactor the 1D plug-flow picture requires (i) a flat
velocity profile or fast radial mixing, and (ii) negligible axial dispersion.
This module reports:

  * Reynolds number and flow regime,
  * the radial diffusion time t_rad = R^2 / D_m versus the residence time tau
    (t_rad << tau  ->  Taylor-Aris dispersion regime, radially well mixed;
     t_rad >> tau  ->  segregated laminar flow, plug flow is optimistic),
  * when applicable, the Taylor-Aris axial dispersion coefficient and the
    Bodenstein number Bo = u L / D_ax (Bo >~ 100 -> <1% deviation from PFR).

Water properties are used for the mixture (dilute aqueous solutions);
viscosity from the Vogel correlation, density from tabulated values.
"""

from __future__ import annotations

from typing import List

import numpy as np

from .mixer import InletState
from .parameters import DIFFUSIVITY_LIQ, ReactorGeometry

_T_TAB = np.array([273.15, 293.15, 313.15, 333.15, 353.15, 373.15])   # K
_RHO_TAB = np.array([999.8, 998.2, 992.2, 983.2, 971.8, 958.4])       # g/L


def water_density_g_L(T_K: float) -> float:
    return float(np.interp(T_K, _T_TAB, _RHO_TAB))


def water_viscosity_Pa_s(T_K: float) -> float:
    """Vogel-type correlation for liquid water, valid ~273-373 K."""
    return 2.414e-5 * 10.0 ** (247.8 / (T_K - 140.0))


def flow_diagnostics(inlet: InletState, geometry: ReactorGeometry,
                     T_K: float, D_m: float = DIFFUSIVITY_LIQ) -> List[str]:
    u = inlet.Q_total_m3_s / geometry.area_m2
    tau = geometry.length_m / u
    radius = geometry.diameter_m / 2.0

    # dilute aqueous mixture: stream-blend density at 25 C, scaled with T like water
    rho = inlet.density_g_L * water_density_g_L(T_K) / water_density_g_L(298.15)
    mu = water_viscosity_Pa_s(T_K)
    re = rho * u * geometry.diameter_m / mu

    t_rad = radius ** 2 / D_m

    lines = [
        f"Reactor volume              : {geometry.volume_mL:7.1f} mL "
        f"(L = {geometry.length_m * 1e3:.0f} mm, ID = {geometry.diameter_m * 1e3:.1f} mm)",
        f"Mixture density (est.)      : {rho:7.1f} g/L",
        f"Water viscosity at T        : {mu * 1e3:7.4f} mPa s",
        f"Reynolds number             : {re:7.1f} "
        f"({'laminar' if re < 2100 else 'transitional' if re < 4000 else 'turbulent'})",
        f"Radial diffusion time R^2/D : {t_rad:9.3g} s   vs   tau = {tau:.1f} s",
    ]

    if re < 2100:
        if t_rad < 0.1 * tau:
            d_ax = D_m + u ** 2 * radius ** 2 / (48.0 * D_m)
            bo = u * geometry.length_m / d_ax
            lines.append(
                f"Taylor-Aris regime          : D_ax = {d_ax:.3g} m^2/s, "
                f"Bo = uL/D_ax = {bo:.1f} "
                f"({'plug flow OK (Bo > 100)' if bo > 100 else 'significant axial dispersion (Bo < 100)'})"
            )
        elif t_rad > 10.0 * tau:
            lines.append(
                "ADVISORY: laminar flow with t_rad >> tau -> radially segregated "
                "streamlines; the real reactor will deviate from ideal plug flow. "
                "Narrow-bore tubing, coiled/static-mixer inserts, or higher flow "
                "rates would tighten the residence-time distribution."
            )
        else:
            lines.append(
                "ADVISORY: laminar flow with t_rad ~ tau -> partial radial mixing; "
                "expect moderate deviation from ideal plug flow."
            )
    else:
        lines.append("Turbulent/transitional flow: plug-flow idealization reasonable.")

    return lines
