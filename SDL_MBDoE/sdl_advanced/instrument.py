"""
AdvancedVirtualLaboratory: the hidden-truth side of the advanced system.

Owns (and hides): the true kinetic parameters, the Layer 1 simulator, the
true spectral nuisance parameters, the transfer-line truth, and the RNG.

Measurement pathway (never short-circuited in 'nmr' mode):

    Layer 1 concentrations at z (theta_true)          [chemistry]
    -> TransferLine.sample: delay/RTD/reaction/carryover   [transport]
    -> NMRSimulator.simulate: realistic spectrum           [instrument]
    -> SpectralFitter.fit: concentrations + Sigma_y        [public analysis]
    -> Measurement(y, cov_y, meta/QC)                      [what leaves]

FIREWALL: controllers receive ONLY Measurement objects (y, cov_y, z, u, QC
metadata and - optionally - the spectra themselves, which are legitimate
instrument output).  reveal_truth() exists solely for post-campaign scoring
and counts its calls, mirroring sdl.truth.VirtualLaboratory.

observation_mode='direct' bypasses the NMR (used by baseline-equivalent
strategies and the F-noNMR ablation): concentrations + legacy NoiseModel
noise, cov_y=None so InferenceModel reconstructs the assumed covariance -
bit-for-bit the legacy observation when transfer is also disabled.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

_SDL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SDL_DIR not in sys.path:
    sys.path.insert(0, _SDL_DIR)

from sdl.layer1_bridge import Layer1Bridge, OperatingConditions  # noqa: E402
from sdl.observation import Measurement, NoiseModel              # noqa: E402
from pfr_twin.parameters import SPECIES as L1_SPECIES            # noqa: E402
from pfr_twin import KineticModel                                # noqa: E402

from .spectral import (AcquisitionSettings, NMRSimulator,        # noqa: E402
                       SpectralNuisance, QUANTIFIED_SPECIES)
from .spectral_fit import SpectralFitter, calibrate_responses    # noqa: E402
from .transfer import TransferConfig, TransferLine               # noqa: E402
from .resources import ResourceCosts, ResourceMeter              # noqa: E402


@dataclass(frozen=True)
class InstrumentConfig:
    observation_mode: str = "nmr"        # "nmr" | "direct"
    nmr_mode: str = "realistic"          # "ideal" | "realistic"
    store_spectra: bool = False
    species_measured: Tuple[str, ...] = QUANTIFIED_SPECIES
    # pre-campaign per-species response calibration against prepared
    # standards (the real Fourier-80 workflow); absorbs systematic
    # lineshape/response bias into measured public factors
    calibrate_responses: bool = True

    def __post_init__(self):
        if self.observation_mode not in ("nmr", "direct"):
            raise ValueError(f"Unknown observation_mode "
                             f"'{self.observation_mode}'.")
        if self.nmr_mode not in ("ideal", "realistic"):
            raise ValueError(f"Unknown nmr_mode '{self.nmr_mode}'.")


class AdvancedVirtualLaboratory:
    def __init__(self,
                 theta_true: Dict[str, float],
                 bridge: Layer1Bridge,
                 config: InstrumentConfig,
                 acq: AcquisitionSettings,
                 nuisance_true: SpectralNuisance,
                 transfer: TransferConfig,
                 costs: ResourceCosts,
                 seed: int = 0,
                 noise_direct: Optional[NoiseModel] = None,
                 calibration_gain: Optional[Dict[str, float]] = None):
        self._theta_true = dict(theta_true)            # hidden
        self._bridge = bridge
        self._rng = np.random.default_rng(seed)
        self.config = config
        self.acq = acq
        nu = nuisance_true if config.nmr_mode == "realistic" \
            else nuisance_true.ideal()
        self._nmr = NMRSimulator(acq, nu)              # truth-side simulator
        self._fitter = SpectralFitter(acq, config.species_measured)
        self._transfer = TransferLine(transfer, bridge.geometry.length_m)
        self._noise_direct = noise_direct or NoiseModel()
        self.calibration_gain = calibration_gain or {}
        self.meter = ResourceMeter(costs, bridge.geometry.volume_mL)
        self.species = tuple(config.species_measured)
        self.n_experiments_run = 0
        self.n_acquisitions = 0
        self.n_truth_reveals = 0
        self._last_u: Optional[OperatingConditions] = None
        # pre-campaign response calibration: prepared standards measured
        # through the REAL (truth-side) channel, fitted by the public
        # fitter - standard compositions are public, so no firewall breach
        if (config.observation_mode == "nmr" and config.calibrate_responses
                and config.nmr_mode == "realistic"):
            calibrate_responses(
                self._fitter,
                lambda std, r: self._nmr.simulate(std, r)[:2],
                self._rng)

    # ------------------------------------------------------------------ #
    @property
    def length_m(self) -> float:
        return self._bridge.geometry.length_m

    def _true_profile(self, u: OperatingConditions,
                      z_m: np.ndarray) -> List[Dict[str, float]]:
        """Hidden true composition (ALL Layer-1 species) at each z."""
        flat = self._bridge.concentrations_at(self._theta_true, u, z_m,
                                              L1_SPECIES)
        nz = len(z_m)
        return [{sp: float(flat[i * nz + k]) for i, sp in enumerate(L1_SPECIES)}
                for k in range(nz)]

    def _propagator(self, u: OperatingConditions, T_line_C: Optional[float]):
        """Batch-reaction propagator at the transfer-line temperature,
        closed over the hidden truth (used only inside this class)."""
        kin = self._bridge.kinetics_from_theta(self._theta_true)
        model = KineticModel(kin)
        inlet = self._bridge._inlet(u, kin)
        T_K = (T_line_C if T_line_C is not None else u.T_C) + 273.15

        def propagate(conc: Dict[str, float], tau_s: float
                      ) -> Dict[str, float]:
            if tau_s <= 0.0:
                return dict(conc)
            arr = {sp: np.array([conc.get(sp, 0.0)]) for sp in L1_SPECIES}
            out = self._bridge._advance_batch(arr, model, T_K,
                                              inlet.c_h_plus, tau_s)
            return {sp: float(out[sp][0]) for sp in L1_SPECIES}

        return propagate

    # ------------------------------------------------------------------ #
    def run_profile(self, u: OperatingConditions,
                    z_positions: Sequence[float],
                    reacquire: bool = False) -> Measurement:
        """Set condition u, sample the requested positions in the given
        order (one moving capillary!), return ONE species-major Measurement
        carrying its own covariance and QC metadata.

        The meter's condition logging is idempotent: repeated calls at an
        UNCHANGED (T, Q, C_EGDA, C_cat) - e.g. adaptive one-z-at-a-time
        sampling - do not incur repeated reactor stabilization.
        reacquire=True marks QC-triggered re-measurements in the accounting."""
        z = np.asarray(z_positions, dtype=float)
        if np.any(z < 0.0) or np.any(z > self.length_m + 1e-12):
            raise ValueError("Sampling position outside the reactor.")
        self.meter.log_condition(u.T_C, u.Q1_mL_min + u.Q2_mL_min,
                                 u.C_EGDA_M, u.C_cat_M)
        if self._last_u is None or u != self._last_u:
            self._transfer.reset()          # new condition: line re-primed
        self._last_u = u

        truths = self._true_profile(u, z)
        propagate = self._propagator(u, self._transfer.cfg.T_line_C)
        n_s, n_z = len(self.species), len(z)
        y = np.zeros(n_s * n_z)
        cov = np.zeros((n_s * n_z, n_s * n_z))
        qc: List[Dict] = []
        spectra: List[Tuple[np.ndarray, np.ndarray]] = []

        for k, (z_k, conc_true) in enumerate(zip(z, truths)):
            seen = self._transfer.sample(conc_true, float(z_k), propagate)
            self.meter.log_acquisition(float(z_k), u.T_C,
                                       u.Q1_mL_min + u.Q2_mL_min,
                                       u.C_EGDA_M, u.C_cat_M,
                                       retry=reacquire)
            self.n_acquisitions += 1
            if self.config.observation_mode == "direct":
                est, cov_k, meta_k = self._observe_direct(seen)
            else:
                est, cov_k, meta_k, spec = self._observe_nmr(seen)
                if self.config.store_spectra:
                    spectra.append(spec)
            for i in range(n_s):
                y[i * n_z + k] = est[i]
                for j in range(n_s):
                    cov[i * n_z + k, j * n_z + k] = cov_k[i, j]
            meta_k["z_m"] = float(z_k)
            qc.append(meta_k)

        self.n_experiments_run += 1
        meta = {"qc": qc, "observation_mode": self.config.observation_mode,
                "nmr_mode": self.config.nmr_mode}
        if spectra:
            meta["spectra"] = spectra
        cov_y = None if self.config.observation_mode == "direct" else cov
        return Measurement(u=u, z_m=z.copy(), species=self.species, y=y,
                           cov_y=cov_y, meta=meta)

    # ------------------------------------------------------------------ #
    def _observe_direct(self, seen: Dict[str, float]):
        """Legacy-style observation: concentrations + NoiseModel noise.
        cov_y stays None so InferenceModel applies its assumed NoiseModel -
        identical to sdl.truth.VirtualLaboratory."""
        clean = np.array([seen[sp] for sp in self.species])
        if self.calibration_gain:
            clean = clean * np.array([self.calibration_gain.get(sp, 1.0)
                                      for sp in self.species])
        cov = self._noise_direct.covariance(clean, self.species, 1)
        noise = (np.linalg.cholesky(cov)
                 @ self._rng.standard_normal(len(clean))
                 if np.any(np.diag(cov) > 0.0) else np.zeros(len(clean)))
        return clean + noise, cov, {"mode": "direct"}

    def _observe_nmr(self, seen: Dict[str, float]):
        """Spectrum -> deconvolution.  The fitter sees only the spectrum."""
        ppm, spec, _rl = self._nmr.simulate(seen, self._rng)
        res = self._fitter.fit(ppm, spec)
        est = np.array([res.conc_M[list(res.species).index(sp)]
                        for sp in self.species])
        meta = {"mode": "nmr", "qc_flags": list(res.qc_flags),
                "censored": list(res.censored),
                "residual_rms": res.residual_rms,
                "condition_number": res.condition_number,
                "corr_EGDA_EGMA": float(
                    res.corr[list(res.species).index("EGDA"),
                             list(res.species).index("EGMA")])
                if {"EGDA", "EGMA"} <= set(res.species) else 0.0,
                "eta": dict(res.eta)}
        return est, res.cov, meta, (ppm, spec, res.fitted)

    # ------------------------------------------------------------------ #
    def reveal_truth(self) -> Dict[str, float]:
        """POST-CAMPAIGN benchmarking only."""
        self.n_truth_reveals += 1
        return dict(self._theta_true)
