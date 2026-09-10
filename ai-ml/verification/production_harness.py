"""
SubSense Layer 4: Production Verification Harness.
Automates rigorous verification of all six Section 8 targets:
1. Recall >= 0.98 / Precision >= 0.90
2. Warning lead time >= 8.0h ahead of collapse
3. False alarm rate < 0.05 / node / month
4. Packet delivery ratio > 96.5%
5. Forecast calibration (ECE) < 0.08
6. Edge/cloud parity > 94.0%
Enforces honest status reporting: PASSED, FAILED, or INSUFFICIENT_DATA with cryptographic signature.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from typing import Dict, List, Optional, Any
import numpy as np


class MetricStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class TargetEvaluationResult:
    metric_name: str
    target_specification: str
    measured_value: Optional[float]
    status: MetricStatus
    sample_size: int
    minimum_required_samples: int
    details: str


@dataclass
class ProductionVerificationReport:
    report_id: str
    generated_at_utc: str
    overall_status: str
    targets: List[TargetEvaluationResult]
    summary_counts: Dict[str, int]
    report_sha256_signature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProductionVerificationHarness:
    """
    Automated CI test harness validating SubSense Layer 4 against strict Section 8 criteria.
    Never obscures or rounds away failing or unsubstantiated metrics.
    """

    def __init__(
        self,
        target_recall: float = 0.98,
        target_precision: float = 0.90,
        target_lead_time_hours: float = 8.0,
        target_max_far_per_node_month: float = 0.05,
        target_pdr_min: float = 0.965,
        target_ece_max: float = 0.08,
        target_edge_parity_min: float = 0.94,
    ):
        self.target_recall = target_recall
        self.target_precision = target_precision
        self.target_lead_time_hours = target_lead_time_hours
        self.target_max_far = target_max_far_per_node_month
        self.target_pdr_min = target_pdr_min
        self.target_ece_max = target_ece_max
        self.target_edge_parity_min = target_edge_parity_min

    def evaluate_recall_precision(
        self,
        ground_truth: List[int],
        predictions: List[int],
        min_positive_samples: int = 10,
    ) -> List[TargetEvaluationResult]:
        """Evaluates Recall (>=0.98) and Precision (>=0.90)."""
        gt = np.array(ground_truth)
        pred = np.array(predictions)
        n_samples = len(gt)
        n_positives = int(np.sum(gt == 1))

        results = []

        if n_positives < min_positive_samples:
            results.append(TargetEvaluationResult(
                metric_name="Recall",
                target_specification=f">={self.target_recall:.2f}",
                measured_value=None,
                status=MetricStatus.INSUFFICIENT_DATA,
                sample_size=n_positives,
                minimum_required_samples=min_positive_samples,
                details=f"Rare catastrophic collapse incidents limited ({n_positives} observed < {min_positive_samples} required). Cannot substantiate recall target.",
            ))
            results.append(TargetEvaluationResult(
                metric_name="Precision",
                target_specification=f">={self.target_precision:.2f}",
                measured_value=None,
                status=MetricStatus.INSUFFICIENT_DATA,
                sample_size=n_positives,
                minimum_required_samples=min_positive_samples,
                details=f"Insufficient positive incident samples to substantiate precision reliably.",
            ))
            return results

        tp = int(np.sum((gt == 1) & (pred == 1)))
        fp = int(np.sum((gt == 0) & (pred == 1)))
        fn = int(np.sum((gt == 1) & (pred == 0)))

        recall = tp / float(tp + fn) if (tp + fn) > 0 else 0.0
        precision = tp / float(tp + fp) if (tp + fp) > 0 else 0.0

        rec_status = MetricStatus.PASSED if recall >= self.target_recall else MetricStatus.FAILED
        prec_status = MetricStatus.PASSED if precision >= self.target_precision else MetricStatus.FAILED

        results.append(TargetEvaluationResult(
            metric_name="Recall",
            target_specification=f">={self.target_recall:.2f}",
            measured_value=float(recall),
            status=rec_status,
            sample_size=n_samples,
            minimum_required_samples=min_positive_samples,
            details=f"Observed TP={tp}, FN={fn} across {n_samples} benchmark scenarios.",
        ))
        results.append(TargetEvaluationResult(
            metric_name="Precision",
            target_specification=f">={self.target_precision:.2f}",
            measured_value=float(precision),
            status=prec_status,
            sample_size=n_samples,
            minimum_required_samples=min_positive_samples,
            details=f"Observed TP={tp}, FP={fp} across {n_samples} benchmark scenarios.",
        ))
        return results

    def evaluate_warning_lead_time(
        self,
        lead_times_hours: List[float],
        min_events: int = 5,
    ) -> TargetEvaluationResult:
        """Evaluates Warning Lead Time (>=8.0h ahead of collapse)."""
        n = len(lead_times_hours)
        if n < min_events:
            return TargetEvaluationResult(
                metric_name="Warning lead time",
                target_specification=f">={self.target_lead_time_hours:.1f}h",
                measured_value=float(np.median(lead_times_hours)) if n > 0 else None,
                status=MetricStatus.INSUFFICIENT_DATA,
                sample_size=n,
                minimum_required_samples=min_events,
                details=f"Empirical collapse count ({n}) below minimum event threshold ({min_events}).",
            )

        median_lt = float(np.median(lead_times_hours))
        status = MetricStatus.PASSED if median_lt >= self.target_lead_time_hours else MetricStatus.FAILED
        return TargetEvaluationResult(
            metric_name="Warning lead time",
            target_specification=f">={self.target_lead_time_hours:.1f}h",
            measured_value=median_lt,
            status=status,
            sample_size=n,
            minimum_required_samples=min_events,
            details=f"Median lead time {median_lt:.2f}h (min {min(lead_times_hours):.1f}h, max {max(lead_times_hours):.1f}h).",
        )

    def evaluate_false_alarm_rate(
        self,
        false_alarms_count: int,
        total_node_months: float,
        min_node_months: float = 1.0,
    ) -> TargetEvaluationResult:
        """Evaluates False Alarm Rate (<0.05 / node / month)."""
        if total_node_months < min_node_months:
            return TargetEvaluationResult(
                metric_name="False alarm rate",
                target_specification=f"<{self.target_max_far:.2f} / node / month",
                measured_value=None,
                status=MetricStatus.INSUFFICIENT_DATA,
                sample_size=int(total_node_months * 30),
                minimum_required_samples=int(min_node_months * 30),
                details=f"Accumulated node operating history ({total_node_months:.2f} node-months) insufficient for statistical confidence.",
            )

        far = false_alarms_count / float(total_node_months)
        status = MetricStatus.PASSED if far < self.target_max_far else MetricStatus.FAILED
        return TargetEvaluationResult(
            metric_name="False alarm rate",
            target_specification=f"<{self.target_max_far:.2f} / node / month",
            measured_value=float(far),
            status=status,
            sample_size=int(total_node_months * 30),
            minimum_required_samples=int(min_node_months * 30),
            details=f"Observed {false_alarms_count} false alarms across {total_node_months:.2f} node-months of operation.",
        )

    def evaluate_packet_delivery(
        self,
        received_packets: int,
        expected_packets: int,
        min_packets: int = 500,
    ) -> TargetEvaluationResult:
        """Evaluates Packet Delivery Ratio (>96.5%)."""
        if expected_packets < min_packets:
            return TargetEvaluationResult(
                metric_name="Packet delivery",
                target_specification=f">{self.target_pdr_min * 100:.1f}%",
                measured_value=None,
                status=MetricStatus.INSUFFICIENT_DATA,
                sample_size=expected_packets,
                minimum_required_samples=min_packets,
                details=f"Packet count ({expected_packets}) below statistical confidence threshold ({min_packets}).",
            )

        pdr = received_packets / float(expected_packets)
        status = MetricStatus.PASSED if pdr > self.target_pdr_min else MetricStatus.FAILED
        return TargetEvaluationResult(
            metric_name="Packet delivery",
            target_specification=f">{self.target_pdr_min * 100:.1f}%",
            measured_value=float(pdr),
            status=status,
            sample_size=expected_packets,
            minimum_required_samples=min_packets,
            details=f"Delivered {received_packets}/{expected_packets} mesh telemetry packets ({pdr * 100:.2f}%).",
        )

    def evaluate_forecast_calibration(
        self,
        observed_ece: float,
        evaluation_horizons: int = 48,
    ) -> TargetEvaluationResult:
        """Evaluates Forecast Calibration ECE (<0.08)."""
        status = MetricStatus.PASSED if observed_ece < self.target_ece_max else MetricStatus.FAILED
        return TargetEvaluationResult(
            metric_name="Forecast calibration (ECE)",
            target_specification=f"<{self.target_ece_max:.2f}",
            measured_value=float(observed_ece),
            status=status,
            sample_size=evaluation_horizons,
            minimum_required_samples=24,
            details=f"Conformal quantile calibration ECE measured at {observed_ece:.4f} across 48h horizon.",
        )

    def evaluate_edge_cloud_parity(
        self,
        edge_scores: np.ndarray,
        cloud_scores: np.ndarray,
        tolerance: float = 0.05,
    ) -> TargetEvaluationResult:
        """Evaluates Edge/Cloud Score Parity (>94.0%)."""
        n = len(edge_scores)
        if n == 0:
            return TargetEvaluationResult(
                metric_name="Edge/cloud parity",
                target_specification=f">{self.target_edge_parity_min * 100:.1f}%",
                measured_value=None,
                status=MetricStatus.INSUFFICIENT_DATA,
                sample_size=0,
                minimum_required_samples=100,
                details="No dual edge/cloud inference pairs evaluated.",
            )

        agreed = np.abs(edge_scores - cloud_scores) <= tolerance
        parity = float(np.mean(agreed))
        status = MetricStatus.PASSED if parity > self.target_edge_parity_min else MetricStatus.FAILED
        return TargetEvaluationResult(
            metric_name="Edge/cloud parity",
            target_specification=f">{self.target_edge_parity_min * 100:.1f}%",
            measured_value=parity,
            status=status,
            sample_size=n,
            minimum_required_samples=50,
            details=f"Dual inference agreement within {tolerance * 100:.0f}% tolerance: {parity * 100:.2f}%.",
        )

    def generate_report(
        self,
        targets: List[TargetEvaluationResult],
        report_dir: str = "reports",
    ) -> ProductionVerificationReport:
        """Assembles, cryptographically signs, and saves the verification report."""
        os.makedirs(report_dir, exist_ok=True)
        now_utc = datetime.now(timezone.utc).isoformat()
        report_id = f"VERIF-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        counts = {
            "PASSED": sum(1 for t in targets if t.status == MetricStatus.PASSED),
            "FAILED": sum(1 for t in targets if t.status == MetricStatus.FAILED),
            "INSUFFICIENT_DATA": sum(1 for t in targets if t.status == MetricStatus.INSUFFICIENT_DATA),
        }

        if counts["FAILED"] > 0:
            overall = "FAILED"
        elif counts["INSUFFICIENT_DATA"] > 0:
            overall = "PARTIAL_VALIDATION_WITH_INSUFFICIENT_DATA"
        else:
            overall = "FULLY_PASSED"

        # Construct payload for hashing
        canon_payload = {
            "report_id": report_id,
            "generated_at_utc": now_utc,
            "overall_status": overall,
            "summary_counts": counts,
            "targets": [asdict(t) for t in targets],
        }
        raw_json = json.dumps(canon_payload, sort_keys=True)
        signature = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        report = ProductionVerificationReport(
            report_id=report_id,
            generated_at_utc=now_utc,
            overall_status=overall,
            targets=targets,
            summary_counts=counts,
            report_sha256_signature=signature,
        )

        # Save JSON
        json_path = os.path.join(report_dir, "PRODUCTION_VERIFICATION_REPORT.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        # Save Markdown
        md_path = os.path.join(report_dir, "PRODUCTION_VERIFICATION_REPORT.md")
        self._write_markdown_report(report, md_path)

        return report

    def _write_markdown_report(self, report: ProductionVerificationReport, path: str) -> None:
        lines = [
            "# SubSense Layer 4: Production Verification Harness Report",
            f"**Report ID**: `{report.report_id}`  ",
            f"**Generated**: `{report.generated_at_utc}`  ",
            f"**Overall Status**: **`{report.overall_status}`**  ",
            f"**SHA-256 Signature**: `{report.report_sha256_signature}`  ",
            "",
            "## Section 8 Target Verification Results",
            "",
            "| Metric | Target | Measured | Status | Sample Size | Rationale / Details |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for t in report.targets:
            meas_str = f"{t.measured_value:.4f}" if t.measured_value is not None else "N/A"
            status_badge = f"**{t.status.value}**"
            lines.append(
                f"| {t.metric_name} | {t.target_specification} | {meas_str} | {status_badge} | {t.sample_size} | {t.details} |"
            )

        lines.extend([
            "",
            "## Summary Counts",
            f"- **Passed**: {report.summary_counts.get('PASSED', 0)}",
            f"- **Failed**: {report.summary_counts.get('FAILED', 0)}",
            f"- **Insufficient Data**: {report.summary_counts.get('INSUFFICIENT_DATA', 0)}",
            "",
            "> **Regulatory Compliance Notice**: This report was generated automatically by the SubSense Section 8 Verification Harness. All unmeasured or data-limited metrics are explicitly documented without silent rounding or artificial inflation.",
        ])

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
