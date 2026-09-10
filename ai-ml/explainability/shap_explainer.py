"""
SubSense Explainability Layer: TreeSHAP and Captum Feature Attribution.
Computes exact game-theoretic Shapley values on tabular Isolation Forest models
and integrated gradients on neural autoencoders / LSTM forecasters.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import torch
import shap
from captum.attr import IntegratedGradients

from features.constants import FEATURE_NAMES, SENSOR_ATTRIBUTION_MAPPING, FEATURE_VECTOR_DIM
from models.anomaly.isoforest import MineIsolationForest


@dataclass
class FeatureShapValue:
    feature_name: str
    shap_value: float
    feature_value: float
    attributed_sensor: str


@dataclass
class ShapExplanationResult:
    feature_attributions: List[FeatureShapValue]
    contributing_sensors: List[str]
    top_feature_names: List[str]
    base_value: float
    is_anomaly_attributed: bool


class TreeShapExplainer:
    """
    TreeSHAP explainer for tabular MineIsolationForest.
    Generates deterministic, audited Shapley values for geotechnical feature vectors.
    """

    def __init__(self, isoforest: MineIsolationForest):
        self.isoforest = isoforest
        self.explainer: Optional[shap.TreeExplainer] = None
        if self.isoforest.is_fitted:
            self._init_explainer()

    def _init_explainer(self) -> None:
        """Initializes shap.TreeExplainer from underlying IsolationForest."""
        self.explainer = shap.TreeExplainer(self.isoforest.model)

    def explain(self, feature_vector: np.ndarray, top_k: int = 4) -> ShapExplanationResult:
        """
        Computes TreeSHAP attributions for a single 12-D feature vector.
        Guarantees non-empty contributing_sensors list.
        """
        assert feature_vector.ndim == 1, "Expected 1D feature vector"
        assert len(feature_vector) == FEATURE_VECTOR_DIM, f"Expected {FEATURE_VECTOR_DIM} features"

        if self.explainer is None:
            if not self.isoforest.is_fitted:
                raise RuntimeError("Cannot compute TreeSHAP on unfitted IsolationForest model.")
            self._init_explainer()

        X = feature_vector.reshape(1, -1)
        # TreeExplainer on IsolationForest returns array of shape (1, 12)
        raw_shap_values = self.explainer.shap_values(X)
        if isinstance(raw_shap_values, list):
            sv = raw_shap_values[0].flatten()
        elif isinstance(raw_shap_values, np.ndarray):
            sv = raw_shap_values.flatten()
        else:
            sv = np.array(raw_shap_values).flatten()

        raw_base = getattr(self.explainer, "expected_value", 0.0)
        if isinstance(raw_base, (list, np.ndarray)):
            base_val = float(np.ravel(raw_base)[0]) if len(np.ravel(raw_base)) > 0 else 0.0
        else:
            base_val = float(raw_base)

        # In sklearn IsolationForest, lower decision score = more anomalous.
        # TreeSHAP negative values push toward anomalous leaves, or absolute magnitudes measure influence.
        # Rank by absolute magnitude of impact
        attributions: List[FeatureShapValue] = []
        for i, name in enumerate(FEATURE_NAMES):
            val = float(feature_vector[i])
            s_val = float(sv[i])
            sensor = SENSOR_ATTRIBUTION_MAPPING.get(name, "unknown")
            attributions.append(FeatureShapValue(
                feature_name=name,
                shap_value=s_val,
                feature_value=val,
                attributed_sensor=sensor,
            ))

        # Sort descending by absolute attribution magnitude
        attributions.sort(key=lambda x: abs(x.shap_value), reverse=True)

        # Extract top contributing sensors (deduplicated, preserving rank order)
        contributing_sensors: List[str] = []
        top_feature_names: List[str] = []
        for attr in attributions[:top_k]:
            top_feature_names.append(attr.feature_name)
            if attr.attributed_sensor not in contributing_sensors and attr.attributed_sensor != "spatial_topology":
                contributing_sensors.append(attr.attributed_sensor)

        # Fallback to highest ranked physical sensor if only spatial topology was in top_k
        if not contributing_sensors:
            for attr in attributions:
                if attr.attributed_sensor != "spatial_topology":
                    contributing_sensors.append(attr.attributed_sensor)
                    break

        if not contributing_sensors:
            contributing_sensors = ["displacement_mm"]

        return ShapExplanationResult(
            feature_attributions=attributions,
            contributing_sensors=contributing_sensors,
            top_feature_names=top_feature_names,
            base_value=base_val,
            is_anomaly_attributed=True,
        )


class NeuralCaptumExplainer:
    """
    Captum Integrated Gradients explainer for deep neural components (Autoencoder & LSTM).
    Evaluates gradient paths to verify feature salience in non-linear models.
    """

    def __init__(self, model: torch.nn.Module):
        self.model = model
        self.model.eval()
        self.ig = IntegratedGradients(self._forward_wrapper)

    def _forward_wrapper(self, x: torch.Tensor) -> torch.Tensor:
        # Wrapper returning scalar loss / reconstruction error for attribution
        if hasattr(self.model, "encoder"):
            # Autoencoder
            recon = self.model(x)
            mse = torch.mean((recon - x)**2, dim=-1)
            return mse
        else:
            out = self.model(x)
            if isinstance(out, tuple):
                out = out[0]
            return out.sum(dim=-1)

    def attribute(self, input_tensor: torch.Tensor, n_steps: int = 20) -> np.ndarray:
        """Computes integrated gradients attribution."""
        self.model.eval()
        if input_tensor.ndim == 1:
            input_tensor = input_tensor.unsqueeze(0)
        baseline = torch.zeros_like(input_tensor)
        attr, _ = self.ig.attribute(input_tensor, baseline, n_steps=n_steps, return_convergence_delta=True)
        return attr.detach().cpu().numpy().flatten()
