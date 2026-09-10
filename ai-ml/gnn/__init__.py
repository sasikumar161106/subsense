"""
SubSense Layer 4 - Graph Neural Network Mesh Correlation Module.
3-layer GATv2 over sensor mesh graph with 4D physically-grounded edge features:
  - 3D Euclidean distance (m)
  - Elevation difference Δz (m)
  - Geological fault intersection flag (0/1)
  - Relative angle to longwall face retreat vector (rad)
Outputs:
  - Graph-refined risk score R_GNN(v_i) in [0.0, 1.0] per node
  - Persisted attention weight tensor for Phase 3 explainability
"""

from .mesh_graph import SensorMeshGraphBuilder, MeshGraphData
from .gatv2_model import SubSenseGATv2, GNNInferenceResult
from .ablation import GNNAblationStudy, AblationResult

__all__ = [
    "SensorMeshGraphBuilder",
    "MeshGraphData",
    "SubSenseGATv2",
    "GNNInferenceResult",
    "GNNAblationStudy",
    "AblationResult",
]
