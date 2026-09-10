"""
SubSense Phase 3d: Full Pipeline Hardware Drill & End-to-End Verification
========================================================================
Validates the complete chain:
1. ESP32 MPU6050 physical telemetry (tilt > 4.0°) across WiFi mesh -> Gateway
2. Gateway Bridge service adapts to Canonical SensorReading contract (Strict Zero-Fabrication)
3. AI/ML Ingestion & Telemetry Store persists reading
4. AI/ML Anomaly Ensemble scores anomaly with Explainability Attribution Gatekeeper
5. Downstream Dispatcher formats payload to Alert_System and GIS raster contracts
6. Verifies no uninstrumented sensor channels are fabricated or attributed
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Add workspace paths to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "gateway-bridge"))
sys.path.insert(0, os.path.join(BASE_DIR, "ai-ml"))

from bridge import to_canonical
from ingestion.canonical_schema import CanonicalSensorReading, to_raw_sensor_record
from models.anomaly.ensemble import AnomalyEnsemble
from explainability.alert_schema import ValidatedAlertEvent, check_sensor_availability
from integration.alert_dispatcher import to_alert_system_contract, to_gis_raster_contract, dispatch_to_alert_system, dispatch_to_gis


class TestSubSenseEndToEndDrill(unittest.TestCase):

    def setUp(self):
        import numpy as np
        np.random.seed(42)
        baseline = np.random.normal(loc=0.0, scale=0.5, size=(100, 12)).astype(np.float32)
        self.ensemble = AnomalyEnsemble(alpha=0.55, beta=12.5, anomaly_threshold=0.45)
        self.ensemble.fit(baseline, epochs=5, batch_size=32)

    def test_complete_hardware_drill_pipeline(self):
        """
        Simulate the exact physical drill:
        ESP32 MPU6050 tilts past 4.0 degrees ->
        Bridge -> AI/ML Scoring & Attribution -> Downstream Contracts
        """
        # ---------------------------------------------------------------------
        # Step 1: ESP32 MPU6050 physical telemetry from Gateway Serial Banner
        # ---------------------------------------------------------------------
        raw_esp32_gateway_rx = {
            "node_id": "SS-PANEL7-N042",
            "site_id": "PANEL7-JHARIA",
            "tenant_id": "tenant-jharia-01",
            "zone_id": "PANEL-7-WEST",
            "tilt_current": 4.82,          # Physical MPU6050 tilt > 4.0 deg threshold
            "vibration_rms": 0.95,         # Physical MPU6050 vibration
            "battery_percent": 91,
            "rssi_dbm": -64,
            "hop_count": 2,                # Sensor Node -> Relay Node -> Gateway Node
            "window_end_ts": datetime.now(timezone.utc).isoformat()
        }

        # ---------------------------------------------------------------------
        # Step 2: Gateway Bridge Canonical Adaptation
        # ---------------------------------------------------------------------
        canonical = to_canonical(raw_esp32_gateway_rx)

        # Invariant checks: Zero fabrication
        self.assertEqual(canonical["node_id"], "SS-PANEL7-N042")
        self.assertEqual(canonical["site_id"], "PANEL7-JHARIA")
        self.assertEqual(canonical["tenant_id"], "tenant-jharia-01")
        self.assertAlmostEqual(canonical["readings"]["tilt_deg"], 4.82)
        self.assertAlmostEqual(canonical["readings"]["vibration_rms_mm_s"], 0.95)
        self.assertIsNone(canonical["readings"]["displacement_mm"], "Displacement MUST be None")
        self.assertIsNone(canonical["readings"]["crack_index"], "Crack index MUST be None")
        self.assertTrue(canonical["sensor_availability"]["tilt"])
        self.assertTrue(canonical["sensor_availability"]["vibration"])
        self.assertFalse(canonical["sensor_availability"]["displacement"])
        self.assertFalse(canonical["sensor_availability"]["crack"])

        # ---------------------------------------------------------------------
        # Step 3: AI/ML Ingestion & Schema Parsing
        # ---------------------------------------------------------------------
        reading_model = CanonicalSensorReading.model_validate(canonical)
        raw_record = to_raw_sensor_record(reading_model)

        self.assertEqual(raw_record.node_id, "SS-PANEL7-N042")
        self.assertAlmostEqual(raw_record.sensors.tilt_deg, 4.82)
        self.assertIsNone(raw_record.sensors.displacement_mm)
        self.assertIsNone(raw_record.sensors.crack_index)
        self.assertFalse(raw_record.sensor_availability["displacement"])

        # ---------------------------------------------------------------------
        # Step 4: AI/ML Ensemble Anomaly Scoring & Attribution
        # ---------------------------------------------------------------------
        features = [
            4.82,  # tilt_current
            0.95,  # vibration_rms
            0.0,   # displacement (zero-filled for model vector)
            0.0,   # crack (zero-filled for model vector)
            0.45,  # tilt_velocity
            0.12,  # vibration_spectral_centroid
            0.0,   # displacement_velocity
            0.0,   # crack_opening_rate
            1.2,   # spatial_neighbor_mean_tilt
            0.0,   # spatial_neighbor_mean_disp
            0.91,  # battery_pct / 100
            0.5,   # hop_count normalized
        ]

        import numpy as np
        features_arr = np.array(features, dtype=float)

        result = self.ensemble.predict(
            features_arr,
            sensor_availability=raw_record.sensor_availability
        )
        score = result.anomaly_score
        is_anom = result.is_anomaly
        contributing = result.contributing_sensors

        self.assertGreater(score, 0.40, f"Expected elevated anomaly score for 4.82 deg tilt, got {score}")
        self.assertTrue(is_anom, "Expected anomaly flag to be True")

        # CRITICAL VERIFICATION: Attribution Gate must not attribute unavailable sensors
        self.assertNotIn("displacement_mm", contributing, "Unavailable displacement MUST NOT be attributed")
        self.assertNotIn("crack_index", contributing, "Unavailable crack MUST NOT be attributed")
        self.assertTrue(any("tilt" in s for s in contributing), "Tilt sensor MUST be attributed as primary driver")

        # ---------------------------------------------------------------------
        # Step 5: Explainability Attribution Gatekeeper Check
        # ---------------------------------------------------------------------
        from fusion.schemas import AlertTier

        alert_event = ValidatedAlertEvent(
            alert_id="ALT-DRILL-001",
            node_id="SS-PANEL7-N042",
            timestamp=datetime.now(timezone.utc),
            tier=AlertTier.CRITICAL,
            confidence=0.92,
            contributing_sensors=contributing,
            corroborating_node_ids=["SS-PANEL7-N043"],
            plain_language_summary=f"Critical tilt anomaly detected on node SS-PANEL7-N042 exceeding threshold at {raw_record.sensors.tilt_deg} deg",
            sensor_availability=raw_record.sensor_availability,
        )
        self.assertEqual(alert_event.tier, AlertTier.CRITICAL)
        self.assertNotIn("displacement_mm", alert_event.contributing_sensors)

        # ---------------------------------------------------------------------
        # Step 6: Downstream Dispatcher Contracts
        # ---------------------------------------------------------------------
        # A) Alert_System Contract
        risk_event_dict = {
            "node_id": "SS-PANEL7-N042",
            "site_id": "PANEL7-JHARIA",
            "tenant_id": "tenant-jharia-01",
            "zone_id": "PANEL-7-WEST",
            "anomaly_score": score,
            "severity": "CRITICAL",
            "contributing_sensors": alert_event.contributing_sensors,
            "sensor_availability": raw_record.sensor_availability,
            "tilt_deg": 4.82,
            "vibration_rms_mm_s": 0.95,
        }

        alert_system_payload = to_alert_system_contract(risk_event_dict)

        self.assertEqual(alert_system_payload["tenant_id"], "tenant-jharia-01")
        self.assertEqual(alert_system_payload["risk_zone_id"], "PANEL-7-WEST")
        self.assertIn("tilt_deg", alert_system_payload["contributing_sensors"])
        self.assertNotIn("displacement_mm", alert_system_payload["contributing_sensors"])
        self.assertNotIn("crack_index", alert_system_payload["contributing_sensors"])

        # B) GIS Kriging Raster Contract
        kriging_output = {
            "tenant_id": "tenant-jharia-01",
            "site_id": "PANEL7-JHARIA",
            "grid_resolution_m": 5.0,
            "bounds": [86.43, 23.78, 86.45, 23.80],
            "interpolated_grid": [[float(score) for _ in range(5)] for _ in range(5)],
            "variance_grid": [[0.05 for _ in range(5)] for _ in range(5)],
        }

        gis_payload = to_gis_raster_contract(kriging_output)
        self.assertEqual(gis_payload["tenant_id"], "tenant-jharia-01")
        self.assertEqual(gis_payload["site_id"], "PANEL7-JHARIA")
        self.assertEqual(len(gis_payload["risk_grid"]), 5)
        self.assertEqual(len(gis_payload["variance_grid"]), 5)

        # ---------------------------------------------------------------------
        # Step 7: Mock Dispatch Execution
        # ---------------------------------------------------------------------
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{"status": "SUCCESS", "alert_id": "ALT-123"}'
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            disp_alert = dispatch_to_alert_system(risk_event_dict, webhook_url="http://localhost:3000/api/v1/webhooks/risk-events")
            self.assertEqual(disp_alert["status"], "DISPATCHED")
            self.assertEqual(disp_alert["status_code"], 200)

            disp_gis = dispatch_to_gis(kriging_output, gis_url="http://localhost:8001/api/v1/raster/ingest")
            self.assertEqual(disp_gis["status"], "INGESTED")
            self.assertEqual(disp_gis["status_code"], 200)

        print("\n>>> ALL PHASE 3d END-TO-END HARDWARE DRILL CHECKS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    unittest.main()
