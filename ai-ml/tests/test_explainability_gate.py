"""
Unit tests for SubSense Explainability Layer and Regulatory Validation Gate.
Proves:
1. TreeSHAP feature attributions on tabular MineIsolationForest.
2. Top-k GAT attention edge extraction.
3. Geotechnical Natural-Language summary conformity.
4. Schema validation gate strictly REJECTS non-compliant alerts missing attribution fields.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from models.anomaly.isoforest import MineIsolationForest
from gnn.gatv2_model import GNNInferenceResult
from fusion.schemas import AlertTier
from explainability.shap_explainer import TreeShapExplainer, ShapExplanationResult
from explainability.attention_extractor import GATAttentionExtractor
from explainability.summary_generator import GeotechnicalSummaryGenerator
from explainability.alert_schema import (
    ValidatedAlertEvent,
    IncompleteExplainabilityAlertError,
    validate_and_gate_alert,
)


class TestExplainabilityAndValidationGate:
    def test_treeshap_feature_attribution(self):
        # Fit baseline Isolation Forest on synthetic normal vectors
        rng = np.random.default_rng(42)
        X_train = rng.normal(0.0, 1.0, (60, 12)).astype(np.float32)
        isoforest = MineIsolationForest(n_estimators=10, max_samples=0.8)
        isoforest.fit(X_train)

        explainer = TreeShapExplainer(isoforest)
        test_vec = rng.normal(2.5, 0.5, 12).astype(np.float32)

        res = explainer.explain(test_vec, top_k=3)
        assert isinstance(res, ShapExplanationResult)
        assert len(res.feature_attributions) == 12
        assert len(res.contributing_sensors) > 0
        assert all(isinstance(s, str) and len(s) > 0 for s in res.contributing_sensors)

    def test_gat_attention_edge_extraction(self):
        # Synthetic GNN result with 3 nodes and 4 edges
        node_ids = ["NODE_01", "NODE_02", "NODE_03"]
        edge_index = np.array([
            [0, 1, 0, 2],  # src
            [1, 0, 2, 0],  # dst
        ])
        att_weights = np.array([0.88, 0.88, 0.65, 0.65])
        layer_atts = [att_weights, att_weights, att_weights]

        gnn_result = GNNInferenceResult(
            risk_scores=np.array([0.85, 0.75, 0.40]),
            edge_index=edge_index,
            attention_weights=att_weights,
            layer_attentions=layer_atts,
            node_ids=node_ids,
            num_nodes=3,
            num_edges=4,
        )

        extractor = GATAttentionExtractor(default_top_k=2)
        att_summary = extractor.extract_top_k_attentions(gnn_result, target_node_id="NODE_01")

        assert att_summary.node_id == "NODE_01"
        assert len(att_summary.corroborating_neighbor_ids) == 2
        assert "NODE_02" in att_summary.corroborating_neighbor_ids
        assert att_summary.max_attention_alpha == 0.88

    def test_geotechnical_natural_language_summary_structure(self):
        generator = GeotechnicalSummaryGenerator()
        summary = generator.generate(
            tier=AlertTier.CRITICAL,
            zone_id="Zone 3B",
            panel_id="Panel 7",
            node_id="SS-PANEL7-N042",
            trigger_deltas_str="sustained tilt surge (+0.24° over 30 min) and differential displacement (+4.8 mm/hr)",
            corroborating_nodes=["N041", "N044"],
            attention_alpha=0.88,
            structural_feature="active extraction face",
            insar_displacement_mm=12.0,
        )

        assert summary.startswith("CRITICAL WARNING (Zone 3B, Panel 7):")
        assert "Node SS-PANEL7-N042" in summary
        assert "sustained tilt surge" in summary
        assert "differential displacement" in summary
        assert "α=0.88" in summary
        assert "adjacent nodes N041 and N044" in summary
        assert "active extraction face" in summary
        assert "InSAR macro-crosscheck confirms 12mm historical depression basin." in summary

    def test_compliant_alert_passes_gate(self):
        valid_payload = {
            "alert_id": "ALERT-20260909-001",
            "node_id": "NODE_01",
            "timestamp": datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
            "tier": AlertTier.WARNING,
            "confidence": 0.82,
            "contributing_sensors": ["displacement_mm", "tilt_deg"],
            "corroborating_node_ids": ["NODE_02", "NODE_03"],
            "plain_language_summary": "WARNING (Zone 3B, Panel 7): Triggered by differential displacement (+3.2 mm/hr) at Node NODE_01. Corroborated by high spatial attention (α=0.85).",
        }

        event = validate_and_gate_alert(valid_payload)
        assert isinstance(event, ValidatedAlertEvent)
        assert event.node_id == "NODE_01"

    def test_alert_missing_contributing_sensors_is_rejected(self):
        invalid_payload = {
            "alert_id": "ALERT-20260909-002",
            "node_id": "NODE_01",
            "timestamp": datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
            "tier": AlertTier.WARNING,
            "confidence": 0.82,
            "contributing_sensors": [],  # EMPTY - VIOLATION
            "corroborating_node_ids": ["NODE_02"],
            "plain_language_summary": "WARNING (Zone 3B, Panel 7): Triggered at Node NODE_01.",
        }

        with pytest.raises(IncompleteExplainabilityAlertError) as exc_info:
            validate_and_gate_alert(invalid_payload)
        assert "contributing_sensors" in str(exc_info.value)

    def test_alert_missing_corroborating_nodes_is_rejected(self):
        invalid_payload = {
            "alert_id": "ALERT-20260909-003",
            "node_id": "NODE_01",
            "timestamp": datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
            "tier": AlertTier.CRITICAL,
            "confidence": 0.95,
            "contributing_sensors": ["displacement_mm"],
            "corroborating_node_ids": [],  # EMPTY - VIOLATION
            "plain_language_summary": "CRITICAL WARNING (Zone 3B, Panel 7): Triggered at Node NODE_01.",
        }

        with pytest.raises(IncompleteExplainabilityAlertError) as exc_info:
            validate_and_gate_alert(invalid_payload)
        assert "corroborating_node_ids" in str(exc_info.value)

    def test_alert_missing_plain_language_summary_is_rejected(self):
        invalid_payload = {
            "alert_id": "ALERT-20260909-004",
            "node_id": "NODE_01",
            "timestamp": datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
            "tier": AlertTier.CRITICAL,
            "confidence": 0.95,
            "contributing_sensors": ["displacement_mm"],
            "corroborating_node_ids": ["NODE_02"],
            "plain_language_summary": "",  # BLANK - VIOLATION
        }

        with pytest.raises(IncompleteExplainabilityAlertError) as exc_info:
            validate_and_gate_alert(invalid_payload)
        assert "plain_language_summary" in str(exc_info.value)
