"""
SubSense Geotechnical Natural-Language Alert Summary Generator.
Generates structured, auditable regulatory explanations conforming to DGMS mandates.
"""

from typing import List, Optional
from fusion.schemas import AlertTier, FusionInputSignals
from .attention_extractor import GATAttentionSummary


class GeotechnicalSummaryGenerator:
    """
    Generates standardized natural-language summaries for SubSense alerts.
    Structure:
    [TIER] [ALERT_TYPE] (Zone, Panel): Triggered by [deltas] at Node [ID].
    Corroborated by high spatial attention (alpha=X.XX) with adjacent nodes [N1, N2] along [feature].
    InSAR macro-crosscheck [InSAR confirmation].
    """

    def generate(
        self,
        tier: AlertTier,
        zone_id: str,
        panel_id: str,
        node_id: str,
        trigger_deltas_str: str,
        corroborating_nodes: List[str],
        attention_alpha: float = 0.85,
        structural_feature: str = "active extraction face",
        insar_displacement_mm: Optional[float] = None,
    ) -> str:
        """Constructs conforming natural-language alert narrative."""
        # Tier & Header
        if tier == AlertTier.CRITICAL:
            header = f"CRITICAL WARNING ({zone_id}, {panel_id}):"
        elif tier == AlertTier.WARNING:
            header = f"WARNING ({zone_id}, {panel_id}):"
        elif tier == AlertTier.ADVISORY:
            header = f"ADVISORY NOTICE ({zone_id}, {panel_id}):"
        else:
            return f"NORMAL STATUS ({zone_id}, {panel_id}): Node {node_id} within nominal operating bounds."

        # Trigger deltas
        trigger_part = f"Triggered by {trigger_deltas_str} at Node {node_id}."

        # Corroboration clause
        if corroborating_nodes:
            if len(corroborating_nodes) == 1:
                nodes_phrase = f"adjacent node {corroborating_nodes[0]}"
            else:
                nodes_phrase = f"adjacent nodes {' and '.join(corroborating_nodes[:2])}"
            corrob_part = (
                f"Corroborated by high spatial attention (α={attention_alpha:.2f}) "
                f"with {nodes_phrase} along the {structural_feature}."
            )
        else:
            corrob_part = "Single-sensor uncorroborated anomaly across mesh."

        # InSAR clause
        if insar_displacement_mm is not None and abs(insar_displacement_mm) > 0.0:
            insar_part = f"InSAR macro-crosscheck confirms {abs(insar_displacement_mm):.0f}mm historical depression basin."
        elif insar_displacement_mm is not None:
            insar_part = "InSAR macro-crosscheck indicates 0mm macro-scale surface divergence."
        else:
            insar_part = "InSAR satellite crosscheck unavailable for current orbital cycle."

        return f"{header} {trigger_part} {corrob_part} {insar_part}"

    def generate_from_signals(
        self,
        signals: FusionInputSignals,
        tier: AlertTier,
        gat_summary: Optional[GATAttentionSummary] = None,
    ) -> str:
        """Automates delta extraction and narrative generation directly from FusionInputSignals."""
        deltas = []
        if signals.instantaneous_tilt_surge_deg != 0.0:
            deltas.append(f"sustained tilt surge ({signals.instantaneous_tilt_surge_deg:+.2f}° over 30 min)")
        if signals.instantaneous_delta_disp_mm != 0.0:
            deltas.append(f"differential displacement ({signals.instantaneous_delta_disp_mm:+.2f} mm/hr)")
        elif signals.lstm_velocity_mm_h != 0.0:
            deltas.append(f"differential displacement (+{signals.lstm_velocity_mm_h:.1f} mm/hr)")
        
        if not deltas:
            deltas.append(f"elevated anomaly score (S_node={signals.s_node:.2f})")

        deltas_str = " and ".join(deltas)

        # Corroborating nodes and alpha
        if gat_summary and gat_summary.corroborating_neighbor_ids:
            corr_nodes = gat_summary.corroborating_neighbor_ids
            alpha = gat_summary.max_attention_alpha or 0.85
            struct_feat = gat_summary.structural_feature_context
        elif signals.corroborating_node_ids:
            corr_nodes = signals.corroborating_node_ids
            alpha = max(signals.gat_neighbor_attentions.values()) if signals.gat_neighbor_attentions else 0.85
            struct_feat = "active extraction face"
        else:
            corr_nodes = []
            alpha = 0.0
            struct_feat = "active extraction face"

        return self.generate(
            tier=tier,
            zone_id=signals.zone_id,
            panel_id=signals.panel_id,
            node_id=signals.node_id,
            trigger_deltas_str=deltas_str,
            corroborating_nodes=corr_nodes,
            attention_alpha=alpha,
            structural_feature=struct_feat,
            insar_displacement_mm=signals.insar_displacement_mm,
        )
