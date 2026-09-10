"""Threshold Sweep, ROC/PR Curves, and Score Distribution Analysis for SubSense.

Generates:
1. Multi-step threshold sweep (0.02 to 0.98) computing Precision, Recall, F1, FPR, FNR.
2. Saves results to `evaluation/results/threshold_analysis.csv`.
3. Plots:
   - `roc_curve.png`
   - `precision_recall_curve.png`
   - `f1_vs_threshold.png`
   - `recall_vs_threshold.png`
   - `precision_recall_vs_threshold.png`
   - `score_distribution.png`
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, precision_recall_curve, auc, average_precision_score
from typing import Dict, Any, Tuple, List, Optional


def perform_threshold_sweep(
    y_true: np.ndarray,
    scores: np.ndarray,
    model_name: str,
    steps: int = 100,
) -> pd.DataFrame:
    """Evaluate performance across 100 candidate thresholds from min to max score."""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores).astype(float)

    # Normalize scores to 0-1 range if needed
    min_s = float(np.min(scores))
    max_s = float(np.max(scores))
    if max_s > min_s:
        norm_scores = (scores - min_s) / (max_s - min_s)
    else:
        norm_scores = scores

    thresholds = np.linspace(0.01, 0.99, steps)
    records = []

    for th in thresholds:
        preds = (norm_scores >= th).astype(int)
        tp = np.sum((preds == 1) & (y_true == 1))
        fp = np.sum((preds == 1) & (y_true == 0))
        fn = np.sum((preds == 0) & (y_true == 1))
        tn = np.sum((preds == 0) & (y_true == 0))

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec + 1e-9)) if (prec + rec) > 0 else 0.0

        records.append({
            "model": model_name,
            "threshold": float(th),
            "raw_threshold": float(min_s + th * (max_s - min_s)),
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "false_positive_rate": fpr,
            "false_negative_rate": fnr,
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
        })

    return pd.DataFrame(records)


def plot_threshold_curves(
    df_sweep: pd.DataFrame,
    plots_dir: str,
    selected_threshold: Optional[float] = None,
):
    """Generate precision, recall, and F1 curves vs. threshold."""
    os.makedirs(plots_dir, exist_ok=True)
    ths = df_sweep["threshold"].values
    prec = df_sweep["precision"].values
    rec = df_sweep["recall"].values
    f1 = df_sweep["f1_score"].values
    fpr = df_sweep["false_positive_rate"].values

    # 1. F1 vs Threshold Plot
    plt.figure(figsize=(7, 4.5), dpi=300)
    plt.plot(ths, f1, color="#1f77b4", lw=2.5, label="F1-Score")
    if selected_threshold is not None:
        plt.axvline(selected_threshold, color="red", linestyle="--", lw=1.5, label=f"Selected Thresh = {selected_threshold:.2f}")
    plt.xlabel("Normalized Threshold", fontsize=11)
    plt.ylabel("F1-Score", fontsize=11)
    plt.title("F1-Score vs Decision Threshold", fontsize=12, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "f1_vs_threshold.png"), dpi=300)
    plt.close()

    # 2. Recall vs Threshold Plot
    plt.figure(figsize=(7, 4.5), dpi=300)
    plt.plot(ths, rec, color="#2ca02c", lw=2.5, label="Recall (Sensitivity)")
    plt.plot(ths, fpr, color="#d62728", lw=2.0, linestyle=":", label="False Positive Rate (FPR)")
    if selected_threshold is not None:
        plt.axvline(selected_threshold, color="black", linestyle="--", lw=1.5, label=f"Operating Point = {selected_threshold:.2f}")
    plt.xlabel("Normalized Threshold", fontsize=11)
    plt.ylabel("Rate", fontsize=11)
    plt.title("Recall & False-Positive Rate vs Threshold", fontsize=12, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "recall_vs_threshold.png"), dpi=300)
    plt.close()

    # 3. Precision-Recall vs Threshold Plot
    plt.figure(figsize=(7, 4.5), dpi=300)
    plt.plot(ths, prec, color="#ff7f0e", lw=2.5, label="Precision")
    plt.plot(ths, rec, color="#2ca02c", lw=2.5, label="Recall")
    plt.plot(ths, f1, color="#1f77b4", lw=2.0, linestyle="--", label="F1-Score")
    if selected_threshold is not None:
        plt.axvline(selected_threshold, color="red", linestyle="--", lw=1.5, label=f"Operating Point = {selected_threshold:.2f}")
    plt.xlabel("Normalized Threshold", fontsize=11)
    plt.ylabel("Metric Value", fontsize=11)
    plt.title("Precision, Recall & F1 Tradeoff vs Threshold", fontsize=12, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "precision_recall_vs_threshold.png"), dpi=300)
    plt.close()


def plot_roc_and_pr_curves(
    y_true: np.ndarray,
    scores: np.ndarray,
    model_name: str,
    plots_dir: str,
):
    """Generate high-resolution ROC and Precision-Recall curves."""
    os.makedirs(plots_dir, exist_ok=True)
    fpr, tpr, _ = roc_curve(y_true, scores)
    roc_auc = auc(fpr, tpr)

    prec, rec, _ = precision_recall_curve(y_true, scores)
    pr_auc = average_precision_score(y_true, scores)

    # ROC Curve
    plt.figure(figsize=(6, 5), dpi=300)
    plt.plot(fpr, tpr, color="#1f77b4", lw=2.5, label=f"{model_name} (AUC = {roc_auc:.4f})")
    plt.plot([0, 1], [0, 1], color="gray", linestyle="--", lw=1.5, label="Random Baseline (AUC = 0.50)")
    plt.xlim([-0.02, 1.02])
    plt.ylim([-0.02, 1.02])
    plt.xlabel("False Positive Rate (FPR)", fontsize=11)
    plt.ylabel("True Positive Rate / Recall", fontsize=11)
    plt.title(f"Receiver Operating Characteristic (ROC) — {model_name}", fontsize=11, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "roc_curve.png"), dpi=300)
    plt.close()

    # Precision-Recall Curve
    plt.figure(figsize=(6, 5), dpi=300)
    plt.plot(rec, prec, color="#2ca02c", lw=2.5, label=f"{model_name} (PR-AUC = {pr_auc:.4f})")
    plt.xlim([-0.02, 1.02])
    plt.ylim([-0.02, 1.02])
    plt.xlabel("Recall (Sensitivity)", fontsize=11)
    plt.ylabel("Precision", fontsize=11)
    plt.title(f"Precision-Recall Curve — {model_name}", fontsize=11, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "precision_recall_curve.png"), dpi=300)
    plt.close()


def plot_score_distributions(
    scores: np.ndarray,
    y_true: np.ndarray,
    threshold: float,
    model_name: str,
    output_path: str,
):
    """Plot distribution of anomaly scores for nominal vs anomalous samples."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    normal_scores = scores[y_true == 0]
    anomaly_scores = scores[y_true == 1]

    plt.figure(figsize=(8, 4.5), dpi=300)
    plt.hist(normal_scores, bins=50, alpha=0.6, color="#1f77b4", label=f"Nominal Mine Operation (N={len(normal_scores):,})", density=True)
    plt.hist(anomaly_scores, bins=50, alpha=0.6, color="#d62728", label=f"Subsidence Anomaly (N={len(anomaly_scores):,})", density=True)
    plt.axvline(threshold, color="black", linestyle="--", lw=2.0, label=f"Operating Threshold = {threshold:.3f}")

    plt.xlabel("Anomaly Reconstruction Error / Output Score", fontsize=11)
    plt.ylabel("Density", fontsize=11)
    plt.title(f"Normal vs. Anomalous Score Distribution — {model_name}", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


# Compatibility Aliases
sweep_anomaly_thresholds = perform_threshold_sweep


def plot_anomaly_score_distribution(
    y_true: np.ndarray,
    scores: np.ndarray,
    selected_threshold: float,
    model_name: str,
    output_path: str,
):
    plot_score_distributions(scores, y_true, selected_threshold, model_name, output_path)

