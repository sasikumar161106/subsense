"""
SubSense TinyML — Robustness & Fault Tolerance Evaluator
Evaluates model behavior under real-world coal mine sensor degradations:
1. Missing sensor values / packet dropouts (5%, 10%, 20%)
2. Sensor noise injection (tilt, vibration, displacement)
3. Sensor failure modes (stuck sensor, zero sensor, extreme spike, missing crack sensor)
"""

import os
import copy
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Callable
from evaluation.metrics import compute_classification_metrics


def simulate_missing_values(
    X_raw: np.ndarray,
    missing_rate: float,
    seed: int = 42
) -> np.ndarray:
    """
    Simulate random sensor packet loss / missing readings.
    Missing readings are imputed with 0.0 (baseline/neutral in raw space).
    """
    if missing_rate <= 0.0:
        return X_raw.copy()
    rng = np.random.default_rng(seed)
    mask = rng.random(X_raw.shape) < missing_rate
    X_corrupted = X_raw.copy()
    X_corrupted[mask] = 0.0
    return X_corrupted


def simulate_sensor_noise(
    X_raw: np.ndarray,
    noise_std: float,
    feature_indices: List[int] = None,
    seed: int = 42
) -> np.ndarray:
    """
    Inject zero-mean Gaussian sensor noise into designated features.
    Standard deviations are scaled relative to each feature's natural variance.
    """
    if noise_std <= 0.0:
        return X_raw.copy()
    rng = np.random.default_rng(seed)
    X_noisy = X_raw.copy()
    
    if feature_indices is None:
        # Default: tilt (0, 1, 2), vibration (3, 4), displacement (5)
        feature_indices = [0, 1, 2, 3, 4, 5]
        
    for idx in feature_indices:
        feat_std = np.std(X_raw[:, idx])
        scale = max(feat_std * noise_std, 1e-4)
        noise = rng.normal(0.0, scale, size=X_raw.shape[0])
        X_noisy[:, idx] += noise
        
    return X_noisy


def simulate_sensor_failure(
    X_raw: np.ndarray,
    failure_type: str
) -> np.ndarray:
    """
    Simulate hard sensor failures:
    - 'stuck_tilt': Tilt sensor frozen at a constant neutral reading
    - 'zero_displacement': Displacement wire/sensor detached (reads 0 delta)
    - 'extreme_vibration': Outlier vibration noise spike from nearby blasting/drilling
    - 'missing_crack': Crack sensor wire cut (crack state and count = 0)
    """
    X_fail = X_raw.copy()
    if failure_type == "stuck_tilt":
        # Indices 0, 1, 2 frozen at 0 (neutral baseline)
        X_fail[:, 0] = 0.0
        X_fail[:, 1] = 0.0
        X_fail[:, 2] = 0.0
    elif failure_type == "zero_displacement":
        # Index 5 set to 0.0
        X_fail[:, 5] = 0.0
    elif failure_type == "extreme_vibration":
        # Sudden 5x vibration spikes on 10% of samples
        rng = np.random.default_rng(42)
        spike_mask = rng.random(X_fail.shape[0]) < 0.10
        max_vib = np.max(X_fail[:, 3]) if np.max(X_fail[:, 3]) > 0 else 1.0
        X_fail[spike_mask, 3] = max_vib * 5.0
        X_fail[spike_mask, 4] = np.max(X_fail[:, 4]) * 3.0
    elif failure_type == "missing_crack":
        # Crack state (6) and crack count (7) set to 0
        X_fail[:, 6] = 0.0
        X_fail[:, 7] = 0.0
    else:
        raise ValueError(f"Unknown failure_type: {failure_type}")
        
    return X_fail


