"""
SubSense Model Promotion Validation Gate.
Enforces non-negotiable CI/CD deployment constraint:
A candidate model is promotable IF AND ONLY IF:
1. Candidate recall >= Current production recall
2. Verified false positive reduction >= 35% ((FP_prod - FP_cand) / FP_prod >= 0.35)
Strictly blocks deployment in code with CandidateModelRejectedException.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


class CandidateModelRejectedException(RuntimeError):
    """Raised when a candidate model fails the promotion validation gate."""
    pass


@dataclass
class ModelEvaluationMetrics:
    model_version: str
    recall: float
    precision: float
    false_positive_count: int
    true_positive_count: int
    false_negative_count: int
    total_samples: int

    @property
    def f1_score(self) -> float:
        denom = self.precision + self.recall
        return (2.0 * self.precision * self.recall) / denom if denom > 0 else 0.0


@dataclass
class ValidationGateResult:
    promotable: bool
    candidate_version: str
    production_version: str
    current_recall: float
    candidate_recall: float
    recall_condition_met: bool
    current_fp_count: int
    candidate_fp_count: int
    measured_fp_reduction_ratio: float
    fp_reduction_condition_met: bool
    rejection_reasons: List[str] = field(default_factory=list)
    evaluated_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CandidateModelValidationGate:
    """
    Code-enforced deployment gatekeeper.
    Guarantees zero safety regressions (no drop in recall) alongside tangible false positive reduction.
    """

    def __init__(self, required_fp_reduction_ratio: float = 0.35):
        self.required_fp_reduction_ratio = float(required_fp_reduction_ratio)

    def evaluate(
        self,
        production: ModelEvaluationMetrics,
        candidate: ModelEvaluationMetrics,
    ) -> ValidationGateResult:
        """
        Evaluates candidate metrics against production baseline.
        """
        rejection_reasons = []

        # Criterion 1: Recall must not regress
        recall_met = bool(candidate.recall >= production.recall)
        if not recall_met:
            rejection_reasons.append(
                f"Recall regression detected: candidate recall {candidate.recall:.4f} < production recall {production.recall:.4f}"
            )

        # Criterion 2: Verified false positive reduction >= 35%
        if production.false_positive_count > 0:
            fp_reduction = (production.false_positive_count - candidate.false_positive_count) / float(production.false_positive_count)
        else:
            fp_reduction = 0.0 if candidate.false_positive_count > 0 else 1.0

        fp_met = bool(fp_reduction >= self.required_fp_reduction_ratio)
        if not fp_met:
            rejection_reasons.append(
                f"Insufficient false positive reduction: achieved {fp_reduction * 100:.1f}%, required >= {self.required_fp_reduction_ratio * 100:.1f}%"
            )

        promotable = bool(recall_met and fp_met)

        return ValidationGateResult(
            promotable=promotable,
            candidate_version=candidate.model_version,
            production_version=production.model_version,
            current_recall=production.recall,
            candidate_recall=candidate.recall,
            recall_condition_met=recall_met,
            current_fp_count=production.false_positive_count,
            candidate_fp_count=candidate.false_positive_count,
            measured_fp_reduction_ratio=fp_reduction,
            fp_reduction_condition_met=fp_met,
            rejection_reasons=rejection_reasons,
        )

    def enforce_gate(
        self,
        production: ModelEvaluationMetrics,
        candidate: ModelEvaluationMetrics,
    ) -> ValidationGateResult:
        """
        Executes evaluation and RAISES CandidateModelRejectedException if candidate is not promotable.
        """
        result = self.evaluate(production, candidate)
        if not result.promotable:
            msg = f"VALIDATION GATE BLOCKED: Model {candidate.model_version} rejected. " + "; ".join(result.rejection_reasons)
            raise CandidateModelRejectedException(msg)
        return result
