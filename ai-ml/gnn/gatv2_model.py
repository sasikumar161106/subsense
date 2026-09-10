"""
3-Layer GATv2 Mesh Correlation Model for SubSense Layer 4.
Processes 13-D node features and 4-D physically-grounded edge features.
Attention:
  α_ij = softmax_j( LeakyReLU( aᵀ[W·h_i ‖ W·h_j ‖ W_e·e_ij] ) )
Outputs:
  - Graph-refined risk score R_GNN(v_i) in [0.0, 1.0] per node
  - Persisted attention weight tensor matrix for Phase 3 explainability
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GATv2Conv

from .mesh_graph import MeshGraphData


@dataclass
class GNNInferenceResult:
    """Dataclass holding graph-refined risk scores and explainability attention weights."""
    risk_scores: np.ndarray             # R_GNN(v_i) in [0.0, 1.0] of shape (N,)
    edge_index: np.ndarray              # (2, E)
    attention_weights: np.ndarray       # (E,) or (E, heads) final layer attention
    layer_attentions: List[np.ndarray]  # Attention weights for each of the 3 GATv2 layers
    node_ids: List[str]
    num_nodes: int
    num_edges: int


class SubSenseGATv2(nn.Module):
    """
    3-Layer Graph Attention Network v2 with Physical Edge Features.
    Satisfies Principle 4 (Physically-Grounded Correlation).
    """

    def __init__(
        self,
        in_channels: int = 13,
        hidden_dim: int = 32,
        edge_dim: int = 4,
        heads: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.in_channels = in_channels
        self.hidden_dim = hidden_dim
        self.edge_dim = edge_dim
        self.heads = heads
        self.dropout = dropout

        # Layer 1: in_channels (13) -> hidden_dim * heads
        self.conv1 = GATv2Conv(
            in_channels=in_channels,
            out_channels=hidden_dim,
            heads=heads,
            concat=True,
            edge_dim=edge_dim,
            dropout=dropout,
        )

        # Layer 2: hidden_dim * heads -> hidden_dim * heads
        self.conv2 = GATv2Conv(
            in_channels=hidden_dim * heads,
            out_channels=hidden_dim,
            heads=heads,
            concat=True,
            edge_dim=edge_dim,
            dropout=dropout,
        )

        # Layer 3: hidden_dim * heads -> 16 (heads=1)
        self.conv3 = GATv2Conv(
            in_channels=hidden_dim * heads,
            out_channels=16,
            heads=1,
            concat=False,
            edge_dim=edge_dim,
            dropout=dropout,
        )

        # Output projection head to risk score in [0.0, 1.0]
        self.risk_head = nn.Sequential(
            nn.Linear(16, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        return_attention_weights: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, List[Tuple[torch.Tensor, torch.Tensor]]]]:
        """
        Forward pass through 3 GATv2 layers.
        """
        attentions = []

        # Layer 1
        if return_attention_weights:
            h1, att1 = self.conv1(x, edge_index, edge_attr=edge_attr, return_attention_weights=True)
            attentions.append(att1)
        else:
            h1 = self.conv1(x, edge_index, edge_attr=edge_attr)
        h1 = F.elu(h1)
        h1 = F.dropout(h1, p=self.dropout, training=self.training)

        # Layer 2
        if return_attention_weights:
            h2, att2 = self.conv2(h1, edge_index, edge_attr=edge_attr, return_attention_weights=True)
            attentions.append(att2)
        else:
            h2 = self.conv2(h1, edge_index, edge_attr=edge_attr)
        h2 = F.elu(h2)
        h2 = F.dropout(h2, p=self.dropout, training=self.training)

        # Layer 3
        if return_attention_weights:
            h3, att3 = self.conv3(h2, edge_index, edge_attr=edge_attr, return_attention_weights=True)
            attentions.append(att3)
        else:
            h3 = self.conv3(h2, edge_index, edge_attr=edge_attr)
        h3 = F.elu(h3)

        # Node risk scores
        risk = self.risk_head(h3).squeeze(-1)  # (N,)

        if return_attention_weights:
            return risk, attentions
        return risk

    def infer_mesh(
        self,
        mesh_graph: Union[MeshGraphData, Data],
        device: Optional[torch.device] = None,
    ) -> GNNInferenceResult:
        """
        Inference interface returning graph-refined risk scores and persisted attention weights.
        """
        self.eval()
        dev = device or next(self.parameters()).device

        if isinstance(mesh_graph, MeshGraphData):
            data = mesh_graph.data
            node_ids = mesh_graph.node_ids
        else:
            data = mesh_graph
            node_ids = [f"node_{i}" for i in range(data.x.size(0))]

        x = data.x.to(dev)
        edge_index = data.edge_index.to(dev)
        edge_attr = data.edge_attr.to(dev)

        with torch.no_grad():
            risk_t, attentions = self.forward(
                x, edge_index, edge_attr, return_attention_weights=True
            )

        risk_np = risk_t.cpu().numpy()
        edge_idx_np = edge_index.cpu().numpy()

        layer_atts = []
        for _, att_w in attentions:
            # att_w can be (E, heads) or (E,)
            layer_atts.append(att_w.cpu().numpy())

        # Primary attention: Layer 3 attention averaged across heads
        final_att = layer_atts[-1]
        if final_att.ndim > 1:
            primary_att = np.mean(final_att, axis=-1)
        else:
            primary_att = final_att

        # Slice to match original mesh edges (excluding PyG internal self-loops)
        num_mesh_edges = data.edge_index.size(1)
        primary_att = primary_att[:num_mesh_edges]

        return GNNInferenceResult(
            risk_scores=risk_np,
            edge_index=edge_idx_np,
            attention_weights=primary_att,
            layer_attentions=layer_atts,
            node_ids=node_ids,
            num_nodes=len(node_ids),
            num_edges=edge_idx_np.shape[1],
        )

    def save_model(self, path: str) -> None:
        """Persists model checkpoint."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        torch.save({
            "state_dict": self.state_dict(),
            "config": {
                "in_channels": self.in_channels,
                "hidden_dim": self.hidden_dim,
                "edge_dim": self.edge_dim,
                "heads": self.heads,
                "dropout": self.dropout,
            },
        }, path)

    @classmethod
    def load_model(cls, path: str, device: Optional[torch.device] = None) -> "SubSenseGATv2":
        """Loads model checkpoint."""
        checkpoint = torch.load(path, map_location=device or "cpu")
        model = cls(**checkpoint["config"])
        model.load_state_dict(checkpoint["state_dict"])
        return model
