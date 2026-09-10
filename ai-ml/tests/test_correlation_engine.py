"""
Cross-Sensor and Cross-Node Rule-Based Correlation Engine Test Suite.
Verifies multi-channel consistency checks, predictive maintenance routing,
spatio-temporal neighbor corroboration (R <= 120m, tau <= 45 min),
isolated node down-weighting (0.25x), and C_corr in [0.0, 1.0].
"""

from datetime import datetime, timezone, timedelta
import pytest

from correlation.engine import CrossCorrelationEngine, SensorDeltas


@pytest.fixture
def engine():
    return CrossCorrelationEngine(
        delta_tilt_min_deg=0.15,
        delta_displacement_min_mm=1.5,
        neighbor_radius_m=120.0,
        temporal_window_min=45.0,
        isolated_penalty_factor=0.25,
    )


def test_single_channel_spike_routes_to_predictive_maintenance(engine):
    """
    Scenario: Large tilt spike (0.45 deg > 0.15 deg), but displacement and other channels flat.
    Expected: Routed to Predictive Maintenance Queue, flagged as sensor fault, suppressed from alert path.
    """
    now = datetime(2026, 9, 9, 4, 15, 0, tzinfo=timezone.utc)
    deltas = SensorDeltas(
        delta_tilt_deg=0.45,           # High spike (> 0.15)
        delta_displacement_mm=0.10,    # Flat (< 1.5)
        delta_vibration_rms_mm_s=1.0,  # Flat (< 10)
        delta_crack_index=0.005,       # Flat (< 0.05)
    )

    res = engine.evaluate(
        node_id="SS-PANEL7-N042",
        timestamp=now,
        lat=23.791204,
        lon=86.433129,
        raw_anomaly_score=0.88,
        deltas=deltas,
    )

    assert res.is_multi_channel_concordant is False
    assert res.concordant_channel_count == 1
    assert res.sensor_fault_flag is True
    assert res.true_movement_flag is False
    assert res.routing_destination == "PREDICTIVE_MAINTENANCE_QUEUE"
    assert res.corroborated_score < 0.30  # Down-weighted by 0.25
    assert 0.0 <= res.corroboration_coefficient <= 1.0


def test_concordant_drift_but_isolated_node(engine):
    """
    Scenario: Multi-channel drift (Delta tilt = 0.22 > 0.15 AND Delta disp = 2.4 > 1.5 mm).
    However, no neighboring nodes within 120m have reported anomalies.
    Expected: Down-weighted by 0.25 factor due to lack of spatial corroboration.
    """
    now = datetime(2026, 9, 9, 4, 15, 0, tzinfo=timezone.utc)
    deltas = SensorDeltas(
        delta_tilt_deg=0.22,           # Concordant
        delta_displacement_mm=2.40,    # Concordant
        delta_vibration_rms_mm_s=2.0,
        delta_crack_index=0.01,
    )

    res = engine.evaluate(
        node_id="SS-PANEL7-N042",
        timestamp=now,
        lat=23.791204,
        lon=86.433129,
        raw_anomaly_score=0.80,
        deltas=deltas,
    )

    assert res.is_multi_channel_concordant is True
    assert res.concordant_channel_count == 2
    assert res.is_isolated_node is True
    assert res.active_neighbor_count == 0
    assert res.true_movement_flag is True
    # Down-weighted by isolated penalty factor 0.25: 0.80 * 0.25 = 0.20
    assert pytest.approx(res.corroborated_score, 0.01) == 0.20
    assert 0.0 <= res.corroboration_coefficient <= 1.0


def test_fully_corroborated_alert_escalation(engine):
    """
    Scenario: Multi-channel drift AND neighboring node within 75m (<120m) reported anomaly 10 min ago (<45 min).
    Expected: Corroboration confirmed, full score retained, routed to ALERT_ESCALATION_PATH.
    """
    t0 = datetime(2026, 9, 9, 4, 10, 0, tzinfo=timezone.utc)
    # Register neighboring node N041 anomaly (at ~75m distance)
    # 0.0006 deg lat ~ 67m
    engine.register_event(
        node_id="SS-PANEL7-N041",
        timestamp=t0,
        lat=23.791800,
        lon=86.433129,
        anomaly_score=0.85,
        is_anomaly=True,
    )

    # 10 minutes later, local node N042 triggers with concordant multi-channel drift
    t1 = t0 + timedelta(minutes=10)
    deltas = SensorDeltas(
        delta_tilt_deg=0.28,           # Concordant
        delta_displacement_mm=3.80,    # Concordant
        delta_vibration_rms_mm_s=12.0, # Concordant
        delta_crack_index=0.08,        # Concordant
    )

    res = engine.evaluate(
        node_id="SS-PANEL7-N042",
        timestamp=t1,
        lat=23.791204,
        lon=86.433129,
        raw_anomaly_score=0.92,
        deltas=deltas,
    )

    assert res.is_multi_channel_concordant is True
    assert res.concordant_channel_count == 4
    assert res.is_isolated_node is False
    assert res.active_neighbor_count == 1
    assert res.routing_destination == "ALERT_ESCALATION_PATH"
    assert res.corroborated_score == 0.92  # Score preserved!
    assert res.corroboration_coefficient >= 0.50
    assert 0.0 <= res.corroboration_coefficient <= 1.0
    assert "CONFIRMED GROUND MOVEMENT" in res.plain_language_summary
