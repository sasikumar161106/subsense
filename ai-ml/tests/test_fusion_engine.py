"""
Unit tests for SubSense Multi-Source Evidence Fusion Decision Engine.
Guarantees 100% branch coverage across all decision table rows, life-safety overrides,
and pre-resolved ADR-005 logic.
"""

from datetime import datetime, timezone
import pytest

from fusion.schemas import AlertTier, FusionInputSignals
from fusion.decision_engine import FusionDecisionEngine
from fusion.confidence import ConfidenceScorer


@pytest.fixture
def base_signals():
    """Returns baseline normal signals."""
    return FusionInputSignals(
        node_id="NODE-TEST-001",
        timestamp=datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc),
        zone_id="Zone 3B",
        panel_id="Panel 7",
        s_node=0.20,
        isoforest_score=0.22,
        ae_reconstruction_error=0.03,
        concordant_channel_count=1,
        is_single_sensor_uncorroborated=False,
        c_corr=0.15,
        c_corr_distance_m=45.0,
        q_mesh=0.98,
        instantaneous_delta_disp_mm=0.2,
        instantaneous_tilt_surge_deg=0.01,
        contributing_sensors=["displacement_mm"],
        r_gnn=0.25,
        lstm_regime="STABLE",
        lstm_velocity_mm_h=0.02,
        lstm_accel_mm_h2=0.003,
        ttc_median_hours=48.0,
        gat_neighbor_attentions={"NODE-TEST-002": 0.40},
        corroborating_node_ids=["NODE-TEST-002"],
        insar_displacement_mm=2.0,
    )


