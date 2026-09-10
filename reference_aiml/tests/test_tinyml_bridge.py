import pytest
from datetime import datetime, timezone
from src.models.autoencoder_detector import PyTorchAutoencoderDetector
from src.tinyml_bridge.distillation_exporter import TinyMLDistillationExporter
from src.tinyml_bridge.edge_reconciler import EdgeCloudReconciler

def test_tinyml_distillation_exporter():
    ae = PyTorchAutoencoderDetector(input_dim=8, latent_dim=2)
    exporter = TinyMLDistillationExporter(teacher_ae=ae)

    manifest = exporter.export_quantized_edge_model(target_device="ARM_Cortex_M4", bits=8)

    assert manifest["quantization"] == "INT8_symmetric"
    assert manifest["target_architecture"] == "ARM_Cortex_M4"
    assert manifest["is_edge_deployable"] is True
    assert "encoder.0.weight" in manifest["weights"]
    assert "scale" in manifest["weights"]["encoder.0.weight"]

def test_edge_cloud_reconciler():
    reconciler = EdgeCloudReconciler(drift_threshold_disagreements=3)
    now = datetime.now(timezone.utc)

    # Nominal agreement
    res1 = reconciler.record_comparison("N-01", True, True, now)
    assert res1["is_agreement"] is True
    assert res1["drift_detected"] is False

    # Disagreements (e.g. edge flag is True, but cloud says False)
    reconciler.record_comparison("N-01", True, False, now)
    reconciler.record_comparison("N-01", True, False, now)
    res_drift = reconciler.record_comparison("N-01", True, False, now)

    assert res_drift["is_agreement"] is False
    assert res_drift["consecutive_disagreements"] == 3
    assert res_drift["drift_detected"] is True
    assert "Redistill" in res_drift["recommended_action"]
