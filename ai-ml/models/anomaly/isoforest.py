"""
Isolation Forest per-node baseline anomaly filter.
Adheres to Section 5.1: 100 estimators, sub-sampling ratio 0.75 (max_samples=0.75).
Normalized anomaly score S_IF in [0.0, 1.0].
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from typing import Optional


class MineIsolationForest:
    """
    Isolation Forest anomaly estimator tuned for geotechnical strata telemetry.
    100 trees, 0.75 sub-sampling ratio.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_samples: float = 0.75,
        contamination: float = 0.05,
        random_state: int = 42,
    ):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        self.is_fitted = False
        self._score_min = -0.7
        self._score_max = -0.3

    def fit(self, X: np.ndarray) -> "MineIsolationForest":
        """Fits the Isolation Forest on 12-dimensional baseline feature matrix."""
        assert X.ndim == 2, "Expected 2D matrix (N, 12)"
        self.model.fit(X)
        self.is_fitted = True

        # Calibrate normalization bounds from baseline distribution
        scores = self.model.score_samples(X)
        if len(scores) > 0:
            self._score_min = float(np.percentile(scores, 1.0))
            self._score_max = float(np.percentile(scores, 99.0))
            if self._score_max <= self._score_min:
                self._score_max = self._score_min + 0.1
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """
        Computes normalized anomaly score S_IF in [0.0, 1.0].
        Higher score means more anomalous.
        """
        if not self.is_fitted:
            # If not fitted yet, default to safe baseline 0.1
            if X.ndim == 1:
                return np.array([0.1], dtype=np.float32)
            return np.full((X.shape[0],), 0.1, dtype=np.float32)

        if X.ndim == 1:
            X_in = X.reshape(1, -1)
        else:
            X_in = X

        # In scikit-learn, decision_function returns positive for inliers/normal,
        # and negative for outliers/anomalies (offset_ is the 0-boundary).
        df = self.model.decision_function(X_in)
        
        # Calibrated mapping to [0.0, 1.0]:
        # If df >= 0 (normal): score in [0.0, 0.25]
        # If df < 0 (anomalous): score in [0.25, 1.0]
        s_if = np.where(
            df >= 0.0,
            0.25 * (1.0 - np.clip(df / 0.15, 0.0, 1.0)),
            0.25 + 0.75 * np.clip(-df / 0.20, 0.0, 1.0)
        ).astype(np.float32)

        if X.ndim == 1:
            return s_if[0]
        return s_if
