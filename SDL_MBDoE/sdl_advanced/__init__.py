"""
sdl_advanced - Layer 2+ : realistic CPR + Fourier-80 virtual instrument and
Bayesian, resource-aware experimental design on top of the existing sdl
baseline (which is preserved unchanged as the regression baseline).

Physical system represented (Reacnostics liquid CPR + Bruker Fourier 80):

    ONE axially moving sampling capillary (a continuous position z, no fixed
    ports, no selector valve) -> one transfer line -> NMR flow cell.

Measurement pathway (strictly modular, so simulated NMR can later be replaced
by real Fourier 80 data without touching inference or design):

    Layer 1 concentration at z  (chemistry - layer1_bridge, unchanged)
      -> transfer.py        sample transport: delay, RTD dispersion,
                            continued reaction, flushing/carryover
      -> spectral.py        NMR forward model (FID or analytic frequency
                            domain), refactored from EGDA_NMR_sim/sim_nmr(2).py
      -> spectral_fit.py    deconvolution -> concentration estimates + Sigma_y
      -> inference          (baseline WLS/FIM or Bayesian model ensemble)
      -> design             (spatial_design + bayes_design, resource-aware)

Truth/inference firewall: instrument.py owns everything hidden; controllers
see only Measurement objects (y, cov_y, QC metadata).
"""

__version__ = "0.1.0"

from .spectral import (AcquisitionSettings, SpectralNuisance, NMRSimulator,
                       LAYER1_TO_NMR, NMR_TO_LAYER1, water_shift)
from .spectral_fit import (SpectralFitter, QuantificationResult,
                           SpectralCovarianceModel, calibrate_responses)
from .transfer import TransferConfig, TransferLine
from .spatial_design import (SpatialDesignConfig, fixed_equal_positions,
                             SpatialDesigner)
from .resources import ResourceCosts, ResourceMeter
from .instrument import AdvancedVirtualLaboratory, InstrumentConfig
from .posterior import GaussianPrior, LaplacePosterior
from .model_ensemble import (CandidateModel, ModelEnsemble,
                             build_egda_family, AssumedTransfer,
                             TransportAwareInference)
from .adequacy import AdequacyGovernor, AdequacyReport, GovernorState
from .bayes_design import AdvancedSelector, expected_information_gain
from .controller import (run_advanced_strategy, AdvancedStrategyResult,
                         QCGateConfig, measure_with_qc)
