"""
Sensor Mesh Graph Builder for SubSense Layer 4.
Constructs PyTorch Geometric graph Data with:
  - 13-D node features: 12-D engineered features + 1-D per-node anomaly score
  - 4-D physical edge features: [distance, delta_z, fault_flag, retreat_angle]
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import torch
from torch_geometric.data import Data


@dataclass
class MeshGraphData:
    """Wrapper holding PyG Data and metadata."""
    data: Data
    node_ids: List[str]
    num_nodes: int
    num_edges: int
    edge_feature_dim: int
    node_feature_dim: int


class SensorMeshGraphBuilder:
    """
    Builds physically-grounded sensor mesh graphs.
    Connects nodes within spatial correlation radius R (or k-NN guarantee),
    and calculates 4D geomechanical edge attributes.
    """

    def __init__(
        self,
        max_edge_radius_m: float = 150.0,
        min_degree: int = 2,
        retreat_vector_azimuth_deg: float = 45.0,
        fault_segments: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
    ):
        self.max_edge_radius = float(max_edge_radius_m)
        self.min_degree = int(min_degree)
        
        # Longwall retreat direction unit vector
        az_rad = np.radians(retreat_vector_azimuth_deg)
        self.retreat_vector = np.array([np.sin(az_rad), np.cos(az_rad)], dtype=float)

        # Fault lines in local coordinates: [((x1, y1), (x2, y2)), ...]
        if fault_segments is None:
            # Default fault plane crossing mine concession (e.g. from x=100, y=0 to x=350, y=800)
            self.fault_segments = [
                ((100.0, 50.0), (380.0, 750.0))
            ]
        else:
            self.fault_segments = fault_segments

    @staticmethod
    def _segments_intersect(
        p1: np.ndarray, p2: np.ndarray,
        q1: np.ndarray, q2: np.ndarray,
    ) -> bool:
        """Determines if segment (p1, p2) intersects segment (q1, q2)."""
        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

        return (ccw(p1, q1, q2) != ccw(p2, q1, q2)) and (ccw(p1, p2, q1) != ccw(p1, p2, q2))

    def check_fault_intersection(self, pos_i: np.ndarray, pos_j: np.ndarray) -> float:
        """Returns 1.0 if edge between i and j intersects any mapped fault segment, else 0.0."""
        pi = pos_i[:2]
        pj = pos_j[:2]
        for f1, f2 in self.fault_segments:
            q1 = np.array(f1, dtype=float)
            q2 = np.array(f2, dtype=float)
            if self._segments_intersect(pi, pj, q1, q2):
                return 1.0
        return 0.0

    def compute_edge_features(
        self,
        pos_i: np.ndarray,
        pos_j: np.ndarray,
    ) -> np.ndarray:
        """
        Computes 4D physically-grounded edge features:
          1. 3D Euclidean distance (normalized by 100m)
          2. Elevation difference Δz = z_j - z_i (normalized by 10m)
          3. Geological fault intersection flag (0.0 or 1.0)
          4. Relative angle to longwall retreat vector in [0.0, 1.0] (θ / π)
        """
        diff = pos_j - pos_i
        dist_3d = float(np.linalg.norm(diff))
        delta_z = float(diff[2]) if len(diff) > 2 else 0.0

        # Fault intersection
        fault_flag = self.check_fault_intersection(pos_i, pos_j)

        # Retreat angle
        vec_2d = diff[:2]
        norm_2d = np.linalg.norm(vec_2d)
        if norm_2d > 1e-4:
            unit_2d = vec_2d / norm_2d
            cos_theta = np.clip(np.dot(unit_2d, self.retreat_vector), -1.0, 1.0)
            angle_rad = np.arccos(cos_theta)
            norm_angle = float(angle_rad / np.pi)  # in [0, 1]
        else:
            norm_angle = 0.0

        return np.array([
            dist_3d / 100.0,
            delta_z / 10.0,
            fault_flag,
            norm_angle,
        ], dtype=np.float32)

    def build_graph(
        self,
        node_features: np.ndarray,       # (N, 12) from FeaturePipeline
        anomaly_scores: np.ndarray,      # (N,) or (N, 1) from AnomalyEnsemble
        node_coords_3d: np.ndarray,      # (N, 3) [x, y, z] in meters
        node_ids: Optional[List[str]] = None,
        ground_truth_risk: Optional[np.ndarray] = None, # (N,) optional
    ) -> MeshGraphData:
        """
        Builds PyTorch Geometric Data object.
        """
        num_nodes = len(node_features)
        if node_ids is None:
            node_ids = [f"node_{i:03d}" for i in range(num_nodes)]

        # Prepare 13-D node feature matrix: [12-D features, 1-D anomaly score]
        scores = np.atleast_2d(anomaly_scores)
        if scores.shape[0] != num_nodes and scores.shape[1] == num_nodes:
            scores = scores.T
        if scores.shape[1] != 1:
            scores = scores.reshape(num_nodes, 1)

        x_mat = np.hstack([node_features, scores]).astype(np.float32)

        # Build edges
        edge_indices = []
        edge_attrs = []

        # Distance matrix
        diffs = node_coords_3d[:, None, :] - node_coords_3d[None, :, :]
        dists_3d = np.linalg.norm(diffs, axis=2)

        for i in range(num_nodes):
            # Candidate neighbors within max_edge_radius
            connected_j = []
            for j in range(num_nodes):
                if i != j and dists_3d[i, j] <= self.max_edge_radius:
                    connected_j.append(j)

            # Enforce minimum degree connectivity to avoid isolated subgraphs
            if len(connected_j) < self.min_degree and num_nodes > 1:
                sorted_j = np.argsort(dists_3d[i])[1:self.min_degree + 1]
                connected_j = list(set(connected_j).union(sorted_j))

            for j in connected_j:
                edge_indices.append([i, j])
                edge_feat = self.compute_edge_features(node_coords_3d[i], node_coords_3d[j])
                edge_attrs.append(edge_feat)

        if len(edge_indices) == 0:
            # Fallback self-loops if single node
            edge_index_t = torch.zeros((2, 1), dtype=torch.long)
            edge_attr_t = torch.zeros((1, 4), dtype=torch.float32)
        else:
            edge_index_t = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
            edge_attr_t = torch.tensor(np.array(edge_attrs), dtype=torch.float32)

        x_t = torch.tensor(x_mat, dtype=torch.float32)
        pos_t = torch.tensor(node_coords_3d, dtype=torch.float32)

        data = Data(x=x_t, edge_index=edge_index_t, edge_attr=edge_attr_t, pos=pos_t)
        if ground_truth_risk is not None:
            data.y = torch.tensor(ground_truth_risk, dtype=torch.float32)

        return MeshGraphData(
            data=data,
            node_ids=node_ids,
            num_nodes=num_nodes,
            num_edges=edge_index_t.size(1),
            edge_feature_dim=4,
            node_feature_dim=13,
        )
