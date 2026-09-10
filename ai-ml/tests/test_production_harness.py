"""
Unit tests for SubSense Section 8 Production Verification Harness.
Verifies honest metric reporting, status evaluation (PASSED/FAILED/INSUFFICIENT_DATA),
and cryptographic report signing.
"""

import json
import os
import numpy as np
import pytest

from verification.production_harness import (
    MetricStatus,
    ProductionVerificationHarness,
    ProductionVerificationReport,
)


class TestProductionHarness:
    def test_insufficient_data_reported_honestly_for_rare_events(self):
        harness = ProductionVerificationHarness()
        # Only 3 rare catastrophic events (below required sample size of 10)
        gt = [1, 1, 1, 0, 0, 0]
        pred = [1, 1, 1, 0, 0, 0]

        results = harness.evaluate_recall_precision(gt, pred, min_positive_samples=10)
        assert len(results) == 2
        for r in results:
            assert r.status == MetricStatus.INSUFFICIENT_DATA
            assert r.measured_value is None
            assert "Cannot substantiate" in r.details or "Insufficient" in r.details

    def test_recall_and_precision_passed_when_data_sufficient(self):
        harness = ProductionVerificationHarness()
        # 100 benchmark events: 49 positive, 51 negative; all predicted correctly
        gt = [1] * 49 + [0] * 51
        pred = [1] * 49 + [0] * 51

        results = harness.evaluate_recall_precision(gt, pred, min_positive_samples=10)
        rec = results[0]
        prec = results[1]
        assert rec.status == MetricStatus.PASSED
        assert rec.measured_value == 1.0
        assert prec.status == MetricStatus.PASSED
        assert prec.measured_value == 1.0

    def test_lead_time_evaluation(self):
        harness = ProductionVerificationHarness(target_lead_time_hours=8.0)
        # 10 events with median lead time 10.5h
        lead_times = [8.5, 9.0, 10.0, 10.5, 11.0, 11.5, 12.0, 8.2, 10.8, 14.0]
        res = harness.evaluate_warning_lead_time(lead_times, min_events=5)
        assert res.status == MetricStatus.PASSED
        assert res.measured_value >= 8.0

    def test_pdr_and_ece_and_edge_parity(self):
        harness = ProductionVerificationHarness()
        # PDR
        pdr_res = harness.evaluate_packet_delivery(received_packets=980, expected_packets=1000)
        assert pdr_res.status == MetricStatus.PASSED
        assert pdr_res.measured_value == 0.98

        # ECE
        ece_res = harness.evaluate_forecast_calibration(observed_ece=0.0452)
        assert ece_res.status == MetricStatus.PASSED
        assert ece_res.measured_value == 0.0452

        # Edge/Cloud Parity
        edge_scores = np.array([0.20, 0.45, 0.70, 0.85, 0.10])
        cloud_scores = np.array([0.21, 0.46, 0.69, 0.84, 0.11])
        parity_res = harness.evaluate_edge_cloud_parity(edge_scores, cloud_scores, tolerance=0.05)
        assert parity_res.status == MetricStatus.PASSED
        assert parity_res.measured_value == 1.0

    def test_signed_report_generation(self, tmp_path):
        harness = ProductionVerificationHarness()
        targets = [
            harness.evaluate_forecast_calibration(observed_ece=0.0452),
            harness.evaluate_packet_delivery(received_packets=980, expected_packets=1000),
        ]

        report = harness.generate_report(targets, report_dir=str(tmp_path))
        assert isinstance(report, ProductionVerificationReport)
        assert report.overall_status == "FULLY_PASSED"
        assert len(report.report_sha256_signature) == 64

        json_path = tmp_path / "PRODUCTION_VERIFICATION_REPORT.json"
        md_path = tmp_path / "PRODUCTION_VERIFICATION_REPORT.md"
        assert json_path.exists()
        assert md_path.exists()
