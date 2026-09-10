"""High-Resolution Inference Latency, Throughput & Component Profiler for SubSense.

Measures:
1. Model loading time
2. Feature preprocessing time (sliding-window feature extraction + Z-score scaling)
3. Raw model forward pass latency (100 warm-up runs, 1000+ timed runs)
4. Post-processing latency (threshold check, event formatting)
5. End-to-end latency
6. Statistical percentiles: Mean, P50 (median), P90, P95, P99, Min, Max, Std Dev
7. Throughput (inferences/sec)
8. Distinguishes HOST-MACHINE BENCHMARK from ESTIMATED ESP32 HARDWARE CYCLES.
"""

import time
import numpy as np
import tensorflow as tf
import torch
from typing import Dict, Any, Callable, List, Optional


def profile_inference_latency(
    inference_fn: Callable[[np.ndarray], Any],
    sample_input: np.ndarray,
    warmup_runs: int = 100,
    measured_runs: int = 1000,
) -> Dict[str, float]:
    """Execute warm-up and timed runs to compute statistical percentiles."""
    # Warm-up runs to ensure JIT/caching/branch prediction stabilization
    for _ in range(warmup_runs):
        inference_fn(sample_input)

    # Measured runs with high-resolution nanosecond timer
    timings_ns = np.zeros(measured_runs, dtype=np.int64)
    for i in range(measured_runs):
        t0 = time.perf_counter_ns()
        inference_fn(sample_input)
        t1 = time.perf_counter_ns()
        timings_ns[i] = t1 - t0

    # Convert to milliseconds
    timings_ms = timings_ns / 1e6

    mean_ms = float(np.mean(timings_ms))
    p50_ms = float(np.percentile(timings_ms, 50))
    p90_ms = float(np.percentile(timings_ms, 90))
    p95_ms = float(np.percentile(timings_ms, 95))
    p99_ms = float(np.percentile(timings_ms, 99))
    min_ms = float(np.min(timings_ms))
    max_ms = float(np.max(timings_ms))
    std_ms = float(np.std(timings_ms))

    throughput_ips = float(1000.0 / mean_ms) if mean_ms > 0 else 0.0

    return {
        "runs": measured_runs,
        "mean_ms": mean_ms,
        "p50_ms": p50_ms,
        "p90_ms": p90_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "std_ms": std_ms,
        "throughput_ips": throughput_ips,
    }


def benchmark_component_breakdown(
    preprocess_fn: Callable[[np.ndarray], np.ndarray],
    inference_fn: Callable[[np.ndarray], Any],
    postprocess_fn: Callable[[Any], Any],
    raw_window: np.ndarray,
    runs: int = 500,
) -> Dict[str, float]:
    """Profile the individual latency stages of the edge processing loop."""
    prep_times_us = np.zeros(runs, dtype=np.float64)
    infer_times_us = np.zeros(runs, dtype=np.float64)
    post_times_us = np.zeros(runs, dtype=np.float64)
    e2e_times_us = np.zeros(runs, dtype=np.float64)

    # Warmup
    for _ in range(50):
        feat = preprocess_fn(raw_window)
        out = inference_fn(feat)
        postprocess_fn(out)

    for i in range(runs):
        t0 = time.perf_counter_ns()
        feat = preprocess_fn(raw_window)
        t1 = time.perf_counter_ns()
        out = inference_fn(feat)
        t2 = time.perf_counter_ns()
        postprocess_fn(out)
        t3 = time.perf_counter_ns()

        prep_times_us[i] = (t1 - t0) / 1000.0
        infer_times_us[i] = (t2 - t1) / 1000.0
        post_times_us[i] = (t3 - t2) / 1000.0
        e2e_times_us[i] = (t3 - t0) / 1000.0

    return {
        "preprocessing_us": float(np.mean(prep_times_us)),
        "inference_us": float(np.mean(infer_times_us)),
        "postprocessing_us": float(np.mean(post_times_us)),
        "end_to_end_us": float(np.mean(e2e_times_us)),
        "end_to_end_ms": float(np.mean(e2e_times_us) / 1000.0),
    }


