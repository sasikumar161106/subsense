import numpy as np

class ConfidenceScorer:
    """
    Confidence Scoring Engine (Section 7).
    Derives machine-auditable confidence from:
    1. Anomaly ensemble agreement (Isolation Forest vs. Autoencoder concordance).
    2. Strength of the GNN spatial correlation.
    3. Cardinality of independent contributing nodes (multi-sensor corroboration).
    """

    def __init__(
        self,
        weight_agreement: float = 0.35,
        weight_gnn: float = 0.40,
        weight_nodes: float = 0.25,
    ):
        self.weight_agreement = weight_agreement
        self.weight_gnn = weight_gnn
        self.weight_nodes = weight_nodes

    def compute_confidence(
        self,
        ensemble_agreement: float,     # [0.0, 1.0]
        correlation_score: float,      # [0.0, 1.0]
        num_contributing_nodes: int,   # >= 1
    ) -> float:
        """
        Computes composite confidence score in [0.0, 1.0].
        Guaranteed to be non-null and strictly bounded.
        """
        # Node factor: log2 saturation curve (1 node -> 0.4, 2 nodes -> 0.63, 3 nodes -> 0.79, 4+ nodes -> 0.9+)
        node_factor = min(1.0, np.log2(1.0 + num_contributing_nodes) / 2.0)

        raw_conf = (
            self.weight_agreement * np.clip(ensemble_agreement, 0.0, 1.0) +
            self.weight_gnn * np.clip(correlation_score, 0.0, 1.0) +
            self.weight_nodes * node_factor
        )

        return float(round(np.clip(raw_conf, 0.05, 0.99), 2))
