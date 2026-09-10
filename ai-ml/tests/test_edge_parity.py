"""
Edge-Cloud Parity and Embedded Constraints Test Suite.
Verifies Section 8 Target: >= 94.0% Agreement Rate between localized TinyML edge
classifications and full cloud ensemble decisions.
Verifies SRAM constraint (< 38KB) and latency benchmark (~4.8ms reference on ESP32-S3).
"""

import numpy as np
import pytest

from features.constants import FEATURE_VECTOR_DIM
from models.anomaly.ensemble import AnomalyEnsemble
from edge_firmware.distillation.distill import TinyMLDistiller
from edge_firmware.hil_harness.hil_benchmark import run_edge_benchmark


def test_edge_cloud_parity_and_sram_constraints():
    """
    Executes end-to-end benchmark:
    1. Distills cloud Autoencoder into int8 3-layer MLP.
    2. Evaluates on shared validation set of 500 samples.
    3. Asserts Parity Agreement Rate >= 94.0%.
    4. Asserts SRAM Memory Footprint < 38KB (38,912 bytes).
    5. Asserts simulated Xtensa LX7 latency benchmark matches ~4.8ms reference.
    """
    benchmark = run_edge_benchmark()

    # 1. Parity Agreement Rate >= 94.0%
    parity = benchmark["parity"]
    agreement_rate = parity["agreement_rate_pct"]
    print(f"\n[Test Parity] Measured Agreement Rate: {agreement_rate:.2f}% (Target: >= 94.0%)")
    assert agreement_rate >= 94.0, f"Edge-cloud parity {agreement_rate}% below 94.0% target!"
    assert parity["meets_target"] is True

    # 2. SRAM Footprint < 38KB
    sram = benchmark["sram_bytes"]
    limit = benchmark["sram_limit_bytes"]
    print(f"[Test SRAM] Measured: {sram} bytes / Limit: {limit} bytes")
    assert sram < limit, f"SRAM footprint {sram} bytes exceeds {limit} bytes limit!"
    assert benchmark["sram_constraint_satisfied"] is True

    # 3. Latency Benchmark within expected range (~4.8ms reference on ESP32-S3 @ 240MHz)
    latency = benchmark["simulated_latency_ms"]
    ref = benchmark["reference_latency_ms"]
    print(f"[Test Latency] Simulated: {latency:.2f} ms / Reference: {ref:.2f} ms")
    assert 4.0 <= latency <= 6.0, f"Latency {latency} ms deviates significantly from reference {ref} ms"
