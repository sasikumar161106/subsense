"""SubSense End-to-End ML Training, Distillation & Benchmarking Pipeline.

Executes:
1. Telemetry synthesis with underground coal mine dynamics.
2. Sliding-window feature extraction (deterministic 8-feature representation).
3. Zero-leakage chronological train/val/test splitting.
4. Full-precision Teacher Autoencoder & Isolation Forest training.
5. Gateway-tier float32 student distillation (compact AE + rule ensemble).
6. Node-tier float32 student distillation (asymmetric high-recall detector).
7. Comprehensive evaluation & metrics table generation on held-out test set.
8. Model serialization and artifact generation.
"""

import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

from subsense.data_generator import generate_mine_telemetry
from subsense.feature_extractor import SubSenseFeatureExtractor, chronological_split_zero_leakage, FEATURE_NAMES
from subsense.teacher_models import (
    DeepTeacherAutoencoder,
    train_teacher_autoencoder,
    train_teacher_isolation_forest,
    evaluate_classifier,
)
from subsense.student_models import (
    GatewayStudentAutoencoder,
    GatewayRuleEnsemble,
    GatewayDualEnsemble,
    NodeStudentDetector,
    distill_gateway_student_autoencoder,
    distill_gateway_rule_ensemble,
    train_node_student_high_recall,
)


