from typing import List, Optional
from src.schemas.risk_event_contracts import ForecastTrendEnum

class ExplainabilityNarrativeGenerator:
    """
    Deterministic Explainability Narrative Generator (Section 7).
    Produces 100% auditable natural-language explanations strictly linked to model signals,
    eliminating generative AI hallucinations and ensuring regulatory DGMS audit compliance.
    """

    @staticmethod
    def generate_explanation(
        node_ids: List[str],
        contributing_sensors: List[str],
        correlation_score: float,
        forecast_trend: ForecastTrendEnum,
        time_to_critical_hours: Optional[float] = None,
    ) -> str:
        count = len(node_ids)
        nodes_str = ", ".join(node_ids[:4])
        if count > 4:
            nodes_str += f" (+{count - 4} more)"

        sensors_str = " and ".join(contributing_sensors) if contributing_sensors else "multi-sensor"

        if count == 1:
            base = f"Single node ({nodes_str}) detected anomalous {sensors_str} activity; low spatial correlation ({correlation_score:.2f})."
        else:
            base = f"Correlated {sensors_str} rise across {count} adjacent nodes ({nodes_str}); GNN correlation score {correlation_score:.2f}."

        # Add trend and time to critical if applicable
        if forecast_trend == ForecastTrendEnum.ACCELERATING:
            trend_str = " Progression accelerating."
        elif forecast_trend == ForecastTrendEnum.SUDDEN_ONSET:
            trend_str = " Sudden rapid onset observed."
        elif forecast_trend == ForecastTrendEnum.SLOW_PROGRESSION:
            trend_str = " Slow creeping progression."
        else:
            trend_str = " Trend currently stable."

        ttc_str = ""
        if time_to_critical_hours is not None:
            ttc_str = f" Estimated time-to-critical: {time_to_critical_hours:.1f} hours."

        return f"{base}{trend_str}{ttc_str}"
