from typing import Optional
import numpy as np
from sklearn.ensemble import IsolationForest
import pickle

class IsolationForestAnomalyDetector:
    """
    Unsupervised Isolation Forest Anomaly Detector (Section 4, Table 2).
    Isolates anomalous sensor observations by recursive random partitioning.
    Produces a continuous anomaly score scaled to [0.0, 1.0] where 1.0 is most anomalous.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.05,
        random_state: int = 42,
        version: str = "if-v1.0.0",
    ):
        self.version = version
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        self.is_fitted = False
        self._df_threshold = 0.0

    def fit(self, X: np.ndarray) -> "IsolationForestAnomalyDetector":
        """Fits the Isolation Forest on baseline / historical feature vectors."""
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        self.model.fit(X)
        self.is_fitted = True

        df = self.model.decision_function(X)
        # 5th percentile of normal training decision function is baseline boundary
        self._df_threshold = float(np.percentile(df, 5))
        return self

    def predict_anomaly_score(self, X: np.ndarray) -> np.ndarray:
        """
        Computes anomaly score in [0.0, 1.0].
        Uses decision_function where positive = normal inlier, negative = outlier anomaly.
        Smooth sigmoidal response:
        score = 1 / (1 + exp(6 * (df - threshold)))
        """
        if not self.is_fitted:
            norm = np.linalg.norm(X, axis=-1, keepdims=True)
            return np.clip(norm / (norm + 10.0), 0.0, 1.0).ravel()

        if X.ndim == 1:
            X = X.reshape(1, -1)

        df = self.model.decision_function(X)
        # Shift so decision threshold maps around 0.5
        scaled = (df - self._df_threshold) * 8.0
        # Invert: positive df (normal) -> score near 0.0; negative df (anomalous) -> score near 1.0
        scores = 1.0 / (1.0 + np.exp(np.clip(scaled, -15.0, 15.0)))
        return np.clip(scores, 0.0, 1.0)

    def save(self, file_path: str) -> None:
        with open(file_path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, file_path: str) -> "IsolationForestAnomalyDetector":
        with open(file_path, "rb") as f:
            return pickle.load(f)