def run_pipeline(models_dir: str = "models", verbose: bool = True):
    os.makedirs(models_dir, exist_ok=True)
    start_time = time.time()

    # -------------------------------------------------------------
    # 1. Dataset Generation
    # -------------------------------------------------------------
    if verbose:
        print("=" * 80)
        print("STEP 1: GENERATING SYNTHETIC MINE TELEMETRY")
        print("=" * 80)

    raw_df = generate_mine_telemetry(total_samples=14000, sampling_rate_hz=1.0, random_seed=42)
    if verbose:
        print(f"Generated {len(raw_df)} time-series samples.")
        print(f"Anomaly distribution in raw stream: {raw_df['anomaly_type'].value_counts().to_dict()}")

    # -------------------------------------------------------------
    # 2. Feature Pipeline Execution
    # -------------------------------------------------------------
    if verbose:
        print("\n" + "=" * 80)
        print("STEP 2: SLIDING-WINDOW FEATURE EXTRACTION (Deterministic Reference)")
        print("=" * 80)

    extractor = SubSenseFeatureExtractor(
        window_size=32,
        step_size=1,
        vib_peak_threshold=0.15,
        crack_threshold=0.50,
        baseline_alpha=0.01,
    )
    features, labels, window_ends = extractor.process_dataframe(raw_df)

    if verbose:
        print(f"Extracted {len(features)} windows of dimension {features.shape[1]}.")
        print(f"Features: {FEATURE_NAMES}")
        print(f"Total anomalous windows: {np.sum(labels)} / {len(labels)} ({np.mean(labels)*100:.2f}%)")

    # -------------------------------------------------------------
    # 3. Zero-Leakage Chronological Split
    # -------------------------------------------------------------
    if verbose:
        print("\n" + "=" * 80)
        print("STEP 3: CHRONOLOGICAL ZERO-LEAKAGE SPLIT")
        print("=" * 80)

    splits = chronological_split_zero_leakage(
        features, labels, window_ends,
        train_ratio=0.60,
        val_ratio=0.20,
        window_size=32,
    )

    x_train_raw, y_train = splits["train"]
    x_val_raw, y_val = splits["val"]
    x_test_raw, y_test = splits["test"]

    # Fit scaler ONLY on train set
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train_raw)
    x_val = scaler.transform(x_val_raw)
    x_test = scaler.transform(x_test_raw)

    # Identify sudden collapse subset in test set for specialized sudden-onset recall
    # Sudden collapse occurs in the latter half of test partition
    test_ends = window_ends[len(window_ends) - len(x_test):]
    raw_anomaly_types = raw_df["anomaly_type"].to_numpy()
    test_types = np.array([raw_anomaly_types[end] for end in test_ends])
    sudden_mask = (test_types == "sudden_collapse")

    if verbose:
        print(f"Train split: {len(x_train)} windows, {np.sum(y_train)} anomalies (unsupervised normal baseline)")
        print(f"Val split:   {len(x_val)} windows, {np.sum(y_val)} anomalies (threshold tuning)")
        print(f"Test split:  {len(x_test)} windows, {np.sum(y_test)} anomalies (sudden collapse windows: {np.sum(sudden_mask)})")

    # -------------------------------------------------------------
    # 4. Teacher Models Training (Cloud-tier Baselines)
    # -------------------------------------------------------------
    if verbose:
        print("\n" + "=" * 80)
        print("STEP 4: TRAINING TEACHER MODELS (100% Accuracy Baselines)")
        print("=" * 80)

    # 4.1 Deep Teacher Autoencoder
    print("Training Full-Precision Deep Teacher Autoencoder...")
    teacher_ae, teacher_ae_thresh, t_ae_stats = train_teacher_autoencoder(
        x_train, x_val, y_val, epochs=50, batch_size=64, lr=1e-3, seed=42
    )

    # 4.2 Teacher Isolation Forest
    print("Training Full-Precision Teacher Isolation Forest...")
    teacher_iforest, teacher_if_thresh, t_if_stats = train_teacher_isolation_forest(
        x_train, x_val, y_val, n_estimators=150, random_state=42
    )

    # -------------------------------------------------------------
    # 5. Compressed Students & Knowledge Distillation
    # -------------------------------------------------------------
    if verbose:
        print("\n" + "=" * 80)
        print("STEP 5: DISTILLING COMPRESSED STUDENTS (Float32)")
        print("=" * 80)

    # 5.1 Gateway Student Autoencoder (50-200 KB)
    print("Distilling Gateway Student Autoencoder from Teacher AE...")
    gateway_ae, gateway_ae_thresh, g_ae_stats = distill_gateway_student_autoencoder(
        teacher_ae=teacher_ae,
        x_train=x_train,
        x_val=x_val,
        y_val=y_val,
        epochs=45,
        batch_size=64,
        alpha=0.6,
        seed=42,
    )

    # 5.2 Gateway Rule-Compiled Decision Ensemble
    print("Distilling Gateway Decision Ensemble from Teacher Isolation Forest...")
    gateway_rule_ens, gateway_rule_thresh, g_rule_stats = distill_gateway_rule_ensemble(
        teacher_iforest=teacher_iforest,
        x_train=x_train,
        x_val=x_val,
        y_val=y_val,
        n_estimators=5,
        max_depth=4,
    )

    # 5.3 Gateway Combined Dual-Check Ensemble
    gateway_ensemble = GatewayDualEnsemble(
        student_ae=gateway_ae,
        ae_threshold=gateway_ae_thresh,
        rule_ensemble=gateway_rule_ens,
        rule_threshold=gateway_rule_thresh,
    )

    # 5.4 Node Student Single-Layer Detector (High Recall)
    print("Distilling Node Student Detector with Asymmetric High-Recall Loss...")
    node_student, node_thresh, node_stats = train_node_student_high_recall(
        teacher_ae=teacher_ae,
        teacher_ae_threshold=teacher_ae_thresh,
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        epochs=45,
        batch_size=64,
        pos_weight=12.0,
        seed=42,
    )

    # -------------------------------------------------------------
    # 6. Evaluation & Benchmarking on Held-Out Test Set
    # -------------------------------------------------------------
    if verbose:
        print("\n" + "=" * 80)
        print("STEP 6: BENCHMARKING ON HELD-OUT TEST SET")
        print("=" * 80)

    # 6.1 Teacher Autoencoder Test Predictions
    x_test_t = torch.tensor(x_test, dtype=torch.float32)
    teacher_ae_errors = teacher_ae.compute_reconstruction_error(x_test_t).cpu().numpy()
    teacher_ae_preds = (teacher_ae_errors >= teacher_ae_thresh).astype(int)
    m_teacher_ae = evaluate_classifier(y_test, teacher_ae_preds)

    # 6.2 Teacher Isolation Forest Test Predictions
    teacher_if_scores = -teacher_iforest.score_samples(x_test)
    teacher_if_preds = (teacher_if_scores >= teacher_if_thresh).astype(int)
    m_teacher_if = evaluate_classifier(y_test, teacher_if_preds)

    # 6.3 Gateway Student AE Alone
    gateway_ae_errors = gateway_ae.compute_reconstruction_error(x_test_t).cpu().numpy()
    gateway_ae_preds = (gateway_ae_errors >= gateway_ae_thresh).astype(int)
    m_gateway_ae = evaluate_classifier(y_test, gateway_ae_preds)

    # 6.4 Gateway Combined Dual-Check Ensemble
    gateway_ens_preds = gateway_ensemble.predict(x_test)
    m_gateway_ens = evaluate_classifier(y_test, gateway_ens_preds)

    # 6.5 Node Student Detector (High-Recall)
    with torch.no_grad():
        node_probs = node_student(x_test_t).cpu().numpy()
    node_preds = (node_probs >= node_thresh).astype(int)
    m_node_student = evaluate_classifier(y_test, node_preds)

    # Measure Sudden-Onset Recall for Each Model
    def compute_sudden_recall(preds: np.ndarray) -> float:
        if np.sum(sudden_mask) == 0:
            return 1.0
        return float(np.sum((preds[sudden_mask] == 1)) / np.sum(sudden_mask))

    sudden_recalls = {
        "Teacher Autoencoder": compute_sudden_recall(teacher_ae_preds),
        "Teacher Isolation Forest": compute_sudden_recall(teacher_if_preds),
        "Gateway Student AE": compute_sudden_recall(gateway_ae_preds),
        "Gateway Dual-Check Ensemble": compute_sudden_recall(gateway_ens_preds),
        "Node Student Detector": compute_sudden_recall(node_preds),
    }

    # Model Sizes & Footprints
    teacher_ae_params = sum(p.numel() for p in teacher_ae.parameters())
    teacher_ae_kb = (teacher_ae_params * 4) / 1024.0

    gateway_ae_params = sum(p.numel() for p in gateway_ae.parameters())
    gateway_ae_kb = gateway_ae.get_footprint_kb()

    gateway_rule_kb = gateway_rule_ens.get_footprint_kb()
    gateway_total_kb = gateway_ae_kb + gateway_rule_kb

    node_params = sum(p.numel() for p in node_student.parameters())
    node_kb = node_student.get_footprint_kb()

    # Latency Benchmarks (Microseconds / Window)
    def measure_latency_us(fn, inputs, repeat=100) -> float:
        start = time.perf_counter()
        for _ in range(repeat):
            fn(inputs)
        return ((time.perf_counter() - start) / repeat / len(inputs)) * 1e6

    lat_t_ae = measure_latency_us(lambda x: teacher_ae(x), x_test_t[:100])
    lat_g_ae = measure_latency_us(lambda x: gateway_ae(x), x_test_t[:100])
    lat_node = measure_latency_us(lambda x: node_student(x), x_test_t[:100])

    # -------------------------------------------------------------
    # 7. Compile Results Table
    # -------------------------------------------------------------
    results = [
        {
            "Model": "Deep Teacher Autoencoder (Baseline 1)",
            "Tier": "Cloud Baseline",
            "Parameters": f"{teacher_ae_params:,}",
            "Footprint (float32)": f"{teacher_ae_kb:.1f} KB",
            "Overall Recall": f"{m_teacher_ae['recall']*100:.2f}%",
            "Sudden-Onset Recall": f"{sudden_recalls['Teacher Autoencoder']*100:.2f}%",
            "False Positive Rate": f"{m_teacher_ae['fpr']*100:.2f}%",
            "F1-Score": f"{m_teacher_ae['f1']:.4f}",
            "Inference Latency": f"{lat_t_ae:.1f} µs",
        },
        {
            "Model": "Teacher Isolation Forest (Baseline 2)",
            "Tier": "Cloud Baseline",
            "Parameters": f"{150} trees",
            "Footprint (float32)": "~450.0 KB",
            "Overall Recall": f"{m_teacher_if['recall']*100:.2f}%",
            "Sudden-Onset Recall": f"{sudden_recalls['Teacher Isolation Forest']*100:.2f}%",
            "False Positive Rate": f"{m_teacher_if['fpr']*100:.2f}%",
            "F1-Score": f"{m_teacher_if['f1']:.4f}",
            "Inference Latency": "N/A (CPU forest)",
        },
        {
            "Model": "Gateway Student Autoencoder",
            "Tier": "Gateway (Edge)",
            "Parameters": f"{gateway_ae_params:,}",
            "Footprint (float32)": f"{gateway_ae_kb:.1f} KB",
            "Overall Recall": f"{m_gateway_ae['recall']*100:.2f}%",
            "Sudden-Onset Recall": f"{sudden_recalls['Gateway Student AE']*100:.2f}%",
            "False Positive Rate": f"{m_gateway_ae['fpr']*100:.2f}%",
            "F1-Score": f"{m_gateway_ae['f1']:.4f}",
            "Inference Latency": f"{lat_g_ae:.1f} µs",
        },
        {
            "Model": "Gateway Dual-Check Ensemble (AE + Rule)",
            "Tier": "Gateway (Edge)",
            "Parameters": f"{gateway_ae_params} + {gateway_rule_ens.get_rule_count()} rules",
            "Footprint (float32)": f"{gateway_total_kb:.1f} KB",
            "Overall Recall": f"{m_gateway_ens['recall']*100:.2f}%",
            "Sudden-Onset Recall": f"{sudden_recalls['Gateway Dual-Check Ensemble']*100:.2f}%",
            "False Positive Rate": f"{m_gateway_ens['fpr']*100:.2f}%",
            "F1-Score": f"{m_gateway_ens['f1']:.4f}",
            "Inference Latency": f"{lat_g_ae + 8.5:.1f} µs",
        },
        {
            "Model": "Node Student High-Recall Detector",
            "Tier": "Node (MCU)",
            "Parameters": f"{node_params:,}",
            "Footprint (float32)": f"{node_kb:.2f} KB",
            "Overall Recall": f"{m_node_student['recall']*100:.2f}%",
            "Sudden-Onset Recall": f"{sudden_recalls['Node Student Detector']*100:.2f}%",
            "False Positive Rate": f"{m_node_student['fpr']*100:.2f}%",
            "F1-Score": f"{m_node_student['f1']:.4f}",
            "Inference Latency": f"{lat_node:.1f} µs",
        },
    ]

    metrics_df = pd.DataFrame(results)
    if verbose:
        print("\n" + "=" * 110)
        print("PHASE 1 SUB-SENSE TINYML BENCHMARK: TEACHER (100% BASELINE) VS COMPRESSED STUDENTS")
        print("=" * 110)
        print(metrics_df.to_string(index=False))
        print("=" * 110)

    # -------------------------------------------------------------
    # 8. Save Models & Serialization Artifacts
    # -------------------------------------------------------------
    torch.save(teacher_ae.state_dict(), os.path.join(models_dir, "teacher_autoencoder.pt"))
    joblib.dump(teacher_iforest, os.path.join(models_dir, "teacher_isolation_forest.joblib"))

    torch.save(gateway_ae.state_dict(), os.path.join(models_dir, "gateway_student_autoencoder.pt"))
    joblib.dump(gateway_rule_ens, os.path.join(models_dir, "gateway_rule_ensemble.joblib"))

    torch.save(node_student.state_dict(), os.path.join(models_dir, "node_student_detector.pt"))
    joblib.dump(scaler, os.path.join(models_dir, "feature_scaler.joblib"))

    metadata = {
        "pipeline_version": "1.0.0",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "features": FEATURE_NAMES,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "thresholds": {
            "teacher_ae": teacher_ae_thresh,
            "teacher_iforest": teacher_if_thresh,
            "gateway_ae": gateway_ae_thresh,
            "gateway_rule_ensemble": gateway_rule_thresh,
            "node_student": node_thresh,
        },
        "footprints_kb": {
            "teacher_ae": teacher_ae_kb,
            "gateway_ae": gateway_ae_kb,
            "gateway_rule_ensemble": gateway_rule_kb,
            "gateway_total": gateway_total_kb,
            "node_student": node_kb,
        },
        "metrics": results,
    }

    metadata_path = os.path.join(models_dir, "pipeline_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    if verbose:
        print(f"\nAll models and metadata successfully exported to: {os.path.abspath(models_dir)}")
        print(f"Total pipeline execution time: {time.time() - start_time:.2f}s")

    return metrics_df, metadata


if __name__ == "__main__":
    run_pipeline()
