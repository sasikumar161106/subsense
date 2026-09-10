"""
GATv2 Attention Edge Extractor for SubSense Phase 3 Explainability.
Extracts top-k attention edges between sensor nodes along physical fracture pathways.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from gnn.gatv2_model import GNNInferenceResult


@dataclass
class AttentionEdgeAttribution:
    source_node_id: str
    target_node_id: str
    attention_alpha: float
    direction: str                     # "TO_TARGET" or "FROM_SOURCE"
    layer_idx: int = 2                 # Final layer index


@dataclass
class GATAttentionSummary:
    node_id: str
    corroborating_neighbor_ids: List[str]
    max_attention_alpha: float
    mean_attention_alpha: float
    top_edges: List[AttentionEdgeAttribution]
    structural_feature_context: str


class GATAttentionExtractor:
    """
    Extracts top-k structural attention edges from GNN inference outputs.
    Corroborates localized ground movement with adjacent mesh nodes.
    """

    def __init__(self, default_top_k: int = 3):
        self.default_top_k = default_top_k

    def extract_top_k_attentions(
        self,
        gnn_result: GNNInferenceResult,
        target_node_id: str,
        top_k: Optional[int] = None,
    ) -> GATAttentionSummary:
        """
        Extracts top-k attention edges connected to target_node_id.
        """
        k = top_k or self.default_top_k
        node_ids = gnn_result.node_ids
        if target_node_id not in node_ids:
            # Fallback if node not found
            return GATAttentionSummary(
                node_id=target_node_id,
                corroborating_neighbor_ids=[],
                max_attention_alpha=0.0,
                mean_attention_alpha=0.0,
                top_edges=[],
                structural_feature_context="active extraction face",
            )

        target_idx = node_ids.index(target_node_id)
        edge_index = gnn_result.edge_index  # (2, E)
        att_weights = gnn_result.attention_weights  # (E,) or (E, heads)

        # Collapse multi-head attention if 2D
        if att_weights.ndim > 1:
            att_weights = np.mean(att_weights, axis=-1)

        src_indices = edge_index[0]
        dst_indices = edge_index[1]

        # Edges connected to target node (either source or destination)
        connected_edges: List[Tuple[int, str, float]] = []
        for e_idx in range(len(src_indices)):
            u = int(src_indices[e_idx])
            v = int(dst_indices[e_idx])
            alpha = float(att_weights[e_idx]) if e_idx < len(att_weights) else 0.5

            if u == target_idx and v != target_idx:
                connected_edges.append((v, "OUTGOING", alpha))
            elif v == target_idx and u != target_idx:
                connected_edges.append((u, "INCOMING", alpha))

        # Sort by attention alpha descending
        connected_edges.sort(key=lambda x: x[2], reverse=True)

        seen_neighbors = set()
        top_attributions: List[AttentionEdgeAttribution] = []
        corroborating_nodes: List[str] = []

        for neighbor_idx, direction, alpha in connected_edges:
            if neighbor_idx >= len(node_ids):
                continue
            nbr_id = node_ids[neighbor_idx]
            if nbr_id in seen_neighbors:
                continue
            seen_neighbors.add(nbr_id)

            corroborating_nodes.append(nbr_id)
            top_attributions.append(AttentionEdgeAttribution(
                source_node_id=target_node_id if direction == "OUTGOING" else nbr_id,
                target_node_id=nbr_id if direction == "OUTGOING" else target_node_id,
                attention_alpha=float(alpha),
                direction=direction,
            ))

            if len(corroborating_nodes) >= k:
                break

        # Calculate summary statistics
        if top_attributions:
            alphas = [e.attention_alpha for e in top_attributions]
            max_alpha = float(max(alphas))
            mean_alpha = float(np.mean(alphas))
        else:
            max_alpha = 0.0
            mean_alpha = 0.0

        return GATAttentionSummary(
            node_id=target_node_id,
            corroborating_neighbor_ids=corroborating_nodes,
            max_attention_alpha=max_alpha,
            mean_attention_alpha=mean_alpha,
            top_edges=top_attributions,
            structural_feature_context="active extraction face",
        )
