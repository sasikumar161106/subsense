"""
Feature engineering constants and definitions.
Implements ADR-001 (FEATURE_VECTOR_DIM = 12).
"""

from typing import List

# Pre-resolved decision: 11 engineered features + 1 raw pass-through crack_index = 12 dimensions
FEATURE_VECTOR_DIM: int = 12

FEATURE_NAMES: List[str] = [
    # Kinematic Deformation (5)
    "tilt_mean",
    "tilt_std",
    "tilt_slope_dt",
    "disp_max",
    "disp_rate_mm_h",
    # Seismic / Vibration Energy (3)
    "vib_rms_max",
    "vib_spectral_energy_10_50hz",
    "crest_factor",
    # Spatial Topology Context (3)
    "nearest_neighbor_dist_m",
    "dist_to_goaf_edge_m",
    "pillar_stress_index",
    # Pass-through 12th feature (ADR-001)
    "crack_index",
]

SENSOR_ATTRIBUTION_MAPPING = {
    "tilt_mean": "tilt_deg",
    "tilt_std": "tilt_deg",
    "tilt_slope_dt": "tilt_deg",
    "disp_max": "displacement_mm",
    "disp_rate_mm_h": "displacement_mm",
    "vib_rms_max": "vibration_rms_mm_s",
    "vib_spectral_energy_10_50hz": "vibration_rms_mm_s",
    "crest_factor": "vibration_rms_mm_s",
    "nearest_neighbor_dist_m": "spatial_topology",
    "dist_to_goaf_edge_m": "spatial_topology",
    "pillar_stress_index": "spatial_topology",
    "crack_index": "crack_index",
}
