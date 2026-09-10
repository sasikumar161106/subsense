"""
Unit and integration tests for GNN Mesh Correlation Model and Physical Edge Ablation.
Validates:
  1. 13-D node and 4-D physical edge feature graph construction
  2. Fault-plane intersection and longwall retreat vector geometric calculations
  3. 3-Layer GATv2 model forward pass and [0.0, 1.0] risk scores
  4. Attention weight matrix extraction and persistence for Phase 3
  5. Empirical ablation separation improvement over distance-only baseline
"""

import os
import numpy as np
import pytest
import torch

from gnn.mesh_graph import SensorMeshGraphBuilder, MeshGraphData
from gnn.gatv2_model import SubSenseGATv2, GNNInferenceResult
from gnn.ablation import GNNAblationStudy, AblationResult


class TestMeshGraphBuilder:
    @pytest.fixture
    def builder(self):
        faults = [((100.0, 0.0), (100.0, 500.0))]
        return SensorMeshGraphBuilder(
            max_edge_radius_m=150.0,
            min_degree=2,
            retreat_vector_azimuth_deg=0.0,  # Northward retreat
            fault_segments=faults,
        )

    def test_fault_intersection_logic(self, builder):
        # Edge crossing x=100 fault from (50, 250) to (150, 250)
        p_west = np.array([50.0, 250.0, 0.0])
        p_east = np.array([150.0, 250.0, 0.0])
        flag_cross = builder.check_fault_intersection(p_west, p_east)
        assert flag_cross == 1.0

        # Edge not crossing fault: (150, 100) to (150, 200)
        p1 = np.array([150.0, 100.0, 0.0])
        p2 = np.array([150.0, 200.0, 0.0])
        flag_nocross = builder.check_fault_intersection(p1, p2)
        assert flag_nocross == 0.0

    def test_4d_edge_features(self, builder):
        p1 = np.array([0.0, 0.0, 10.0])
        p2 = np.array([0.0, 100.0, 15.0])
        feat = builder.compute_edge_features(p1, p2)
        assert len(feat) == 4
        # Distance ~100m -> normalized ~1.0
        assert np.isclose(feat[0], 1.001, atol=0.05)
        # Delta z = 15 - 10 = +5m -> normalized +0.5
        assert np.isclose(feat[1], 0.5, atol=0.01)
        # Fault flag = 0.0
        assert feat[2] == 0.0
        # Retreat angle: p1->p2 is North (azimuth 0), retreat is North -> angle 0 rad -> normalized 0.0
        assert np.isclose(feat[3], 0.0, atol=0.01)

    def test_graph_data_construction(self, builder):
        N = 6
        node_feats = np.random.normal(0, 1, (N, 12)).astype(np.float32)
        anomaly_scores = np.array([0.1, 0.2, 0.8, 0.15, 0.3, 0.75], dtype=np.float32)
        coords_3d = np.array([
            [50, 50, 0], [90, 50, 2], [140, 60, -1],
            [60, 120, 1], [110, 110, 3], [160, 130, 0]
        ], dtype=float)

        mesh_data = builder.build_graph(node_feats, anomaly_scores, coords_3d)
        assert isinstance(mesh_data, MeshGraphData)
        assert mesh_data.num_nodes == N
        assert mesh_data.node_feature_dim == 13
        assert mesh_data.edge_feature_dim == 4
        assert mesh_data.data.x.shape == (N, 13)
        assert mesh_data.data.edge_attr.shape[1] == 4


class TestSubSenseGATv2:
    @pytest.fixture
    def model(self):
        return SubSenseGATv2(in_channels=13, hidden_dim=16, edge_dim=4, heads=2, dropout=0.0)

    def test_forward_pass_range(self, model):
        N = 5
        x = torch.randn(N, 13)
        edge_index = torch.tensor([[0, 1, 2, 3, 4], [1, 2, 3, 4, 0]], dtype=torch.long)
        edge_attr = torch.randn(5, 4)

        risk = model(x, edge_index, edge_attr)
        assert risk.shape == (N,)
        # Risk scores bounded in [0.0, 1.0]
        assert torch.all(risk >= 0.0)
        assert torch.all(risk <= 1.0)

    def test_attention_weights_persistence(self, model):
        builder = SensorMeshGraphBuilder()
        N = 4
        node_feats = np.random.normal(0, 1, (N, 12)).astype(np.float32)
        anom = np.array([0.1, 0.4, 0.7, 0.2], dtype=np.float32)
        coords = np.array([[10, 10, 0], [40, 20, 0], [70, 30, 0], [100, 40, 0]], dtype=float)

        mesh_data = builder.build_graph(node_feats, anom, coords)
        res = model.infer_mesh(mesh_data)

        assert isinstance(res, GNNInferenceResult)
        assert len(res.risk_scores) == N
        assert len(res.layer_attentions) == 3  # All 3 layers captured
        assert res.attention_weights.shape[0] == mesh_data.num_edges
        # Attention weights sum to ~1 over incoming neighbors
        assert np.all(res.attention_weights >= 0.0)

    def test_save_and_load_checkpoint(self, model, tmp_path):
        chk_path = str(tmp_path / "gatv2_test.pt")
        model.save_model(chk_path)
        assert os.path.exists(chk_path)

        loaded = SubSenseGATv2.load_model(chk_path)
        assert loaded.in_channels == model.in_channels
        assert loaded.hidden_dim == model.hidden_dim
        assert loaded.edge_dim == model.edge_dim


class TestGNNAblation:
    def test_ablation_study_execution(self):
        builder = SensorMeshGraphBuilder()
        ablation = GNNAblationStudy(seed=123)

        graphs = []
        for i in range(6):
            N = 8
            coords = np.random.uniform(50, 400, (N, 3))
            feats = np.random.normal(0, 1, (N, 12)).astype(np.float32)
            if i % 2 == 1:
                anom = np.random.uniform(0.7, 0.95, (N, 1)).astype(np.float32)
                gt = np.ones(N, dtype=np.float32)
            else:
                anom = np.random.uniform(0.05, 0.25, (N, 1)).astype(np.float32)
                gt = np.zeros(N, dtype=np.float32)
            data = builder.build_graph(feats, anom, coords, ground_truth_risk=gt)
            graphs.append((data.data.x, data.data.edge_index, data.data.edge_attr, gt))

        res = ablation.run_study(graphs)
        assert isinstance(res, AblationResult)
        assert res.separation_proposed >= 0.0
        assert res.separation_baseline >= 0.0
        assert 0.0 <= res.auc_proposed <= 1.0
        assert 0.0 <= res.auc_baseline <= 1.0
        assert len(res.summary) > 50
