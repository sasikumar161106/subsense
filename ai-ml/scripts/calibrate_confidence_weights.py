"""
SubSense Layer 4: Confidence Weights Calibration Script.
Optimizes w1 (Model Agreement), w2 (C_corr), and w3 (Q_mesh)
against verified incident ground truth to minimize Brier calibration error.
"""

import os
import sys
import yaml
import numpy as np
from scipy.optimize import minimize
from typing import Dict, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fusion.confidence import ConfidenceScorer



def generate_calibration_dataset(n_samples: int = 200, seed: int = 42):
    """
    Generates synthetic validation incident vectors with known ground truth labels.
    - True collapses: high agreement, high c_corr, varying q_mesh.
    - False alarms / blasts: discordant agreement, isolated c_corr, high q_mesh.
    """
    rng = np.random.default_rng(seed)
    agreements = []
    c_corrs = []
    q_meshes = []
    labels = []

    for _ in range(n_samples):
        is_true = rng.choice([0, 1], p=[0.4, 0.6])
        labels.append(is_true)
        if is_true:
            agreements.append(rng.beta(8, 2))  # Mean ~0.80
            c_corrs.append(rng.beta(7, 2))     # Mean ~0.78
            q_meshes.append(rng.beta(9, 1))    # Mean ~0.90
        else:
            agreements.append(rng.beta(2, 6))  # Mean ~0.25
            c_corrs.append(rng.beta(2, 7))     # Mean ~0.22
            q_meshes.append(rng.beta(6, 2))    # Mean ~0.75

    return (
        np.array(agreements, dtype=float),
        np.array(c_corrs, dtype=float),
        np.array(q_meshes, dtype=float),
        np.array(labels, dtype=float),
    )


def calibrate_weights(
    agreements: np.ndarray,
    c_corrs: np.ndarray,
    q_meshes: np.ndarray,
    labels: np.ndarray,
    initial_w: Tuple[float, float, float] = (0.50, 0.30, 0.20),
) -> Dict[str, float]:
    """
    Solves bounded constrained optimization:
        min sum ( (w1*agr + w2*corr + w3*qos) - label )^2
        s.t. w1 + w2 + w3 = 1.0, w_i in [0.05, 0.85]
    """
    def brier_objective(weights):
        w1, w2, w3 = weights
        pred_conf = w1 * agreements + w2 * c_corrs + w3 * q_meshes
        return np.mean((pred_conf - labels)**2)

    bounds = [(0.10, 0.80), (0.10, 0.60), (0.05, 0.50)]
    constraints = ({'type': 'eq', 'fun': lambda w: w[0] + w[1] + w[2] - 1.0})

    res = minimize(
        brier_objective,
        x0=np.array(initial_w),
        method='SLSQP',
        bounds=bounds,
        constraints=constraints,
    )

    opt_w1, opt_w2, opt_w3 = res.x
    total = opt_w1 + opt_w2 + opt_w3
    opt_w1, opt_w2, opt_w3 = opt_w1 / total, opt_w2 / total, opt_w3 / total

    return {
        "w1_agreement": float(round(opt_w1, 4)),
        "w2_correlation": float(round(opt_w2, 4)),
        "w3_qos": float(round(opt_w3, 4)),
        "brier_score": float(round(res.fun, 6)),
        "success": bool(res.success),
    }


def main():
    print("=== SubSense Confidence Scoring Calibration Engine ===")
    agreements, c_corrs, q_meshes, labels = generate_calibration_dataset()
    print(f"Calibration dataset size: {len(labels)} incidents")

    results = calibrate_weights(agreements, c_corrs, q_meshes, labels)
    print("Optimization Completed:")
    print(f"  w1 (Model Agreement): {results['w1_agreement']}")
    print(f"  w2 (Cross-Correlation): {results['w2_correlation']}")
    print(f"  w3 (Mesh QoS): {results['w3_qos']}")
    print(f"  Final Brier Calibration Loss: {results['brier_score']}")


if __name__ == "__main__":
    main()
