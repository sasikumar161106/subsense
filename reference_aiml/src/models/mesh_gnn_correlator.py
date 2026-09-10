from typing import Dict, List, Tuple, Optional
import numpy as np
import torch
import torch.nn as nn
import networkx as nx
from src.schemas.sensor_contracts import EngineeredFeatureVector

class GraphConvolutionLayer(nn.Module):
    """Symmetric spectral graph convolution: H' = ReLU(A_norm @ H @ W)."""

    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features)
        # Initialize with positive Xavier weights to preserve anomaly excitation
        nn.init.xavier_uniform_(self.linear.weight, gain=1.2)
        nn.init.constant_(self.linear.bias, 0.1)
        self.activation = nn.ReLU()

    def forward(self, x: torch.Tensor, adj_norm: torch.Tensor) -> torch.Tensor:
        support = self.linear(x)
        output = torch.matmul(adj_norm, support)
        return self.activation(output)

class MeshSpatialGNN(nn.Module):
    """Two-layer Spatial Graph Neural Network over wireless mesh topology."""

    def __init__(self, in_features: int = 9, hidden_dim: int = 16, out_dim: int = 8):
        super().__init__()
        self.gcn1 = GraphConvolutionLayer(in_features, hidden_dim)
        self.gcn2 = GraphConvolutionLayer(hidden_dim, out_dim)
        self.head = nn.Sequential(
            nn.Linear(out_dim, 1),
            nn.Sigmoid()
        )
        # Positive initialization on final projection
        nn.init.constant_(self.head[0].weight, 0.5)
        nn.init.constant_(self.head[0].bias, 0.0)

    def forward(self, x: torch.Tensor, adj_norm: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h1 = self.gcn1(x, adj_norm)
        h2 = self.gcn2(h1, adj_norm)
        correlated_node_scores = self.head(h2)  # [N, 1]
        return correlated_node_scores, h2

class MeshGNNCorrelator:
    """
    Graph-Based Spatial Correlation Engine (Section 5).
    Propagates and aggregates anomaly features across wireless mesh neighborhoods
    to distinguish genuine subsidence basins from isolated hardware noise.
    """

    def __init__(
        self,
        spatial_radius_m: float = 150.0,
        correlation_threshold: float = 0.65,
        min_cluster_size: int = 2,
        version: str = "gnn-corr-v1.4.0",
    ):
        self.spatial_radius_m = spatial_radius_m
        self.correlation_threshold = correlation_threshold
        self.min_cluster_size = min_cluster_size
        self.version = version

        # Fixed deterministic seed for runtime reproducibility
        torch.manual_seed(42)
        # 9 features = 8 engineered features + 1 anomaly_score
        self.gnn = MeshSpatialGNN(in_features=9, hidden_dim=16, out_dim=8)
        self.gnn.eval()

    def build_adjacency(
        self,
        node_ids: List[str],
        node_coords: Dict[str, Tuple[float, float]],
    ) -> Tuple[torch.Tensor, nx.Graph]:
        """
        Constructs distance-weighted spatial adjacency matrix and NetworkX graph.
        coords: {node_id: (utm_x, utm_y)}
        """
        n = len(node_ids)
        coords = np.zeros((n, 2), dtype=np.float32)
        for i, nid in enumerate(node_ids):
            coords[i] = node_coords.get(nid, (0.0, 0.0))

        # Pairwise distance matrix
        diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=-1))

        # Gaussian radial basis edge weights
        sigma = self.spatial_radius_m / 2.0
        adj = np.exp(- (dist ** 2) / (2.0 * sigma ** 2))
        # Mask edges beyond spatial radius and zero out self-loops for graph building
        mask = (dist <= self.spatial_radius_m) & (dist > 0.0)
        adj_masked = np.where(mask, adj, 0.0)

        # Add self-loops with weight 1.0 for GNN message aggregation
        adj_self = adj_masked + np.eye(n)

        # Symmetric degree normalization: D^(-1/2) @ A @ D^(-1/2)
        deg = np.sum(adj_self, axis=1)
        deg_inv_sqrt = np.power(np.maximum(deg, 1e-6), -0.5)
        adj_norm = deg_inv_sqrt[:, np.newaxis] * adj_self * deg_inv_sqrt[np.newaxis, :]

        # NetworkX graph representation for connected component analysis
        G = nx.Graph()
        for i, nid in enumerate(node_ids):
            G.add_node(nid, pos=coords[i])
        for i in range(n):
            for j in range(i + 1, n):
                if mask[i, j]:
                    G.add_edge(node_ids[i], node_ids[j], weight=float(adj[i, j]))

        return torch.tensor(adj_norm, dtype=torch.float32), G

    def correlate(
        self,
        node_ids: List[str],
        node_coords: Dict[str, Tuple[float, float]],
        feature_map: Dict[str, EngineeredFeatureVector],
        anomaly_scores: Dict[str, float],
        site_id: str = "SITE-JHARIA-04",
    ) -> List[Dict]:
        """
        Runs spatial message passing over the mesh graph.
        Returns candidate risk zones with correlation_score and contributing nodes.
        """
        if len(node_ids) < self.min_cluster_size:
            return []

        adj_norm, graph = self.build_adjacency(node_ids, node_coords)

        # Construct input feature matrix [N, 9]
        features = []
        for nid in node_ids:
            fvec = feature_map[nid].to_feature_list()
            ascore = anomaly_scores.get(nid, 0.0)
            features.append(fvec + [ascore])

        x_tensor = torch.tensor(features, dtype=torch.float32)

        with torch.no_grad():
            node_corr_scores, embeddings = self.gnn(x_tensor, adj_norm)
            node_corr_scores = node_corr_scores.cpu().numpy().ravel()

        # Combine GNN score with raw anomaly score for spatial corroboration
        # Correlated score is boosted if adjacent nodes are both anomalous
        refined_scores = {}
        for i, nid in enumerate(node_ids):
            raw_a = anomaly_scores.get(nid, 0.0)
            gnn_val = float(node_corr_scores[i])
            # High GNN output corroborates spatial coherence
            refined_scores[nid] = 0.5 * raw_a + 0.5 * gnn_val

        # Subgraph clustering of candidate elevated nodes
        elevated_nodes = [
            nid for nid in node_ids
            if refined_scores[nid] >= 0.40 or anomaly_scores.get(nid, 0.0) >= 0.50
        ]
        subgraph = graph.subgraph(elevated_nodes)

        risk_zones = []
        zone_idx = 1
        for comp in nx.connected_components(subgraph):
            cluster_nodes = list(comp)
            # Evaluate cluster strength
            cluster_anomalies = [refined_scores[n] for n in cluster_nodes]
            mean_score = float(np.mean(cluster_anomalies))

            # Isolated single nodes get discounted heavily (anti-false-alarm mechanism)
            if len(cluster_nodes) == 1:
                correlation_score = float(mean_score * 0.45)
            else:
                # Multi-node spatial coherence boost: sqrt(cluster_size) bonus up to 1.0
                cluster_boost = min(1.3, 1.0 + 0.1 * (len(cluster_nodes) - 1))
                correlation_score = float(np.clip(mean_score * cluster_boost, 0.0, 1.0))

            zone_name = f"PANEL-7-ZONE-{zone_idx:02d}"
            risk_zones.append({
                "site_id": site_id,
                "zone_id": zone_name,
                "node_ids": cluster_nodes,
                "correlation_score": correlation_score,
                "anomaly_score": mean_score,
                "cluster_size": len(cluster_nodes),
                "is_significant": correlation_score >= self.correlation_threshold,
            })
            zone_idx += 1

        # Sort descending by correlation score
        risk_zones.sort(key=lambda z: z["correlation_score"], reverse=True)
        return risk_zones
