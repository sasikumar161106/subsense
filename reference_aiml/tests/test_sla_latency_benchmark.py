import pytest
import time
import numpy as np
from datetime import datetime
from data.synthetic_generator import SyntheticSubsidenceDataGenerator
from src.pipeline.inference_pipeline import InferencePipeline
from src.schemas.risk_event_contracts import RiskEvent

def test_full_pipeline_sla_latency_benchmark():
    """
    End-to-End Inference Pipeline SLA Latency Benchmark (Section 11, Table 3).
    Verifies that for a 10-node underground coal mine mesh with 60 sliding window samples,
    the complete inference cycle finishes well within the <= 15-20 second latency SLA.
    """
    gen = SyntheticSubsidenceDataGenerator()
    pipeline = InferencePipeline()

    # Pre-train ensemble on normal baseline for clean inference
    baseline_data = np.random.normal(loc=0.5, scale=0.1, size=(80, 8))
    pipeline.ensemble.fit(baseline_data)

    node_ids = [
        "N-014", "N-015", "N-021", "N-022", "N-030",
        "N-031", "N-040", "N-041", "N-042", "N-FAULTY"
    ]
    active_zone_nodes = ["N-014", "N-015", "N-021"]

    # Generate multi-sensor telemetry batch
    telemetry_map = gen.generate_mesh_telemetry_batch(
        node_ids=node_ids,
        active_zone_nodes=active_zone_nodes,
        n_samples=60,
    )

    node_readings = {nid: telemetry_map[nid][0] for nid in node_ids}
    node_health = {nid: telemetry_map[nid][1] for nid in node_ids}

    node_coords = {
        "N-014": (442420.0, 2631650.0),
        "N-015": (442480.0, 2631680.0),
        "N-021": (442450.0, 2631720.0),
        "N-022": (442550.0, 2631760.0),
        "N-030": (442350.0, 2631550.0),
        "N-031": (442650.0, 2631850.0),
        "N-040": (442250.0, 2631450.0),
        "N-041": (442750.0, 2631950.0),
        "N-042": (442800.0, 2632000.0),
        "N-FAULTY": (442400.0, 2631600.0),
    }
    bounds_utm = (442000.0, 2631200.0, 443000.0, 2632200.0)

    t_start = time.perf_counter()
    results = pipeline.run_inference_cycle(
        site_id="SITE-JHARIA-04",
        node_readings_map=node_readings,
        node_health_map=node_health,
        node_coords_utm=node_coords,
        bounds_utm=bounds_utm,
        utm_epsg=32645,
    )
    duration = time.perf_counter() - t_start

    print(f"\n[BENCHMARK] Full 10-node E2E Inference Duration: {duration:.4f} s (SLA Target: <= 15.0 s)")

    # Assertions
    assert duration <= 15.0, f"Inference duration {duration:.2f}s exceeded 15.0s SLA target!"
    assert results["sla_passed"] is True
    assert results["node_count_analyzed"] == 9  # N-FAULTY was quarantined
    assert "N-FAULTY" in results["quarantined_nodes"]

    # Verify Risk Event formation
    assert len(results["risk_events"]) >= 1
    event = results["risk_events"][0]
    assert isinstance(event, RiskEvent)
    assert event.site_id == "SITE-JHARIA-04"
    assert event.anomaly_score > 0.0
    assert event.correlation_score > 0.0
    assert 0.0 <= event.confidence_score <= 1.0
    assert event.explanation_text is not None and len(event.explanation_text) > 10
    assert len(event.contributing_sensors) >= 1
    assert event.model_versions.anomaly == "cloud-ensemble-v2.1.0"

    # Verify Raster payload
    raster = results["raster_payload"]
    assert raster.site_id == "SITE-JHARIA-04"
    assert raster.utm_epsg == 32645
    assert len(raster.risk_values) > 0
    assert len(raster.variance_values) > 0
