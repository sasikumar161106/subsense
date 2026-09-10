"""
SubSense Layer 4 Explainability Package.
"""

from .shap_explainer import TreeShapExplainer, NeuralCaptumExplainer, ShapExplanationResult, FeatureShapValue
from .attention_extractor import GATAttentionExtractor, GATAttentionSummary, AttentionEdgeAttribution
from .summary_generator import GeotechnicalSummaryGenerator
from .alert_schema import (
    ValidatedAlertEvent,
    IncompleteExplainabilityAlertError,
    validate_and_gate_alert,
)

__all__ = [
    "TreeShapExplainer",
    "NeuralCaptumExplainer",
    "ShapExplanationResult",
    "FeatureShapValue",
    "GATAttentionExtractor",
    "GATAttentionSummary",
    "AttentionEdgeAttribution",
    "GeotechnicalSummaryGenerator",
    "ValidatedAlertEvent",
    "IncompleteExplainabilityAlertError",
    "validate_and_gate_alert",
]
