"""
Active Learning Operator Feedback API and Interface.
Supports exactly four regulatory DGMS feedback classes:
1. Confirmed Ground Movement
2. False Alarm — Surface Blast
3. False Alarm — Machinery Vibration
4. Sensor Hardware Fault
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ConfigDict

from .negative_mining import NegativeSampleMiningRepository, NegativeSampleRecord


class FeedbackLabel(str, Enum):
    CONFIRMED_GROUND_MOVEMENT = "Confirmed Ground Movement"
    FALSE_ALARM_SURFACE_BLAST = "False Alarm — Surface Blast"
    FALSE_ALARM_MACHINERY_VIBRATION = "False Alarm — Machinery Vibration"
    SENSOR_HARDWARE_FAULT = "Sensor Hardware Fault"


class OperatorLabelSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: Annotated[str, Field(min_length=1, max_length=128)]
    node_id: Annotated[str, Field(min_length=1, max_length=64)]
    timestamp: Annotated[datetime, Field()]
    operator_id: Annotated[str, Field(min_length=1, max_length=64)]
    feedback_label: FeedbackLabel
    notes: Optional[str] = None
    feature_vector: Optional[List[float]] = None
    sensor_deltas: Optional[Dict[str, float]] = None


# Shared in-memory or persisted repository instance
negative_mining_repo = NegativeSampleMiningRepository()
labeled_submissions: List[OperatorLabelSubmission] = []

router = APIRouter(prefix="/api/v1/feedback", tags=["Active Retraining Feedback"])


@router.post("/label", status_code=status.HTTP_201_CREATED)
def submit_operator_label(submission: OperatorLabelSubmission) -> Dict[str, Any]:
    """
    Submits operator ground-truth verification.
    Confirmed false alarms are automatically ingested into the negative mining repository.
    """
    labeled_submissions.append(submission)

    is_false_alarm = submission.feedback_label in [
        FeedbackLabel.FALSE_ALARM_SURFACE_BLAST,
        FeedbackLabel.FALSE_ALARM_MACHINERY_VIBRATION,
        FeedbackLabel.SENSOR_HARDWARE_FAULT,
    ]

    mined_sample_id = None
    if is_false_alarm and submission.feature_vector:
        record = negative_mining_repo.add_sample(
            alert_id=submission.alert_id,
            node_id=submission.node_id,
            timestamp=submission.timestamp,
            label=submission.feedback_label.value,
            feature_vector=submission.feature_vector,
            sensor_deltas=submission.sensor_deltas or {},
            operator_notes=submission.notes,
        )
        mined_sample_id = record.sample_id

    return {
        "status": "ACCEPTED",
        "alert_id": submission.alert_id,
        "label": submission.feedback_label.value,
        "is_false_alarm_mined": is_false_alarm,
        "mined_sample_id": mined_sample_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/samples")
def list_feedback_submissions(limit: int = Query(default=50, ge=1, le=500)) -> List[Dict[str, Any]]:
    """Lists submitted operator feedback records."""
    return [s.model_dump() for s in labeled_submissions[-limit:]]


@router.get("/ui", response_class=HTMLResponse)
def get_operator_feedback_ui() -> str:
    """
    Minimal, responsive operator dashboard UI for rapid incident adjudication.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SubSense Layer 4: Operator Incident Labeling</title>
    <style>
        :root {
            --bg: #0d1117;
            --card-bg: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --alert-critical: #f85149;
            --alert-warning: #d29922;
            --success: #2ea043;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }
        .container {
            max-width: 960px;
            margin: 0 auto;
        }
        h1 {
            color: #fff;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
            font-size: 24px;
        }
        .incident-card {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 12px;
            margin-bottom: 12px;
        }
        .badge-critical { background-color: rgba(248,81,73,0.2); color: var(--alert-critical); border: 1px solid var(--alert-critical); }
        .badge-warning { background-color: rgba(210,153,34,0.2); color: var(--alert-warning); border: 1px solid var(--alert-warning); }
        .summary-box {
            background-color: #0d1117;
            border-left: 4px solid var(--accent);
            padding: 12px 16px;
            font-size: 14px;
            line-height: 1.5;
            margin: 14px 0;
            border-radius: 0 6px 6px 0;
        }
        .form-group {
            margin: 16px 0;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 13px;
        }
        select, input, textarea {
            width: 100%;
            padding: 10px;
            background-color: #0d1117;
            border: 1px solid var(--border);
            color: #fff;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 14px;
        }
        button {
            background-color: var(--success);
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background-color: #2c974b; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SubSense Layer 4: Operator Adjudication Portal</h1>
        <p style="color:#8b949e; font-size: 14px;">Active Retraining & Continuous Mining Gateway (DGMS Level 2/3 Adjudication)</p>

        <div class="incident-card" id="incident-card">
            <span class="badge badge-critical">CRITICAL INCIDENT PENDING REVIEW</span>
            <div class="grid-2">
                <div><strong>Node ID:</strong> SS-PANEL7-N042</div>
                <div><strong>Location:</strong> Zone 3B, Panel 7</div>
                <div><strong>Timestamp:</strong> 2026-09-09 16:30:00 UTC</div>
                <div><strong>Calculated Confidence:</strong> 0.892</div>
            </div>

            <div class="summary-box">
                <strong>Plain-Language Explanation:</strong><br>
                CRITICAL WARNING (Zone 3B, Panel 7): Triggered by sustained tilt surge (+0.24° over 30 min) and differential displacement (+4.8 mm/hr) at Node SS-PANEL7-N042. Corroborated by high spatial attention (α=0.88) with adjacent nodes N041 and N044 along the active extraction face. InSAR macro-crosscheck confirms 12mm historical depression basin.
            </div>

            <form id="labelForm">
                <input type="hidden" id="alertId" value="ALERT-20260909-042">
                <input type="hidden" id="nodeId" value="SS-PANEL7-N042">

                <div class="form-group">
                    <label for="feedbackClass">Geotechnical Adjudication Class (Strict 4-Class Schema):</label>
                    <select id="feedbackClass" required>
                        <option value="Confirmed Ground Movement">Confirmed Ground Movement</option>
                        <option value="False Alarm — Surface Blast">False Alarm — Surface Blast</option>
                        <option value="False Alarm — Machinery Vibration">False Alarm — Machinery Vibration</option>
                        <option value="Sensor Hardware Fault">Sensor Hardware Fault</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="operatorId">Operator ID / DGMS Badge Number:</label>
                    <input type="text" id="operatorId" placeholder="e.g. DGMS-MIN-GEO-884" required>
                </div>

                <div class="form-group">
                    <label for="notes">Geotechnical Observation Notes:</label>
                    <textarea id="notes" rows="3" placeholder="Describe face inspection observations, crack gauges, or blast schedule correlation..."></textarea>
                </div>

                <button type="button" onclick="submitLabel()">Commit Label to Retraining Pipeline</button>
            </form>
            <div id="resultBox" style="margin-top: 14px; font-weight: 600; display: none;"></div>
        </div>
    </div>

    <script>
        async function submitLabel() {
            const btn = document.querySelector('button');
            btn.disabled = true;
            btn.innerText = "Submitting...";
            
            const payload = {
                alert_id: document.getElementById('alertId').value,
                node_id: document.getElementById('nodeId').value,
                timestamp: new Date().toISOString(),
                operator_id: document.getElementById('operatorId').value,
                feedback_label: document.getElementById('feedbackClass').value,
                notes: document.getElementById('notes').value,
                feature_vector: [0.24, 0.05, 0.008, 4.8, 4.8, 1.2, 0.45, 2.1, 45.0, 18.5, 0.72, 0.42],
                sensor_deltas: {"tilt_deg": 0.24, "disp_mm": 4.8}
            };

            try {
                const res = await fetch('/api/v1/feedback/label', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                const box = document.getElementById('resultBox');
                box.style.display = 'block';
                if (res.ok) {
                    box.style.color = '#2ea043';
                    box.innerText = "✓ Successfully committed! Sample ID: " + (data.mined_sample_id || "RECORDED");
                } else {
                    box.style.color = '#f85149';
                    box.innerText = "✗ Submission rejected: " + JSON.stringify(data);
                }
            } catch (err) {
                const box = document.getElementById('resultBox');
                box.style.display = 'block';
                box.style.color = '#f85149';
                box.innerText = "✗ Network Error: " + err.message;
            } finally {
                btn.disabled = false;
                btn.innerText = "Commit Label to Retraining Pipeline";
            }
        }
    </script>
</body>
</html>"""
