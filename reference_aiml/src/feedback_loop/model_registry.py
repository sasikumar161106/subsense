from typing import Dict, List, Optional
from datetime import datetime, timezone
from src.schemas.feedback_contracts import ModelRegistryEntry

class ModelRegistry:
    """
    Model Registry and Version Traceability Store (Section 8.2 & 12).
    Tracks active versions, training sample counts, and validation scores.
    Enables instant rollback and ensures 100% auditability for regulatory DGMS inquiries.
    """

    def __init__(self):
        self._entries: Dict[str, Dict[str, ModelRegistryEntry]] = {
            "anomaly": {},
            "correlation": {},
            "forecast": {},
        }
        self._active_versions: Dict[str, str] = {
            "anomaly": "cloud-ensemble-v2.1.0",
            "correlation": "gnn-corr-v1.4.0",
            "forecast": "lstm-forecast-v1.2.0",
        }
        # Pre-seed initial active baselines
        self.register(
            family="anomaly",
            version="cloud-ensemble-v2.1.0",
            metrics={"precision": 0.94, "recall": 0.91, "f1": 0.925},
            is_active=True,
        )
        self.register(
            family="correlation",
            version="gnn-corr-v1.4.0",
            metrics={"precision": 0.96, "recall": 0.89, "f1": 0.924},
            is_active=True,
        )
        self.register(
            family="forecast",
            version="lstm-forecast-v1.2.0",
            metrics={"mae_hours": 2.4, "rmse_hours": 3.8},
            is_active=True,
        )

    def register(
        self,
        family: str,
        version: str,
        metrics: Dict[str, float],
        hyperparameters: Optional[Dict] = None,
        is_active: bool = False,
    ) -> ModelRegistryEntry:
        entry = ModelRegistryEntry(
            model_name=family,
            version=version,
            created_at=datetime.now(timezone.utc),
            is_active=is_active,
            validation_metrics=metrics,
            hyperparameters=hyperparameters or {},
        )
        if family not in self._entries:
            self._entries[family] = {}
        self._entries[family][version] = entry

        if is_active:
            for v, e in self._entries[family].items():
                e.is_active = (v == version)
            self._active_versions[family] = version

        return entry

    def get_active_versions(self) -> Dict[str, str]:
        return dict(self._active_versions)

    def rollback(self, family: str, target_version: str) -> bool:
        """Rolls back the active model version to a previously validated checkpoint."""
        if family in self._entries and target_version in self._entries[family]:
            for v, e in self._entries[family].items():
                e.is_active = (v == target_version)
            self._active_versions[family] = target_version
            return True
        return False

    def list_history(self, family: Optional[str] = None) -> List[ModelRegistryEntry]:
        results = []
        families = [family] if family else list(self._entries.keys())
        for f in families:
            results.extend(self._entries[f].values())
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results
