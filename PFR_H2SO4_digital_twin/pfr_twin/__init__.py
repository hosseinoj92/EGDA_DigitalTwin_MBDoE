"""
pfr_twin - 1D deterministic digital twin of an isothermal plug flow reactor
for the cleavage of ethylene glycol diacetate (EGDA) with a selectable
catalyst system:

  catalyst = "H2SO4"  - REVERSIBLE acid-catalyzed hydrolysis (reverse =
                        Fischer esterification), [H+] a true catalyst:

        EGDA + H2O <--H+--> EGMA + AcOH        (step 1, Keq K1)
        EGMA + H2O <--H+--> EG   + AcOH        (step 2, Keq K2)

  catalyst = "NaOH"   - IRREVERSIBLE saponification (~1000x faster per mole
                        of catalyst), OH- consumed stoichiometrically:

        EGDA + OH-  ---->  EGMA + AcO-         (step 1)
        EGMA + OH-  ---->  EG   + AcO-         (step 2)

Modules
-------
parameters   : all physical / kinetic / geometric parameters (single source of truth)
mixer        : ideal micromixer -> inlet boundary condition at x = 0
kinetics     : Arrhenius / van 't Hoff constants and per-catalyst rate laws
reactor      : steady-state 1D PFR integration (scipy.solve_ivp)
analytical   : closed-form irreversible-limit solution + coupled-equilibrium
               solver (verification of the integrator and of thermodynamic
               consistency)
diagnostics  : flow-regime / plug-flow-validity checks (Re, dispersion, radial mixing)
plotting     : styled matplotlib figures, each paired with a data CSV
runio        : hyperparameter-tagged run folders + CSV writers
"""

__version__ = "1.3.0"

from .parameters import (
    R_GAS,
    MOLAR_MASS,
    SPECIES,
    CATALYSTS,
    C_WATER_REF,
    ArrheniusStep,
    EquilibriumStep,
    KineticParameters,
    default_kinetics,
    ReactorGeometry,
    SolverSettings,
)
from .mixer import Stream, InletState, mix_streams
from .kinetics import KineticModel
from .reactor import PFRResult, simulate_pfr
from .analytical import analytical_profiles, equilibrium_state, reaction_quotients
from .diagnostics import flow_diagnostics
from .runio import (
    run_tag,
    resolve_root,
    make_run_dir,
    write_run_config,
    write_columns_csv,
    write_rows_csv,
)