def evaluate_robustness(
    predict_fn: Callable[[np.ndarray], np.ndarray],
    X_raw_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str = "Model",
    noise_levels: List[float] = [0.0, 0.01, 0.05, 0.10, 0.20],
    missing_rates: List[float] = [0.0, 0.05, 0.10, 0.20]
) -> Dict[str, Any]:
    """
    Comprehensive robustness evaluation across missing rates, noise levels, and sensor failure modes.
    predict_fn accepts raw feature matrix X_raw and returns binary predictions (0 or 1).
    """
    results = {
        "model_name": model_name,
        "baseline": None,
        "missing_values": {},
        "sensor_noise": {},
        "sensor_failures": {}
    }
    
    # 1. Baseline
    y_pred_base = predict_fn(X_raw_test)
    base_metrics = compute_classification_metrics(y_test, y_pred_base)
    results["baseline"] = base_metrics
    
    # 2. Missing Value Dropout
    for rate in missing_rates:
        X_corrupted = simulate_missing_values(X_raw_test, missing_rate=rate)
        y_pred = predict_fn(X_corrupted)
        m = compute_classification_metrics(y_test, y_pred)
        results["missing_values"][f"{int(rate*100)}%"] = {
            "dropout_rate": rate,
            "recall": m["recall"],
            "precision": m["precision"],
            "f1_score": m["f1_score"],
            "fpr": m["false_positive_rate"]
        }
        
    # 3. Sensor Noise Injection
    for noise in noise_levels:
        X_noisy = simulate_sensor_noise(X_raw_test, noise_std=noise)
        y_pred = predict_fn(X_noisy)
        m = compute_classification_metrics(y_test, y_pred)
        results["sensor_noise"][f"sigma_{noise}"] = {
            "noise_std": noise,
            "recall": m["recall"],
            "precision": m["precision"],
            "f1_score": m["f1_score"],
            "fpr": m["false_positive_rate"]
        }
        
    # 4. Sensor Failure Modes
    failure_types = ["stuck_tilt", "zero_displacement", "extreme_vibration", "missing_crack"]
    for ft in failure_types:
        X_fail = simulate_sensor_failure(X_raw_test, failure_type=ft)
        y_pred = predict_fn(X_fail)
        m = compute_classification_metrics(y_test, y_pred)
        results["sensor_failures"][ft] = {
            "failure_type": ft,
            "recall": m["recall"],
            "precision": m["precision"],
            "f1_score": m["f1_score"],
            "fpr": m["false_positive_rate"]
        }
        
    return results


def plot_robustness_comparison(
    node_robustness: Dict[str, Any],
    gateway_robustness: Dict[str, Any],
    save_path: str = "evaluation/results/plots/robustness_noise_performance.png"
):
    """
    Generate side-by-side plots of robustness performance:
    - Left: Recall & F1 vs Sensor Noise
    - Right: Recall & F1 vs Missing Data Rate
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    
    # 1. Noise Performance
    node_noise = node_robustness["sensor_noise"]
    gw_noise = gateway_robustness["sensor_noise"]
    
    sigmas = [v["noise_std"] for v in node_noise.values()]
    node_rec = [v["recall"] for v in node_noise.values()]
    node_f1 = [v["f1_score"] for v in node_noise.values()]
    gw_rec = [v["recall"] for v in gw_noise.values()]
    gw_f1 = [v["f1_score"] for v in gw_noise.values()]
    
    ax0 = axes[0]
    ax0.plot(sigmas, node_rec, 'o-', color='#10b981', linewidth=2.2, label='Node Recall')
    ax0.plot(sigmas, node_f1, 's--', color='#059669', linewidth=1.8, label='Node F1')
    ax0.plot(sigmas, gw_rec, '^--', color='#3b82f6', linewidth=2.2, label='Gateway Recall')
    ax0.plot(sigmas, gw_f1, 'd:', color='#1d4ed8', linewidth=1.8, label='Gateway F1')
    ax0.set_xlabel("Noise Std Deviation (Relative σ)", fontsize=11, fontweight='bold')
    ax0.set_ylabel("Metric Value (0 - 1.0)", fontsize=11, fontweight='bold')
    ax0.set_title("Model Resilience vs Sensor Gaussian Noise", fontsize=12, fontweight='bold')
    ax0.grid(True, linestyle='--', alpha=0.4)
    ax0.legend(loc='lower left')
    ax0.set_ylim(-0.05, 1.05)
    
    # 2. Missing Value Performance
    node_miss = node_robustness["missing_values"]
    gw_miss = gateway_robustness["missing_values"]
    
    drop_rates = [v["dropout_rate"] * 100 for v in node_miss.values()]
    node_rec_m = [v["recall"] for v in node_miss.values()]
    node_f1_m = [v["f1_score"] for v in node_miss.values()]
    gw_rec_m = [v["recall"] for v in gw_miss.values()]
    gw_f1_m = [v["f1_score"] for v in gw_miss.values()]
    
    ax1 = axes[1]
    ax1.plot(drop_rates, node_rec_m, 'o-', color='#10b981', linewidth=2.2, label='Node Recall')
    ax1.plot(drop_rates, node_f1_m, 's--', color='#059669', linewidth=1.8, label='Node F1')
    ax1.plot(drop_rates, gw_rec_m, '^--', color='#3b82f6', linewidth=2.2, label='Gateway Recall')
    ax1.plot(drop_rates, gw_f1_m, 'd:', color='#1d4ed8', linewidth=1.8, label='Gateway F1')
    ax1.set_xlabel("Missing Data Dropout Rate (%)", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Metric Value (0 - 1.0)", fontsize=11, fontweight='bold')
    ax1.set_title("Model Resilience vs Sensor Packet Loss", fontsize=12, fontweight='bold')
    ax1.grid(True, linestyle='--', alpha=0.4)
    ax1.legend(loc='lower left')
    ax1.set_ylim(-0.05, 1.05)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