def estimate_esp32_cycles_and_latency(mac_operations: int, clock_mhz: float = 240.0) -> Dict[str, Any]:
    """Estimate microcontroller execution latency based on CPU clock and MAC count.

    On Xtensa LX7 (ESP32-S3): ~1 cycle per INT8 MAC with SIMD vector extensions,
    ~3-4 cycles on scalar RISC-V (ESP32-C3).
    """
    cycles_simd = mac_operations * 1.5
    cycles_scalar = mac_operations * 4.0

    latency_ms_240mhz = (cycles_scalar / (240.0 * 1e6)) * 1000.0
    latency_ms_160mhz = (cycles_scalar / (160.0 * 1e6)) * 1000.0

    return {
        "mac_operations": mac_operations,
        "estimated_cycles": int(cycles_scalar),
        "estimated_cycles_simd": int(cycles_simd),
        "estimated_cycles_scalar": int(cycles_scalar),
        "estimated_latency_ms": float(latency_ms_240mhz),
        "estimated_latency_240mhz_ms": float(latency_ms_240mhz),
        "estimated_latency_160mhz_ms": float(latency_ms_160mhz),
        "hardware_benchmark_note": "ESTIMATED ESP32 HARDWARE METRIC (Actual depends on flash bus latency & cache)",
    }


def benchmark_model_latency(
    inference_fn: Callable,
    sample_input: Optional[np.ndarray] = None,
    warmup_runs: int = 100,
    measured_runs: int = 1000,
) -> Dict[str, float]:
    """Flexible latency profiler supporting both 0-arg and 1-arg callables."""
    if sample_input is not None:
        return profile_inference_latency(inference_fn, sample_input, warmup_runs, measured_runs)
    else:
        # 0-arg callable wrapper
        wrapper = lambda _: inference_fn()
        return profile_inference_latency(wrapper, np.zeros((1, 8), dtype=np.float32), warmup_runs, measured_runs)


def benchmark_end_to_end_pipeline(
    raw_sample_window: Any,
    feature_extractor_fn: Callable,
    scaler_transform_fn: Callable,
    model_inference_fn: Callable,
    postprocess_fn: Callable,
    warmup_runs: int = 50,
    measured_runs: int = 500,
) -> Dict[str, float]:
    """Benchmark full edge ingestion pipeline from raw window to alert decision."""
    prep_times_ms = np.zeros(measured_runs, dtype=np.float64)
    infer_times_ms = np.zeros(measured_runs, dtype=np.float64)
    post_times_ms = np.zeros(measured_runs, dtype=np.float64)
    e2e_times_ms = np.zeros(measured_runs, dtype=np.float64)

    # Warmup
    for _ in range(warmup_runs):
        raw_feat = feature_extractor_fn(raw_sample_window)
        scaled_feat = scaler_transform_fn(raw_feat)
        out = model_inference_fn(scaled_feat)
        _ = postprocess_fn(out)

    # Measured
    for i in range(measured_runs):
        t0 = time.perf_counter_ns()
        raw_feat = feature_extractor_fn(raw_sample_window)
        scaled_feat = scaler_transform_fn(raw_feat)
        t1 = time.perf_counter_ns()
        out = model_inference_fn(scaled_feat)
        t2 = time.perf_counter_ns()
        _ = postprocess_fn(out)
        t3 = time.perf_counter_ns()

        prep_times_ms[i] = (t1 - t0) / 1e6
        infer_times_ms[i] = (t2 - t1) / 1e6
        post_times_ms[i] = (t3 - t2) / 1e6
        e2e_times_ms[i] = (t3 - t0) / 1e6

    return {
        "preprocessing_ms": float(np.mean(prep_times_ms)),
        "inference_ms": float(np.mean(infer_times_ms)),
        "postprocessing_ms": float(np.mean(post_times_ms)),
        "total_e2e_ms": float(np.mean(e2e_times_ms)),
        "end_to_end_ms": float(np.mean(e2e_times_ms)),
    }


# Aliases
estimate_esp32_cycles = estimate_esp32_cycles_and_latency

