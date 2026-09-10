"""
Unit tests for SubSense Cold-Start Bootstrap and Geological Cluster Assignment.
"""

import numpy as np
import pytest

from cold_start.bootstrap_pipeline import (
    PanelGeologicalProperties,
    GeotechnicalSimulationBootstrap,
    BootstrapResult,
)
from cold_start.cluster_partitioning import (
    GeologicalCluster,
    GeologicalClusterAssigner,
    ClusterAssignmentResult,
)


class TestColdStartAndClusterPartitioning:
    def test_flac3d_bootstrap_pipeline_fits_virgin_panel(self):
        props = PanelGeologicalProperties(
            panel_id="PANEL_VIRGIN_09",
            overburden_depth_m=195.0,
            seam_thickness_m=3.2,
            rock_mass_rating_rmr=68.0,
            uniaxial_compressive_strength_ucs_mpa=55.0,
        )

        bootstrap = GeotechnicalSimulationBootstrap(random_seed=42)
        res = bootstrap.bootstrap_panel_model(props, num_samples=80, epochs=3)

        assert isinstance(res, BootstrapResult)
        assert res.synthetic_samples_generated == 80
        assert res.baseline_feature_matrix.shape == (80, 12)
        assert res.fitted_ensemble.is_fitted is True

        # Test inference on a synthetic test vector
        test_vec = res.baseline_feature_matrix[0]
        inf = res.fitted_ensemble.predict(test_vec)
        assert 0.0 <= inf.anomaly_score <= 1.0

    def test_cluster_assignment_rule_deep_high_stress(self):
        assigner = GeologicalClusterAssigner()
        props = PanelGeologicalProperties(
            panel_id="DEEP_LONGWALL_01",
            overburden_depth_m=320.0,  # > 280m
            seam_thickness_m=2.5,
            rock_mass_rating_rmr=65.0,
            uniaxial_compressive_strength_ucs_mpa=60.0,
        )
        res = assigner.assign_panel(props)
        assert res.assigned_cluster == GeologicalCluster.CLUSTER_3_DEEP_HIGH_STRESS

    def test_cluster_assignment_rule_compact_sandstone(self):
        assigner = GeologicalClusterAssigner()
        props = PanelGeologicalProperties(
            panel_id="JHARIA_SEAM7",
            overburden_depth_m=180.0,  # <= 280m
            seam_thickness_m=3.0,
            rock_mass_rating_rmr=68.0,  # >= 60
            uniaxial_compressive_strength_ucs_mpa=62.0,  # >= 50
        )
        res = assigner.assign_panel(props)
        assert res.assigned_cluster == GeologicalCluster.CLUSTER_1_COMPACT_SANDSTONE

    def test_cluster_assignment_rule_weak_shale(self):
        assigner = GeologicalClusterAssigner()
        props = PanelGeologicalProperties(
            panel_id="SINGARENI_SHALE_04",
            overburden_depth_m=140.0,
            seam_thickness_m=4.5,
            rock_mass_rating_rmr=38.0,  # < 45
            uniaxial_compressive_strength_ucs_mpa=22.0,  # < 30
        )
        res = assigner.assign_panel(props)
        assert res.assigned_cluster == GeologicalCluster.CLUSTER_2_WEAK_SHALE

    def test_cluster_assignment_rule_intermediate_mixed(self):
        assigner = GeologicalClusterAssigner()
        props = PanelGeologicalProperties(
            panel_id="GONDWANA_MIXED_02",
            overburden_depth_m=210.0,
            seam_thickness_m=3.5,
            rock_mass_rating_rmr=52.0,  # Intermediate
            uniaxial_compressive_strength_ucs_mpa=42.0,  # Intermediate
        )
        res = assigner.assign_panel(props)
        assert res.assigned_cluster == GeologicalCluster.CLUSTER_4_INTERMEDIATE_MIXED