class TestFusionEngineBranchCoverage:
    """
    Tests every individual branch and decision rule in FusionDecisionEngine.
    """

    def test_normal_operation_fires_none_tier(self, base_signals):
        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.NONE
        assert result.audit_level == 0
        assert "ROUTINE_MONITORING" in result.actions

    def test_advisory_tier_fires_on_isolated_drift(self, base_signals):
        # ADVISORY: S_node > 0.65; uncorroborated; LSTM stable; confidence < 0.60
        base_signals.s_node = 0.68
        base_signals.is_single_sensor_uncorroborated = True
        base_signals.concordant_channel_count = 1
        base_signals.lstm_regime = "STABLE"
        base_signals.isoforest_score = 0.68
        base_signals.r_gnn = 0.20
        base_signals.c_corr = 0.10
        base_signals.q_mesh = 0.50

        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.ADVISORY
        assert result.audit_level == 1
        assert "DASHBOARD_NOTICE" in result.actions
        assert "NODE_HEALTH_PING" in result.actions
        assert result.confidence < 0.60

    def test_advisory_suppressed_if_confidence_too_high(self, base_signals):
        # If confidence >= 0.60, it's not a low-confidence uncorroborated advisory
        base_signals.s_node = 0.68
        base_signals.is_single_sensor_uncorroborated = True
        base_signals.concordant_channel_count = 1
        base_signals.lstm_regime = "STABLE"
        # Artificially force high confidence
        scorer = ConfidenceScorer()
        scorer.score = lambda **kwargs: type('obj', (object,), {
            'confidence': 0.75, 'model_agreement': 0.8, 'c_corr': 0.8, 'q_mesh': 0.9
        })()
        engine = FusionDecisionEngine(confidence_scorer=scorer)
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.NONE

    def test_warning_tier_fires_on_multi_channel_concordance(self, base_signals):
        # WARNING: S_node >= 0.75 across >=2 channels; C_corr >= 0.70 (<=120m); R_GNN >= 0.70; LSTM = Sustained
        base_signals.s_node = 0.78
        base_signals.concordant_channel_count = 2
        base_signals.c_corr = 0.75
        base_signals.c_corr_distance_m = 95.0
        base_signals.r_gnn = 0.72
        base_signals.lstm_regime = "SUSTAINED"
        base_signals.ttc_median_hours = 24.0  # Safe (>12h)

        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.WARNING
        assert result.audit_level == 2
        assert "SMS_TELEGRAM_GEOTECHNICAL_MANAGER" in result.actions
        assert "INSPECTION_DISPATCH" in result.actions

    def test_warning_tier_fails_if_any_single_condition_missing(self, base_signals):
        engine = FusionDecisionEngine()

        # Missing concordant channel (only 1)
        base_signals.s_node = 0.80
        base_signals.concordant_channel_count = 1
        base_signals.c_corr = 0.75
        base_signals.c_corr_distance_m = 50.0
        base_signals.r_gnn = 0.75
        base_signals.lstm_regime = "SUSTAINED"
        base_signals.ttc_median_hours = 24.0
        assert engine.evaluate(base_signals).tier != AlertTier.WARNING

        # Distance > 120m
        base_signals.concordant_channel_count = 2
        base_signals.c_corr_distance_m = 135.0
        assert engine.evaluate(base_signals).tier != AlertTier.WARNING

        # C_corr < 0.70
        base_signals.c_corr_distance_m = 80.0
        base_signals.c_corr = 0.65
        assert engine.evaluate(base_signals).tier != AlertTier.WARNING

        # R_GNN < 0.70
        base_signals.c_corr = 0.75
        base_signals.r_gnn = 0.62
        assert engine.evaluate(base_signals).tier != AlertTier.WARNING

        # LSTM not SUSTAINED
        base_signals.r_gnn = 0.75
        base_signals.lstm_regime = "STABLE"
        assert engine.evaluate(base_signals).tier != AlertTier.WARNING

    def test_critical_branch_c1_warning_plus_ttc12h_plus_rapid_accel(self, base_signals):
        # Warning conditions + TTC <= 12h + rapid LSTM acceleration
        base_signals.s_node = 0.78
        base_signals.concordant_channel_count = 2
        base_signals.c_corr = 0.75
        base_signals.c_corr_distance_m = 95.0
        base_signals.r_gnn = 0.72
        base_signals.lstm_regime = "SUSTAINED"
        base_signals.ttc_median_hours = 11.5  # <= 12h
        base_signals.lstm_accel_mm_h2 = 0.065  # >= 0.050 (rapid accel)

        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.CRITICAL
        assert result.audit_level == 3
        assert "AUTOMATED_SIRENS" in result.actions
        assert "CONVEYOR_CUTOFF" in result.actions
        assert "ZONE_EVACUATION" in result.actions
        assert "CRITICAL_BRANCH_C1_WARNING_PLUS_TTC12H_PLUS_RAPID_ACCEL" in result.evidence_attribution.triggered_rules

    def test_critical_branch_c2_hard_override_ttc_less_than_8h(self, base_signals):
        # Pre-resolved ADR-005: TTC < 8h on its own triggers CRITICAL unconditionally
        # even if single sensor, low c_corr, stable LSTM
        base_signals.s_node = 0.30
        base_signals.concordant_channel_count = 1
        base_signals.c_corr = 0.10
        base_signals.r_gnn = 0.15
        base_signals.lstm_regime = "STABLE"
        base_signals.ttc_median_hours = 6.8  # < 8h override

        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.CRITICAL
        assert result.audit_level == 3
        assert "AUTOMATED_SIRENS" in result.actions
        assert "CRITICAL_BRANCH_C2_TTC_LESS_THAN_8H_OVERRIDE" in result.evidence_attribution.triggered_rules

    def test_critical_branch_c3_instantaneous_displacement_spike(self, base_signals):
        # Instantaneous delta_disp > 10mm triggers CRITICAL unconditionally
        base_signals.s_node = 0.25
        base_signals.ttc_median_hours = 36.0
        base_signals.instantaneous_delta_disp_mm = 11.8  # > 10mm

        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.CRITICAL
        assert result.audit_level == 3
        assert "AUTOMATED_SIRENS" in result.actions
        assert "CRITICAL_BRANCH_C3_INSTANTANEOUS_DISPLACEMENT_EXCEEDANCE" in result.evidence_attribution.triggered_rules

    def test_fallback_summary_without_deltas_or_neighbors_or_insar(self, base_signals):
        # Exercises fallback summary branches where deltas are 0, neighbors are empty, insar is None
        base_signals.ttc_median_hours = 5.0  # triggers CRITICAL via C2
        base_signals.instantaneous_tilt_surge_deg = 0.0
        base_signals.instantaneous_delta_disp_mm = 0.0
        base_signals.corroborating_node_ids = []
        base_signals.insar_displacement_mm = None

        engine = FusionDecisionEngine()
        result = engine.evaluate(base_signals)
        assert result.tier == AlertTier.CRITICAL
        assert "S_node=" in result.plain_language_summary
        assert "Uncorroborated single-sensor anomaly" in result.plain_language_summary
        assert "InSAR satellite data currently unavailable" in result.plain_language_summary

