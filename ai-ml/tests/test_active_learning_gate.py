"""
Unit tests for SubSense Active Learning Feedback Loop and Model Promotion Validation Gate.
Proves:
1. Operator feedback labeling across the 4 strict regulatory classes.
2. Automatic false-alarm routing to the Negative Sample Mining Repository.
3. Code-enforced validation gate strictly blocks regressing candidate models.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from active_learning.feedback_api import (
    FeedbackLabel,
    OperatorLabelSubmission,
    submit_operator_label,
    negative_mining_repo,
)
from active_learning.validation_gate import (
    CandidateModelValidationGate,
    ModelEvaluationMetrics,
    CandidateModelRejectedException,
)
from dags.weekly_subsense_retraining import run_weekly_retraining_pipeline


class TestActiveLearningAndValidationGate:
    def setup_method(self):
        negative_mining_repo.clear()

    def test_operator_feedback_and_negative_mining(self):
        # 1. Submit Confirmed Ground Movement (Not a false alarm)
        sub1 = OperatorLabelSubmission(
            alert_id="ALERT-001",
            node_id="NODE-10",
            timestamp=datetime.now(timezone.utc),
            operator_id="GEO-ENG-01",
            feedback_label=FeedbackLabel.CONFIRMED_GROUND_MOVEMENT,
            notes="Visual crack opening confirmed at face",
            feature_vector=[0.2] * 12,
        )
        res1 = submit_operator_label(sub1)
        assert res1["is_false_alarm_mined"] is False
        assert negative_mining_repo.get_sample_count() == 0

        # 2. Submit False Alarm — Surface Blast
        sub2 = OperatorLabelSubmission(
            alert_id="ALERT-002",
            node_id="NODE-12",
            timestamp=datetime.now(timezone.utc),
            operator_id="GEO-ENG-01",
            feedback_label=FeedbackLabel.FALSE_ALARM_SURFACE_BLAST,
            notes="Correlated with open cast bench blast at 14:00",
            feature_vector=[0.4] * 12,
        )
        res2 = submit_operator_label(sub2)
        assert res2["is_false_alarm_mined"] is True
        assert negative_mining_repo.get_sample_count() == 1

        # 3. Submit Machinery Vibration
        sub3 = OperatorLabelSubmission(
            alert_id="ALERT-003",
            node_id="NODE-15",
            timestamp=datetime.now(timezone.utc),
            operator_id="GEO-ENG-01",
            feedback_label=FeedbackLabel.FALSE_ALARM_MACHINERY_VIBRATION,
            notes="Continuous shearer drum pass",
            feature_vector=[0.3] * 12,
        )
        submit_operator_label(sub3)
        assert negative_mining_repo.get_sample_count() == 2

        # 4. Ingest matrix check
        matrix = negative_mining_repo.get_negative_feature_matrix()
        assert matrix.shape == (2, 12)

    def test_validation_gate_promotes_compliant_candidate(self):
        prod = ModelEvaluationMetrics(
            model_version="v1.0.0",
            recall=0.982,
            precision=0.910,
            false_positive_count=100,
            true_positive_count=500,
            false_negative_count=9,
            total_samples=1000,
        )
        # Candidate has higher recall and 40% FP reduction (100 -> 60)
        cand = ModelEvaluationMetrics(
            model_version="v1.1.0-candidate",
            recall=0.985,
            precision=0.940,
            false_positive_count=60,
            true_positive_count=502,
            false_negative_count=8,
            total_samples=1000,
        )

        gate = CandidateModelValidationGate(required_fp_reduction_ratio=0.35)
        res = gate.enforce_gate(production=prod, candidate=cand)
        assert res.promotable is True
        assert res.measured_fp_reduction_ratio == 0.40

    def test_validation_gate_rejects_candidate_with_regressed_recall(self):
        prod = ModelEvaluationMetrics(
            model_version="v1.0.0",
            recall=0.985,
            precision=0.910,
            false_positive_count=100,
            true_positive_count=500,
            false_negative_count=8,
            total_samples=1000,
        )
        # Candidate has lower recall (0.970 < 0.985) despite 60% FP reduction
        cand = ModelEvaluationMetrics(
            model_version="v1.1.0-worse-recall",
            recall=0.970,
            precision=0.960,
            false_positive_count=40,
            true_positive_count=485,
            false_negative_count=15,
            total_samples=1000,
        )

        gate = CandidateModelValidationGate(required_fp_reduction_ratio=0.35)
        with pytest.raises(CandidateModelRejectedException) as exc_info:
            gate.enforce_gate(production=prod, candidate=cand)
        assert "Recall regression detected" in str(exc_info.value)

    def test_validation_gate_rejects_candidate_with_insufficient_fp_reduction(self):
        prod = ModelEvaluationMetrics(
            model_version="v1.0.0",
            recall=0.982,
            precision=0.910,
            false_positive_count=100,
            true_positive_count=500,
            false_negative_count=9,
            total_samples=1000,
        )
        # Candidate has same recall, but only 15% FP reduction (100 -> 85 < 35% required)
        cand = ModelEvaluationMetrics(
            model_version="v1.1.0-insufficient-fp",
            recall=0.982,
            precision=0.920,
            false_positive_count=85,
            true_positive_count=500,
            false_negative_count=9,
            total_samples=1000,
        )

        gate = CandidateModelValidationGate(required_fp_reduction_ratio=0.35)
        with pytest.raises(CandidateModelRejectedException) as exc_info:
            gate.enforce_gate(production=prod, candidate=cand)
        assert "Insufficient false positive reduction" in str(exc_info.value)

    def test_airflow_pipeline_execution_halts_on_regressing_model(self):
        prod = ModelEvaluationMetrics(
            model_version="v1.0.0",
            recall=0.985,
            precision=0.910,
            false_positive_count=100,
            true_positive_count=500,
            false_negative_count=8,
            total_samples=1000,
        )
        cand_bad = ModelEvaluationMetrics(
            model_version="v1.1.0-bad",
            recall=0.960,  # Regressed
            precision=0.910,
            false_positive_count=100,
            true_positive_count=480,
            false_negative_count=20,
            total_samples=1000,
        )
        X_dummy = np.random.normal(0, 1, (50, 12)).astype(np.float32)

        with pytest.raises(CandidateModelRejectedException):
            run_weekly_retraining_pipeline(
                repo=negative_mining_repo,
                X_baseline=X_dummy,
                production_metrics=prod,
                candidate_metrics=cand_bad,
            )
