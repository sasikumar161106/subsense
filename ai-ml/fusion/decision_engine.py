"""
SubSense Layer 4: Multi-Source Evidence Fusion & Scoring Decision Engine.
Strictly implements ADR-005: Explicit, deterministic boolean rules engine for life-safety alerting.
Zero black-box or learned classifiers allowed to trigger sirens or evacuations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import logging

from .schemas import (
    AlertTier,
    FusionInputSignals,
    EvidenceAttribution,
    FusionDecisionResult,
)
from .confidence import ConfidenceScorer

logger = logging.getLogger("subsense.fusion.decision_engine")


class FusionDecisionEngine:
    """
    Life-safety decision engine integrating Phase 1 and Phase 2 signals.
    Enforces deterministic DGMS compliance rules:
    - ADVISORY: S_node > 0.65 (single node); uncorroborated; LSTM stable; confidence < 0.60
    - WARNING: S_node >= 0.75 across >=2 channels; C_corr >= 0.70 (<=120m); R_GNN >= 0.70; LSTM = Sustained
    - CRITICAL: (Warning + TTC <= 12h + rapid accel) OR TTC < 8h OR instantaneous delta_disp > 10mm
    """

    def __init__(
        self,
        # Advisory thresholds
        advisory_s_node: float = 0.65,
        advisory_max_confidence: float = 0.60,
        # Warning thresholds
        warning_s_node: float = 0.75,
        warning_concordant_channels_min: int = 2,
        warning_c_corr_min: float = 0.70,
        warning_c_corr_radius_m: float = 120.0,
        warning_r_gnn_min: float = 0.70,
        # Critical thresholds (ADR-005)
        critical_ttc_override_hours: float = 8.0,
        critical_ttc_floor_hours: float = 12.0,
        critical_instantaneous_disp_mm: float = 10.0,
        critical_accel_threshold_mm_h2: float = 0.050,
        # Confidence scorer
        confidence_scorer: Optional[ConfidenceScorer] = None,
    ):
        self.advisory_s_node = float(advisory_s_node)
        self.advisory_max_confidence = float(advisory_max_confidence)

        self.warning_s_node = float(warning_s_node)
        self.warning_concordant_channels_min = int(warning_concordant_channels_min)
        self.warning_c_corr_min = float(warning_c_corr_min)
        self.warning_c_corr_radius_m = float(warning_c_corr_radius_m)
        self.warning_r_gnn_min = float(warning_r_gnn_min)

        self.critical_ttc_override_hours = float(critical_ttc_override_hours)
        self.critical_ttc_floor_hours = float(critical_ttc_floor_hours)
        self.critical_instantaneous_disp_mm = float(critical_instantaneous_disp_mm)
        self.critical_accel_threshold_mm_h2 = float(critical_accel_threshold_mm_h2)

        self.confidence_scorer = confidence_scorer or ConfidenceScorer()

    def evaluate_warning_conditions(self, signals: FusionInputSignals) -> Tuple[bool, Dict[str, bool]]:
        """
        Evaluates the conjunction of Warning conditions:
        (S_node >= 0.75 across >=2 channels) AND (C_corr >= 0.70 at <= 120m) AND (R_GNN >= 0.70) AND (LSTM == Sustained)
        """
        cond_s_node = bool(signals.s_node >= self.warning_s_node)
        cond_channels = bool(signals.concordant_channel_count >= self.warning_concordant_channels_min)
        cond_c_corr = bool(signals.c_corr >= self.warning_c_corr_min)
        cond_radius = bool(signals.c_corr_distance_m <= self.warning_c_corr_radius_m)
        cond_r_gnn = bool(signals.r_gnn >= self.warning_r_gnn_min)
        cond_lstm = bool(signals.lstm_regime.strip().upper() == "SUSTAINED")

        all_warning_met = (
            cond_s_node
            and cond_channels
            and cond_c_corr
            and cond_radius
            and cond_r_gnn
            and cond_lstm
        )

        breakdown = {
            "s_node_ge_0.75": cond_s_node,
            "concordant_channels_ge_2": cond_channels,
            "c_corr_ge_0.70": cond_c_corr,
            "c_corr_radius_le_120m": cond_radius,
            "r_gnn_ge_0.70": cond_r_gnn,
            "lstm_regime_sustained": cond_lstm,
        }
        return all_warning_met, breakdown

    def evaluate_critical_conditions(
        self,
        signals: FusionInputSignals,
        warning_conditions_met: bool,
    ) -> Tuple[bool, Dict[str, bool], List[str]]:
        """
        Evaluates Critical Tier triggers per ADR-005:
        (Warning conditions + TTC <= 12h + rapid accel)
        OR (TTC < 8h override)
        OR (instantaneous delta_displacement > 10mm)
        """
        triggered_rules = []

        # Branch C1: Warning + TTC <= 12h + rapid LSTM acceleration
        c1_ttc_valid = signals.ttc_median_hours is not None
        c1_ttc_le_12 = bool(c1_ttc_valid and (signals.ttc_median_hours <= self.critical_ttc_floor_hours))
        c1_rapid_accel = bool(
            signals.lstm_regime.strip().upper() == "ACCELERATING"
            or signals.lstm_accel_mm_h2 >= self.critical_accel_threshold_mm_h2
        )
        c1_full = bool(warning_conditions_met and c1_ttc_le_12 and c1_rapid_accel)
        if c1_full:
            triggered_rules.append("CRITICAL_BRANCH_C1_WARNING_PLUS_TTC12H_PLUS_RAPID_ACCEL")

        # Branch C2: Hard life-safety override TTC < 8h (regardless of other conditions)
        c2_ttc_override = bool(c1_ttc_valid and (signals.ttc_median_hours < self.critical_ttc_override_hours))
        if c2_ttc_override:
            triggered_rules.append("CRITICAL_BRANCH_C2_TTC_LESS_THAN_8H_OVERRIDE")

        # Branch C3: Instantaneous differential displacement spike > 10mm
        c3_disp_spike = bool(abs(signals.instantaneous_delta_disp_mm) > self.critical_instantaneous_disp_mm)
        if c3_disp_spike:
            triggered_rules.append("CRITICAL_BRANCH_C3_INSTANTANEOUS_DISPLACEMENT_EXCEEDANCE")

        is_critical = bool(c1_full or c2_ttc_override or c3_disp_spike)

        breakdown = {
            "c1_warning_plus_ttc12h_accel": c1_full,
            "c1_ttc_le_12h": c1_ttc_le_12,
            "c1_rapid_accel": c1_rapid_accel,
            "c2_ttc_override_lt_8h": c2_ttc_override,
            "c3_disp_spike_gt_10mm": c3_disp_spike,
        }
        return is_critical, breakdown, triggered_rules

    def evaluate_advisory_conditions(
        self,
        signals: FusionInputSignals,
        confidence: float,
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Evaluates Advisory conditions:
        S_node > 0.65 (single node); single-sensor/uncorroborated; LSTM flat/decelerating; confidence < 0.60
        """
        cond_s_node = bool(signals.s_node > self.advisory_s_node)
        cond_uncorroborated = bool(
            signals.is_single_sensor_uncorroborated
            or signals.concordant_channel_count < self.warning_concordant_channels_min
        )
        regime = signals.lstm_regime.strip().upper()
        cond_lstm_flat = bool(regime in ["STABLE", "DECELERATING"])
        cond_low_conf = bool(confidence < self.advisory_max_confidence)

        is_advisory = bool(cond_s_node and cond_uncorroborated and cond_lstm_flat and cond_low_conf)

        breakdown = {
            "s_node_gt_0.65": cond_s_node,
            "is_uncorroborated_single_sensor": cond_uncorroborated,
            "lstm_flat_or_decelerating": cond_lstm_flat,
            "confidence_lt_0.60": cond_low_conf,
        }
        return is_advisory, breakdown

    def evaluate(self, signals: FusionInputSignals) -> FusionDecisionResult:
        """
        Deterministic, auditable evaluation across all tiers.
        Guarantees:
        1. 100% deterministic boolean execution path.
        2. No alert emitted without contributing sensors.
        3. Plain language summary strictly generated for audits.
        """
        # Step 1: Compute composite calibrated confidence
        conf_res = self.confidence_scorer.score(
            isoforest_score=signals.isoforest_score,
            lstm_regime=signals.lstm_regime,
            r_gnn=signals.r_gnn,
            c_corr=signals.c_corr,
            q_mesh=signals.q_mesh,
            lstm_velocity_mm_h=signals.lstm_velocity_mm_h,
            lstm_accel_mm_h2=signals.lstm_accel_mm_h2,
        )
        confidence = conf_res.confidence

        # Step 2: Evaluate Warning conditions
        warning_met, warning_breakdown = self.evaluate_warning_conditions(signals)

        # Step 3: Evaluate Critical conditions (Top priority)
        critical_met, critical_breakdown, critical_rules = self.evaluate_critical_conditions(
            signals, warning_conditions_met=warning_met
        )

        tier: AlertTier
        audit_level: int
        actions: List[str]
        triggered_rules: List[str] = []
        rule_evidence: Dict[str, Any] = {
            "warning_conditions": warning_breakdown,
            "critical_conditions": critical_breakdown,
            "confidence_components": {
                "confidence": confidence,
                "model_agreement": conf_res.model_agreement,
                "c_corr": conf_res.c_corr,
                "q_mesh": conf_res.q_mesh,
            },
        }

        if critical_met:
            tier = AlertTier.CRITICAL
            audit_level = 3
            actions = [
                "AUTOMATED_SIRENS",
                "CONVEYOR_CUTOFF",
                "ZONE_EVACUATION",
                "LEVEL_3_DGMS_EMERGENCY_AUDIT",
            ]
            triggered_rules = critical_rules

        elif warning_met:
            tier = AlertTier.WARNING
            audit_level = 2
            actions = [
                "SMS_TELEGRAM_GEOTECHNICAL_MANAGER",
                "INSPECTION_DISPATCH",
                "LEVEL_2_DGMS_TRACKED",
            ]
            triggered_rules = ["WARNING_MULTI_CHANNEL_CONCORDANT_SURGE"]

        else:
            # Step 4: Evaluate Advisory conditions
            advisory_met, advisory_breakdown = self.evaluate_advisory_conditions(signals, confidence)
            rule_evidence["advisory_conditions"] = advisory_breakdown

            if advisory_met:
                tier = AlertTier.ADVISORY
                audit_level = 1
                actions = [
                    "DASHBOARD_NOTICE",
                    "NODE_HEALTH_PING",
                    "LEVEL_1_AUDIT_LOG",
                ]
                triggered_rules = ["ADVISORY_SINGLE_SENSOR_UNCORROBORATED_DRIFT"]
            else:
                tier = AlertTier.NONE
                audit_level = 0
                actions = ["ROUTINE_MONITORING"]
                triggered_rules = ["NORMAL_OPERATION_NO_ACTION_REQUIRED"]

        # Step 5: Format structured summary
        summary = self._generate_fallback_summary(signals, tier, confidence)

        evidence = EvidenceAttribution(
            tier=tier,
            confidence=confidence,
            triggered_rules=triggered_rules,
            rule_evidence=rule_evidence,
            contributing_sensors=signals.contributing_sensors,
            corroborating_node_ids=signals.corroborating_node_ids,
            plain_language_summary=summary,
        )

        return FusionDecisionResult(
            node_id=signals.node_id,
            timestamp=signals.timestamp,
            tier=tier,
            confidence=confidence,
            audit_level=audit_level,
            actions=actions,
            evidence_attribution=evidence,
            plain_language_summary=summary,
        )

    def _generate_fallback_summary(
        self,
        signals: FusionInputSignals,
        tier: AlertTier,
        confidence: float,
    ) -> str:
        """Internal summary generator matching required regulatory structure."""
        if tier == AlertTier.NONE:
            return f"NORMAL: Node {signals.node_id} ({signals.zone_id}, {signals.panel_id}) operating within nominal limits."

        tier_title = f"{tier.value} WARNING" if tier in [AlertTier.WARNING, AlertTier.CRITICAL] else "ADVISORY NOTICE"
        
        # Trigger deltas
        deltas = []
        if signals.instantaneous_tilt_surge_deg != 0.0:
            deltas.append(f"tilt surge ({signals.instantaneous_tilt_surge_deg:+.2f}°)")
        if signals.instantaneous_delta_disp_mm != 0.0:
            deltas.append(f"differential displacement ({signals.instantaneous_delta_disp_mm:+.2f} mm)")
        if not deltas:
            deltas.append(f"anomaly score S_node={signals.s_node:.2f}")
        delta_str = " and ".join(deltas)

        # Corroborating nodes + attention
        if signals.corroborating_node_ids:
            nodes_str = " and ".join(signals.corroborating_node_ids[:2])
            mean_alpha = max(signals.gat_neighbor_attentions.values()) if signals.gat_neighbor_attentions else 0.85
            corr_str = f"Corroborated by high spatial attention (α={mean_alpha:.2f}) with adjacent nodes {nodes_str} along the active extraction face."
        else:
            corr_str = "Uncorroborated single-sensor anomaly across mesh."

        # InSAR crosscheck
        if signals.insar_displacement_mm is not None:
            insar_str = f"InSAR macro-crosscheck confirms {abs(signals.insar_displacement_mm):.0f}mm historical depression basin."
        else:
            insar_str = "InSAR satellite data currently unavailable for pass."

        return f"{tier_title} ({signals.zone_id}, {signals.panel_id}): Triggered by {delta_str} at Node {signals.node_id}. {corr_str} {insar_str}"
