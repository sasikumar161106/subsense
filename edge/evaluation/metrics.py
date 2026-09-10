"""Comprehensive Metrics Calculation and Confusion Matrix Plotting for SubSense TinyML.

Computes:
- Core metrics: Accuracy, Precision, Recall, F1, Specificity, FPR, FNR
- Advanced metrics: ROC-AUC, PR-AUC, Balanced Accuracy, Matthews Correlation Coefficient (MCC)
- Life-safety critical metrics: Sudden-onset precursor recall
- Confusion Matrix generation & visualization
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    balanced_accuracy_score,
    matthews_corrcoef,
    roc_curve,
    precision_recall_curve,
)
from typing import Dict, Any, Tuple, Optional


def compute_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: Optional[np.ndarray] = None,
    sudden_onset_mask: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Compute comprehensive classification and anomaly detection metrics."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)

    # Confusion matrix elements
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    total = len(y_true)

    # Core rates
    accuracy = float((tp + tn) / total) if total > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall + 1e-9)) if (precision + recall) > 0 else 0.0

    # Additional metrics
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    try:
        mcc = float(matthews_corrcoef(y_true, y_pred))
    except Exception:
        mcc = 0.0

    # Area under curves (if continuous scores provided)
    roc_auc = None
    pr_auc = None
    if y_scores is not None and len(np.unique(y_true)) > 1:
        try:
            roc_auc = float(roc_auc_score(y_true, y_scores))
            pr_auc = float(average_precision_score(y_true, y_scores))
        except Exception:
            roc_auc = None
            pr_auc = None

    # Specialized Sudden-Onset Precursor Recall (Zero Missed Siren Mandate)
    sudden_recall = 1.0
    sudden_count = 0
    if sudden_onset_mask is not None:
        sudden_mask = np.asarray(sudden_onset_mask).astype(bool)
        sudden_count = int(np.sum(sudden_mask))
        if sudden_count > 0:
            sudden_tp = int(np.sum((y_pred[sudden_mask] == 1)))
            sudden_recall = float(sudden_tp / sudden_count)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1_score": f1,
        "false_positive_rate": fpr,
        "false_negative_rate": fnr,
        "balanced_accuracy": bal_acc,
        "matthews_corrcoef": mcc,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "sudden_onset_recall": sudden_recall,
        "sudden_onset_events_count": sudden_count,
        "confusion_matrix": {
            "true_positive": int(tp),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "total_samples": int(total),
        },
    }


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str,
    output_path: str,
    normalize: bool = False,
):
    """Generate and save a high-contrast confusion matrix plot."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    if normalize:
        cm_display = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    else:
        cm_display = cm

    fig, ax = plt.subplots(figsize=(6, 5), dpi=300)
    cax = ax.matshow(cm_display, cmap=plt.cm.Blues)
    fig.colorbar(cax)

    # Axis labels
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['Nominal (0)', 'Anomaly (1)'], fontsize=11)
    ax.set_yticklabels(['Nominal (0)', 'Anomaly (1)'], fontsize=11)
    ax.set_xlabel('Predicted Label', fontsize=12, labelpad=10)
    ax.set_ylabel('True Ground Truth', fontsize=12, labelpad=10)
    ax.set_title(f'Confusion Matrix — {model_name}', fontsize=13, pad=15, fontweight='bold')

    # Annotate numbers
    thresh = cm_display.max() / 2.0
    for i in range(2):
        for j in range(2):
            val_str = f"{cm[i, j]:,}\n({cm_display[i, j]*100:.1f}%)" if normalize else f"{cm[i, j]:,}"
            color = "white" if cm_display[i, j] > thresh else "black"
            ax.text(j, i, val_str, ha="center", va="center", color=color, fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


# Alias for compatibility with external modules
compute_classification_metrics = compute_all_metrics


def plot_model_size_comparison(
    models_size_data: Dict[str, float],
    output_path: str = "evaluation/results/plots/model_size_comparison.png",
):
    """
    Generate a bar chart comparing model footprints in KB across tiers and precisions.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    names = list(models_size_data.keys())
    sizes = list(models_size_data.values())

    colors = ['#3b82f6', '#1d4ed8', '#10b981', '#059669', '#f59e0b']
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    bars = ax.bar(names, sizes, color=colors[:len(names)], edgecolor='black', linewidth=0.8, width=0.55)

    ax.set_ylabel("Size (KB)", fontsize=11, fontweight='bold')
    ax.set_title("SubSense TinyML Model Footprint Comparison", fontsize=12, fontweight='bold')
    ax.grid(axis='y', linestyle='--', alpha=0.4)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f} KB',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.xticks(rotation=15, ha='right', fontsize=10)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_latency_comparison(
    latency_data: Dict[str, Dict[str, float]],
    output_path: str = "evaluation/results/plots/latency_comparison.png",
):
    """
    Generate latency comparison chart (Mean, P50, P95, P99) across models.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    models = list(latency_data.keys())
    means = [latency_data[m]["mean_ms"] for m in models]
    p50s = [latency_data[m]["p50_ms"] for m in models]
    p95s = [latency_data[m]["p95_ms"] for m in models]
    p99s = [latency_data[m]["p99_ms"] for m in models]

    x = np.arange(len(models))
    width = 0.18

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=300)
    ax.bar(x - 1.5*width, means, width, label='Mean', color='#3b82f6')
    ax.bar(x - 0.5*width, p50s, width, label='P50 (Median)', color='#10b981')
    ax.bar(x + 0.5*width, p95s, width, label='P95', color='#f59e0b')
    ax.bar(x + 1.5*width, p99s, width, label='P99', color='#ef4444')

    ax.set_ylabel("Latency (ms / window) [HOST-MACHINE]", fontsize=11, fontweight='bold')
    ax.set_title("SubSense Inference Latency Profile (Host PC Benchmark)", fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=10, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(axis='y', linestyle='--', alpha=0.4)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_fp32_vs_int8_comparison(
    comparison_data: Dict[str, Dict[str, Any]],
    output_path: str = "evaluation/results/plots/fp32_vs_int8_comparison.png",
):
    """
    Generate side-by-side grouped bar chart comparing FP32 vs INT8 for:
    - Size (KB)
    - Recall (%)
    - F1-Score
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), dpi=300)

    # 1. Size Comparison
    ax0 = axes[0]
    tiers = list(comparison_data.keys())
    fp32_sizes = [comparison_data[t]["fp32_size_kb"] for t in tiers]
    int8_sizes = [comparison_data[t]["int8_size_kb"] for t in tiers]
    x = np.arange(len(tiers))
    width = 0.35

    ax0.bar(x - width/2, fp32_sizes, width, label='FP32', color='#64748b')
    ax0.bar(x + width/2, int8_sizes, width, label='INT8 Quantized', color='#10b981')
    ax0.set_ylabel("Size (KB)", fontsize=10, fontweight='bold')
    ax0.set_title("Flash Footprint Reduction", fontsize=11, fontweight='bold')
    ax0.set_xticks(x)
    ax0.set_xticklabels(tiers, fontweight='bold')
    ax0.legend()
    ax0.grid(axis='y', linestyle='--', alpha=0.3)

    # 2. Recall Comparison
    ax1 = axes[1]
    fp32_recalls = [comparison_data[t]["fp32_recall"] * 100 for t in tiers]
    int8_recalls = [comparison_data[t]["int8_recall"] * 100 for t in tiers]
    ax1.bar(x - width/2, fp32_recalls, width, label='FP32', color='#64748b')
    ax1.bar(x + width/2, int8_recalls, width, label='INT8 Quantized', color='#3b82f6')
    ax1.set_ylabel("Recall (%)", fontsize=10, fontweight='bold')
    ax1.set_title("Detection Recall Retention", fontsize=11, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(tiers, fontweight='bold')
    ax1.set_ylim(80, 105)
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.3)

    # 3. F1-Score Comparison
    ax2 = axes[2]
    fp32_f1s = [comparison_data[t]["fp32_f1"] for t in tiers]
    int8_f1s = [comparison_data[t]["int8_f1"] for t in tiers]
    ax2.bar(x - width/2, fp32_f1s, width, label='FP32', color='#64748b')
    ax2.bar(x + width/2, int8_f1s, width, label='INT8 Quantized', color='#8b5cf6')
    ax2.set_ylabel("F1 Score", fontsize=10, fontweight='bold')
    ax2.set_title("Overall F1-Score Retention", fontsize=11, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(tiers, fontweight='bold')
    ax2.set_ylim(0.7, 1.05)
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)

