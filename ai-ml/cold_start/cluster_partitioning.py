"""
Panel-Cluster Model Partitioning & Geological Assignment Engine.
Partitions models by coalfield geotechnical strata characteristics rather than a single universal model.
Provides deterministic assignment rules based on RMR, UCS, Overburden Depth, and Seam Thickness.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np

from .bootstrap_pipeline import PanelGeologicalProperties


class GeologicalCluster(str, Enum):
    CLUSTER_1_COMPACT_SANDSTONE = "CLUSTER_1_COMPACT_SANDSTONE"
    CLUSTER_2_WEAK_SHALE = "CLUSTER_2_WEAK_SHALE"
    CLUSTER_3_DEEP_HIGH_STRESS = "CLUSTER_3_DEEP_HIGH_STRESS"
    CLUSTER_4_INTERMEDIATE_MIXED = "CLUSTER_4_INTERMEDIATE_MIXED"


@dataclass
class ClusterAssignmentResult:
    panel_id: str
    assigned_cluster: GeologicalCluster
    coalfield_archetype: str
    governing_criteria: List[str]
    cluster_hyperparameters: Dict[str, float]


# Geotechnical parameter centroids for Mahalanobis / Euclidean proximity
CLUSTER_CENTROIDS = {
    GeologicalCluster.CLUSTER_1_COMPACT_SANDSTONE: {
        "rmr": 70.0, "ucs_mpa": 65.0, "depth_m": 180.0, "seam_m": 3.0,
        "archetype": "Jharia / Raniganj Massive Hard Sandstone (Brittle Caving)",
        "hyperparameters": {
            "theta_vel_mm_h": 0.20,
            "theta_accel_mm_h2": 0.040,
            "alpha": 0.60,
            "beta": 14.0,
        }
    },
    GeologicalCluster.CLUSTER_2_WEAK_SHALE: {
        "rmr": 40.0, "ucs_mpa": 25.0, "depth_m": 150.0, "seam_m": 4.5,
        "archetype": "Singareni / Talcher Friable Weak Shale (Ductile Creep)",
        "hyperparameters": {
            "theta_vel_mm_h": 0.35,
            "theta_accel_mm_h2": 0.065,
            "alpha": 0.50,
            "beta": 10.0,
        }
    },
    GeologicalCluster.CLUSTER_3_DEEP_HIGH_STRESS: {
        "rmr": 55.0, "ucs_mpa": 45.0, "depth_m": 350.0, "seam_m": 2.5,
        "archetype": "Deep Longwall High In-Situ Lithostatic Stress (>280m)",
        "hyperparameters": {
            "theta_vel_mm_h": 0.25,
            "theta_accel_mm_h2": 0.045,
            "alpha": 0.55,
            "beta": 13.0,
        }
    },
    GeologicalCluster.CLUSTER_4_INTERMEDIATE_MIXED: {
        "rmr": 52.0, "ucs_mpa": 40.0, "depth_m": 210.0, "seam_m": 3.5,
        "archetype": "Gondwana Interbedded Sandstone-Shale Sequence",
        "hyperparameters": {
            "theta_vel_mm_h": 0.25,
            "theta_accel_mm_h2": 0.050,
            "alpha": 0.55,
            "beta": 12.5,
        }
    },
}


class GeologicalClusterAssigner:
    """
    Assigns newly opened mining panels to geological model clusters.
    Uses deterministic priority rules backed by normalized geotechnical distance.
    """

    def assign_panel(self, props: PanelGeologicalProperties) -> ClusterAssignmentResult:
        """
        Deterministic Assignment Rule Hierarchy:
        1. Rule 1 (Deep High Stress): Overburden Depth > 280.0m -> CLUSTER_3_DEEP_HIGH_STRESS
        2. Rule 2 (Compact Sandstone): RMR >= 60.0 AND UCS >= 50.0 MPa -> CLUSTER_1_COMPACT_SANDSTONE
        3. Rule 3 (Weak Shale): RMR < 45.0 OR UCS < 30.0 MPa -> CLUSTER_2_WEAK_SHALE
        4. Rule 4 (Default / Interbedded): Otherwise -> CLUSTER_4_INTERMEDIATE_MIXED
        """
        governing_criteria = []
        assigned_cluster: GeologicalCluster

        if props.overburden_depth_m > 280.0:
            assigned_cluster = GeologicalCluster.CLUSTER_3_DEEP_HIGH_STRESS
            governing_criteria.append(f"Overburden depth ({props.overburden_depth_m:.1f}m) exceeds 280m threshold")
        elif props.rock_mass_rating_rmr >= 60.0 and props.uniaxial_compressive_strength_ucs_mpa >= 50.0:
            assigned_cluster = GeologicalCluster.CLUSTER_1_COMPACT_SANDSTONE
            governing_criteria.append(
                f"High strata competence: RMR {props.rock_mass_rating_rmr:.1f} >= 60.0 and UCS {props.uniaxial_compressive_strength_ucs_mpa:.1f} >= 50 MPa"
            )
        elif props.rock_mass_rating_rmr < 45.0 or props.uniaxial_compressive_strength_ucs_mpa < 30.0:
            assigned_cluster = GeologicalCluster.CLUSTER_2_WEAK_SHALE
            governing_criteria.append(
                f"Weak strata competence: RMR {props.rock_mass_rating_rmr:.1f} < 45.0 or UCS {props.uniaxial_compressive_strength_ucs_mpa:.1f} < 30 MPa"
            )
        else:
            assigned_cluster = GeologicalCluster.CLUSTER_4_INTERMEDIATE_MIXED
            governing_criteria.append("Intermediate strata competency: falls between hard sandstone and weak shale criteria")

        cluster_info = CLUSTER_CENTROIDS[assigned_cluster]

        return ClusterAssignmentResult(
            panel_id=props.panel_id,
            assigned_cluster=assigned_cluster,
            coalfield_archetype=cluster_info["archetype"],
            governing_criteria=governing_criteria,
            cluster_hyperparameters=cluster_info["hyperparameters"],
        )
