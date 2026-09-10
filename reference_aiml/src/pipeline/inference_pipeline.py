from typing import Dict, List, Tuple, Optional, Any
import time
import numpy as np
from datetime import datetime, timezone

from src.schemas.sensor_contracts import SensorReading, NodeHealthMetadata, EngineeredFeatureVector
from src.schemas.risk_event_contracts import RiskEvent, ModelVersionMetadata, ForecastTrendEnum
from src.schemas.gis_interop_contracts import IngestionRasterPayload
from src.ingestion.fault_filter import SensorFaultFilter
from src.ingestion.feature_extractor import FeatureExtractor
from src.models.anomaly_ensemble import AnomalyDetectionEnsemble
from src.models.mesh_gnn_correlator import MeshGNNCorrelator
from src.models.lstm_forecaster import LSTMProgressionForecaster
from src.geostats.ordinary_kriging import OrdinaryKrigingInterpolator
from src.explainability.confidence_scorer import ConfidenceScorer
from src.explainability.narrative_generator import ExplainabilityNarrativeGenerator
from src.feedback_loop.online_calibrator import OnlineCalibrator
from src.feedback_loop.model_registry import ModelRegistry

class InferencePipeline:
    """
    End-to-End Orchestrator for SubSense AI/ML Data Inference Layer (Layer 4).
    Orchestrates the entire real-time analysis pipeline:
    Telemetry -> Fault Filtering -> Feature Extraction -> Anomaly Ensemble ->
    GNN Spatial Correlation -> LSTM Progression Forecasting -> Ordinary Kriging ->
    Confidence & Explainability -> Structured Risk Events & GIS Raster Payload.
    """

    def __init__(
        self,
        fault_filter: Optional[SensorFaultFilter] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
        ensemble: Optional[AnomalyDetectionEnsemble] = None,
        gnn_correlator: Optional[MeshGNNCorrelator] = None,
        lstm_forecaster: Optional[LSTMProgressionForecaster] = None,
        kriging_interpolator: Optional[OrdinaryKrigingInterpolator] = None,
        confidence_scorer: Optional[ConfidenceScorer] = None,
        calibrator: Optional[OnlineCalibrator] = None,
        registry: Optional[ModelRegistry] = None,
    ):
        self.fault_filter = fault_filter or SensorFaultFilter()
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.ensemble = ensemble or AnomalyDetectionEnsemble()
        self.gnn = gnn_correlator or MeshGNNCorrelator()
        self.lstm = lstm_forecaster or LSTMProgressionForecaster()
        self.kriging = kriging_interpolator or OrdinaryKrigingInterpolator()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.calibrator = calibrator or OnlineCalibrator()
        self.registry = registry or ModelRegistry()

    def run_inference_cycle(
        self,
        site_id: str,
        node_readings_map: Dict[str, List[SensorReading]],
        node_health_map: Dict[str, NodeHealthMetadata],
        node_coords_utm: Dict[str, Tuple[float, float]],
        bounds_utm: Tuple[float, float, float, float],
        utm_epsg: int = 32645,
    ) -> Dict[str, Any]:
        """
        Executes a complete inference cycle over the sensor mesh telemetry.
        Returns: {
            "risk_events": List[RiskEvent],
            "raster_payload": IngestionRasterPayload,
            "quarantined_nodes": Dict[str, str],
            "execution_duration_sec": float,
            "sla_passed": bool
        }
        """
        start_time = time.perf_counter()
        cycle_timestamp = datetime.now(timezone.utc)

        # Step 1: Data-Quality & Sensor-Fault Filtering (Section 3.3)
        valid_readings, quarantined = self.fault_filter.filter_mesh_batch(
            node_readings_map=node_readings_map,
            node_health_map=node_health_map,
        )

        # Step 2: Feature Extraction (Section 3.2)
        feature_map = self.feature_extractor.extract_batch(valid_readings)

        # Step 3: Unsupervised Anomaly Detection Ensemble (Section 4)
        scored_nodes = self.ensemble.score_batch(feature_map)
        anomaly_scores = {nid: vals["anomaly_score"] for nid, vals in scored_nodes.items()}

        # Step 4: Graph-Based Spatial Correlation via Mesh GNN (Section 5)
        valid_node_ids = list(valid_readings.keys())
        candidate_zones = self.gnn.correlate(
            node_ids=valid_node_ids,
            node_coords=node_coords_utm,
            feature_map=feature_map,
            anomaly_scores=anomaly_scores,
            site_id=site_id,
        )

        # Active dynamic site threshold from feedback loop
        effective_threshold = self.calibrator.get_effective_threshold(site_id)

        # Active model versions from registry
        active_versions = self.registry.get_active_versions()
        version_meta = ModelVersionMetadata(
            anomaly=active_versions.get("anomaly", self.ensemble.version),
            correlation=active_versions.get("correlation", self.gnn.version),
            forecast=active_versions.get("forecast", self.lstm.version),
        )

        risk_events: List[RiskEvent] = []

        # Step 5: For each identified zone, run LSTM progression and generate Risk Event
        for zone in candidate_zones:
            cluster_nodes = zone["node_ids"]
            corr_score = zone["correlation_score"]
            anom_score = zone["anomaly_score"]

            # Filter insignificant noise clusters unless correlation exceeds threshold
            if corr_score < effective_threshold and len(cluster_nodes) < 2:
                continue

            # Assemble temporal sequence for the cluster
            # [T, 4] -> [tilt, vibration, displacement, anomaly]
            first_node_readings = valid_readings[cluster_nodes[0]]
            seq_len = len(first_node_readings)
            temporal_matrix = np.zeros((seq_len, 4), dtype=np.float32)

            for step_i in range(seq_len):
                tilts = [valid_readings[nid][step_i].tilt_deg for nid in cluster_nodes]
                vibes = [valid_readings[nid][step_i].vibration_g for nid in cluster_nodes]
                disps = [valid_readings[nid][step_i].displacement_mm for nid in cluster_nodes]
                temporal_matrix[step_i, 0] = np.mean(tilts)
                temporal_matrix[step_i, 1] = np.mean(vibes)
                temporal_matrix[step_i, 2] = np.mean(disps)
                temporal_matrix[step_i, 3] = anom_score

            latest_displacement = float(temporal_matrix[-1, 2])

            # Step 5a: LSTM Progression Forecasting (Section 6.1 & 6.3)
            trend, time_to_critical, metrics = self.lstm.forecast_zone(
                temporal_features=temporal_matrix,
                current_displacement_mm=latest_displacement,
            )

            # Determine contributing sensors
            contributing_sensors = []
            mean_tilt = np.mean([feature_map[nid].tilt_mean for nid in cluster_nodes])
            mean_vibe = np.mean([feature_map[nid].vibration_rms for nid in cluster_nodes])
            mean_crack = np.mean([feature_map[nid].crack_active_ratio for nid in cluster_nodes])

            if abs(mean_tilt) > 0.8:
                contributing_sensors.append("tilt")
            if mean_vibe > 0.05:
                contributing_sensors.append("vibration")
            if latest_displacement > 5.0:
                contributing_sensors.append("displacement")
            if mean_crack > 0.0:
                contributing_sensors.append("crack")
            if not contributing_sensors:
                contributing_sensors = ["tilt", "displacement"]

            # Step 5b: Confidence Scoring (Section 7)
            agreements = [scored_nodes[nid]["agreement"] for nid in cluster_nodes]
            mean_agreement = float(np.mean(agreements)) if agreements else 0.8
            confidence = self.confidence_scorer.compute_confidence(
                ensemble_agreement=mean_agreement,
                correlation_score=corr_score,
                num_contributing_nodes=len(cluster_nodes),
            )

            # Step 5c: Explainability Narrative (Section 7)
            explanation = ExplainabilityNarrativeGenerator.generate_explanation(
                node_ids=cluster_nodes,
                contributing_sensors=contributing_sensors,
                correlation_score=corr_score,
                forecast_trend=trend,
                time_to_critical_hours=time_to_critical,
            )

            risk_events.append(
                RiskEvent(
                    site_id=site_id,
                    zone_id=zone["zone_id"],
                    node_ids=cluster_nodes,
                    anomaly_score=float(round(anom_score, 2)),
                    correlation_score=float(round(corr_score, 2)),
                    forecast_trend=trend,
                    time_to_critical_hours=time_to_critical,
                    confidence_score=confidence,
                    contributing_sensors=contributing_sensors,
                    explanation_text=explanation,
                    model_versions=version_meta,
                    event_timestamp=cycle_timestamp,
                )
            )

        # Step 6: Ordinary Kriging Spatial Interpolation for GIS (Section 6.2)
        raster_payload = self.kriging.interpolate_raster(
            site_id=site_id,
            node_coords=node_coords_utm,
            node_values=anomaly_scores,
            bounds_utm=bounds_utm,
            utm_epsg=utm_epsg,
            timestamp=cycle_timestamp,
        )

        duration = time.perf_counter() - start_time
        sla_passed = duration <= 15.0  # Under 15s budget per Table 3 target

        return {
            "risk_events": risk_events,
            "raster_payload": raster_payload,
            "quarantined_nodes": quarantined,
            "node_count_analyzed": len(valid_readings),
            "execution_duration_sec": float(round(duration, 4)),
            "sla_passed": sla_passed,
        }
