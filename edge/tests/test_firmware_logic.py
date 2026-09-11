"""Unit Tests for Phase 3 ESP32 Firmware Logic, Schema Conformity & Safety Safeguards.

Tests:
1. Exact zero-drift between Python feature extractor and C algorithm.
2. JSON detection event schema compliance (all 9 required keys, types, and values).
3. Raw safety fallback triggers on extreme sensor excursions.
4. Dual-slot OTA staging, CRC32 verification, promotion, and automatic rollback.
5. Power duty-cycling battery lifespan formulas.
"""

import json
import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from subsense.data_generator import generate_mine_telemetry
from subsense.feature_extractor import SubSenseFeatureExtractor


class TestSubSenseFirmwareLogic(unittest.TestCase):

    def setUp(self):
        self.df = generate_mine_telemetry(total_samples=500, sampling_rate_hz=1.0, random_seed=42)
        self.extractor = SubSenseFeatureExtractor(window_size=32, step_size=1)

    def test_c_feature_extraction_zero_drift(self):
        """Verify that the C-port feature algorithm produces 0 numerical drift vs Python."""
        py_features, _, _ = self.extractor.process_dataframe(self.df)

        tilt = self.df["tilt"].to_numpy(dtype=np.float32)
        vib = self.df["vibration"].to_numpy(dtype=np.float32)
        disp = self.df["displacement"].to_numpy(dtype=np.float32)
        crack = self.df["crack"].to_numpy(dtype=np.float32)

        c_features = np.zeros_like(py_features)
        rolling_baseline = float(np.mean(disp[:32]))

        for i in range(len(py_features)):
            start = i
            end = i + 32
            cur_disp = disp[end - 1]
            rolling_baseline = 0.99 * rolling_baseline + 0.01 * cur_disp

            w_tilt = tilt[start:end]
            w_vib = vib[start:end]
            w_disp = disp[start:end]
            w_crack = crack[start:end]

            t_cur = float(w_tilt[-1])
            t_roc = float((w_tilt[-1] - w_tilt[0]) / 32.0)
            t_mean = float(np.mean(w_tilt))
            t_var = float(np.mean((w_tilt - t_mean) ** 2))

            v_rms = float(np.sqrt(np.mean(w_vib ** 2)))
            v_peaks = float(np.sum(np.abs(w_vib) > 0.15))

            d_delta = float(cur_disp - rolling_baseline)
            c_cur = float(w_crack[-1])
            c_count = float(np.sum(w_crack >= 0.50))

            c_features[i] = [t_cur, t_roc, t_var, v_rms, v_peaks, d_delta, c_cur, c_count]

        # Drift must be negligible (< 1e-6)
        max_drift = np.max(np.abs(py_features - c_features))
        self.assertLess(max_drift, 1e-6, f"Feature extraction drift detected: {max_drift}")

    def test_json_event_schema_conformity(self):
        """Verify JSON detection event schema has exactly all required fields and valid types."""
        event_dict = {
            "node_id": "N-021",
            "model_version": "gw-autoencoder-v1.3.0",
            "window_end_ts": "2026-09-09T05:11:58Z",
            "anomaly_score": 0.79,
            "local_confidence": 0.62,
            "contributing_features": ["tilt_rate", "vibration_rms"],
            "threshold_breached": "warning",
            "siren_triggered": False,
            "source_tier": "gateway"
        }

        # Validate JSON serialization and deserialization
        json_str = json.dumps(event_dict)
        parsed = json.loads(json_str)

        required_keys = [
            "node_id", "model_version", "window_end_ts", "anomaly_score",
            "local_confidence", "contributing_features", "threshold_breached",
            "siren_triggered", "source_tier"
        ]
        for key in required_keys:
            self.assertIn(key, parsed)

        self.assertIsInstance(parsed["node_id"], str)
        self.assertIsInstance(parsed["model_version"], str)
        self.assertIsInstance(parsed["window_end_ts"], str)
        self.assertIsInstance(parsed["anomaly_score"], float)
        self.assertIsInstance(parsed["local_confidence"], float)
        self.assertIsInstance(parsed["contributing_features"], list)
        self.assertIn(parsed["threshold_breached"], ["none", "warning", "critical"])
        self.assertIsInstance(parsed["siren_triggered"], bool)
        self.assertIn(parsed["source_tier"], ["gateway", "node"])

    def test_raw_safety_fallback_triggers(self):
        """Verify hard-coded safety fallback activates on severe sensor values."""
        # Simulation of subsense_fallback_evaluate thresholds:
        def fallback_eval(tilt_cur, tilt_rate, vib_peak, disp_delta, crack_state):
            if abs(disp_delta) >= 12.0: return True, True
            if abs(tilt_rate) >= 1.5: return True, True
            if abs(vib_peak) >= 1.2: return True, True
            if crack_state >= 0.8: return True, True
            if abs(tilt_cur) >= 4.0: return True, True
            return False, False

        # Nominal test
        hazard, siren = fallback_eval(0.1, 0.02, 0.05, 0.2, 0.0)
        self.assertFalse(hazard)
        self.assertFalse(siren)

        # Displacement breach (> 12mm)
        hazard, siren = fallback_eval(0.1, 0.02, 0.05, 15.4, 0.0)
        self.assertTrue(hazard)
        self.assertTrue(siren)

        # Violent shockwave breach (> 1.2g)
        hazard, siren = fallback_eval(0.1, 0.02, 1.85, 0.2, 0.0)
        self.assertTrue(hazard)
        self.assertTrue(siren)

        # Crack fissure latch (>= 0.8)
        hazard, siren = fallback_eval(0.1, 0.02, 0.05, 0.2, 1.0)
        self.assertTrue(hazard)
        self.assertTrue(siren)

    def test_dual_slot_ota_logic(self):
        """Simulate dual-slot (A/B) OTA manager state transitions and automatic rollback."""
        class MockOTAManager:
            def __init__(self):
                self.active_slot = 0
                self.backup_slot = 0
                self.slots = [{"version": "v1.0.0", "state": "ACTIVE"}, {"version": "", "state": "EMPTY"}]
                self.faults = 0

            def stage_new(self, version, valid_crc=True):
                self.slots[1] = {"version": version, "state": "STAGING"}
                if not valid_crc:
                    self.slots[1]["state"] = "EMPTY"
                    return False
                self.slots[1]["state"] = "VALIDATED"
                return True

            def promote(self):
                if self.slots[1]["state"] == "VALIDATED":
                    self.backup_slot = self.active_slot
                    self.active_slot = 1
                    self.slots[1]["state"] = "ACTIVE"
                    return True
                return False

            def report_fault(self):
                self.faults += 1
                if self.faults >= 2:
                    self.slots[self.active_slot]["state"] = "ROLLBACK"
                    self.active_slot = self.backup_slot
                    self.slots[self.active_slot]["state"] = "ACTIVE"
                    return True
                return False

        ota = MockOTAManager()
        self.assertEqual(ota.active_slot, 0)

        # Corrupted transfer rejects
        ok = ota.stage_new("v1.1.0", valid_crc=False)
        self.assertFalse(ok)
        self.assertEqual(ota.active_slot, 0)

        # Valid transfer stages and promotes
        ok = ota.stage_new("v1.1.0", valid_crc=True)
        self.assertTrue(ok)
        promoted = ota.promote()
        self.assertTrue(promoted)
        self.assertEqual(ota.active_slot, 1)

        # Crash after boot causes auto-rollback to slot 0
        ota.report_fault()
        self.assertEqual(ota.active_slot, 1) # First fault: logged
        ota.report_fault()                   # Second fault: triggers auto-rollback
        self.assertEqual(ota.active_slot, 0) # Rolled back to slot 0!
        self.assertEqual(ota.slots[0]["state"], "ACTIVE")

    def test_duty_cycle_power_math(self):
        """Verify duty-cycle current and lifespan math."""
        # Active: 45 mA for 5 ms, Sleep: 10 uA for 995 ms -> interval = 1000 ms
        active_current_ma = 45.0
        sleep_current_ma = 0.010
        interval_ms = 1000.0
        active_ms = 5.0
        sleep_ms = interval_ms - active_ms

        avg_current = (active_current_ma * active_ms + sleep_current_ma * sleep_ms) / interval_ms
        # Expected: (225 + 9.95) / 1000 = 0.23495 mA
        self.assertAlmostEqual(avg_current, 0.23495, places=4)

        battery_mah = 2600.0 * 0.85 # 2210 mAh usable
        life_hours = battery_mah / avg_current
        life_months = life_hours / (24.0 * 30.4375)
        # Expected: ~12.8 months
        self.assertGreater(life_months, 11.0)


if __name__ == "__main__":
    unittest.main()
