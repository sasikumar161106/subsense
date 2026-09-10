import pytest
from src.explainability.confidence_scorer import ConfidenceScorer
from src.explainability.narrative_generator import ExplainabilityNarrativeGenerator
from src.schemas.risk_event_contracts import ForecastTrendEnum

def test_confidence_scorer():
    scorer = ConfidenceScorer()

    # 1 node, weak agreement, weak correlation
    c1 = scorer.compute_confidence(ensemble_agreement=0.4, correlation_score=0.3, num_contributing_nodes=1)
    assert 0.05 <= c1 <= 0.99

    # 4 nodes, high agreement, high GNN correlation
    c2 = scorer.compute_confidence(ensemble_agreement=0.95, correlation_score=0.90, num_contributing_nodes=4)
    assert 0.05 <= c2 <= 0.99
    assert c2 > c1

def test_explainability_narrative_generator():
    text = ExplainabilityNarrativeGenerator.generate_explanation(
        node_ids=["N-014", "N-015", "N-021"],
        contributing_sensors=["tilt", "vibration", "crack"],
        correlation_score=0.76,
        forecast_trend=ForecastTrendEnum.ACCELERATING,
        time_to_critical_hours=36.5,
    )

    assert "Correlated tilt and vibration and crack rise across 3 adjacent nodes" in text
    assert "N-014, N-015, N-021" in text
    assert "GNN correlation score 0.76" in text
    assert "accelerating" in text.lower()
    assert "36.5 hours" in text
