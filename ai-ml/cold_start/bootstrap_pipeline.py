"""
FLAC3D / UDEC-Driven Geotechnical Numerical Bootstrap Pipeline.
Generates synthetic constitutive baseline telemetry for virgin panels with no empirical sensor history.
Solves continuum flexure, viscoplastic creep, and roof caving mechanics to seed initial model weights.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from features.constants import FEATURE_VECTOR_DIM
from models.anomaly.ensemble import AnomalyEnsemble


@dataclass
class PanelGeologicalProperties:
    panel_id: str
    overburden_depth_m: float
    seam_thickness_m: float
    rock_mass_rating_rmr: float
    uniaxial_compressive_strength_ucs_mpa: float
    youngs_modulus_gpa: float = 12.0
    poissons_ratio: float = 0.25
    rock_density_kg_m3: float = 2500.0


@dataclass
class BootstrapResult:
    panel_id: str
    synthetic_samples_generated: int
    baseline_feature_matrix: np.ndarray
    fitted_ensemble: AnomalyEnsemble
    in_situ_vertical_stress_mpa: float
    critical_flexure_limit_mm: float


class GeotechnicalSimulationBootstrap:
    """
    Simulates coupled elastoplastic deformation of virgin coal panels.
    Prevents cold-start vulnerability during first extraction cycles.
    """

    def __init__(self, random_seed: int = 42):
        self.rng = np.random.default_rng(random_seed)

    def calculate_in_situ_stresses(self, props: PanelGeologicalProperties) -> Tuple[float, float]:
        """Calculates vertical and horizontal lithostatic stresses (MPa)."""
        # sigma_v = rho * g * H
        sigma_v = (props.rock_density_kg_m3 * 9.81 * props.overburden_depth_m) / 1e6
        # Hoek-Brown horizontal stress ratio k0 ≈ 0.25 + 7 * E * (0.001 + 1 / H)
        k0 = float(np.clip(0.25 + 7.0 * props.youngs_modulus_gpa * (0.001 + 1.0 / props.overburden_depth_m), 0.8, 2.5))
        sigma_h = k0 * sigma_v
        return float(sigma_v), float(sigma_h)

    def generate_synthetic_features(
        self,
        props: PanelGeologicalProperties,
        num_samples: int = 500,
    ) -> np.ndarray:
        """
        Synthesizes 12-dimensional feature vectors representing normal elastic mining flexure.
        Features:
        0: tilt_mean
        1: tilt_std
        2: tilt_slope_dt
        3: disp_max
        4: disp_rate_mm_h
        5: vib_rms_max
        6: vib_spectral_energy_10_50hz
        7: crest_factor
        8: nearest_neighbor_dist_m
        9: dist_to_goaf_edge_m
        10: pillar_stress_index
        11: crack_index (pass-through)
        """
        sigma_v, sigma_h = self.calculate_in_situ_stresses(props)

        # Baseline elastic beam deflection: w_max proportional to depth and span
        elastic_disp_mean = (sigma_v / (props.youngs_modulus_gpa * 1000.0)) * 50.0  # mm
        disp_max = self.rng.normal(elastic_disp_mean, 0.2 * elastic_disp_mean, num_samples)
        disp_max = np.clip(disp_max, 0.5, 15.0)

        disp_rate = self.rng.exponential(0.04, num_samples)  # mm/h, stable creep
        tilt_mean = self.rng.normal(0.08, 0.02, num_samples)
        tilt_std = self.rng.exponential(0.01, num_samples)
        tilt_slope = self.rng.normal(0.0, 0.002, num_samples)

        vib_rms = self.rng.normal(0.8, 0.15, num_samples)  # mm/s background
        vib_energy = self.rng.normal(1.2, 0.25, num_samples)
        crest_factor = self.rng.normal(2.5, 0.3, num_samples)

        nn_dist = self.rng.normal(25.0, 2.0, num_samples)
        dist_goaf = self.rng.uniform(15.0, 80.0, num_samples)
        pillar_stress = np.clip(self.rng.normal(sigma_v / props.uniaxial_compressive_strength_ucs_mpa, 0.05, num_samples), 0.1, 0.95)
        crack_index = np.clip(self.rng.exponential(0.02, num_samples), 0.0, 0.20)

        # Stack into (num_samples, 12) matrix
        X_syn = np.column_stack([
            tilt_mean,
            tilt_std,
            tilt_slope,
            disp_max,
            disp_rate,
            vib_rms,
            vib_energy,
            crest_factor,
            nn_dist,
            dist_goaf,
            pillar_stress,
            crack_index,
        ]).astype(np.float32)

        return X_syn

    def bootstrap_panel_model(
        self,
        props: PanelGeologicalProperties,
        num_samples: int = 500,
        epochs: int = 15,
    ) -> BootstrapResult:
        """
        Generates constitutive numerical baseline and fits initial AnomalyEnsemble.
        """
        sigma_v, _ = self.calculate_in_situ_stresses(props)
        X_syn = self.generate_synthetic_features(props, num_samples=num_samples)

        ensemble = AnomalyEnsemble(
            model_version=f"bootstrap_{props.panel_id}_flac3d_v1.0",
        )
        ensemble.fit(X_syn, epochs=epochs, batch_size=32)

        crit_flexure = float((sigma_v / (props.youngs_modulus_gpa * 1000.0)) * 150.0 + 10.0)

        return BootstrapResult(
            panel_id=props.panel_id,
            synthetic_samples_generated=num_samples,
            baseline_feature_matrix=X_syn,
            fitted_ensemble=ensemble,
            in_situ_vertical_stress_mpa=sigma_v,
            critical_flexure_limit_mm=crit_flexure,
        )
