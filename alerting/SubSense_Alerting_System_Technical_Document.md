# SubSense Alerting & Decision Support System
## Technical Design Document

**Project:** SubSense — AI-Enabled Wireless Surface Mesh Network for Real-Time Subsidence Monitoring
**Module:** Alerting & Decision Support System (Step 6 of the SubSense Workflow)
**Document Type:** Technical Architecture & Design Specification
**Prepared for:** Smart India Hackathon Submission

---

## 1. Purpose & Scope

The Alerting System is the decision-support layer of SubSense that converts AI/ML risk assessments into timely, actionable notifications for mine operators, safety officers, regulators, and nearby communities. Its objective is to close the gap between **detection** (an anomaly identified in sensor/AI data) and **action** (evacuation, load restriction, reinforcement, or regulatory reporting) with minimum latency and maximum reliability.

This document covers:
- Alert classification and severity model
- Triggering and escalation logic
- Notification channel architecture (digital and non-digital)
- Data flow from AI layer to end recipient
- Explainability and confidence scoring attached to alerts
- False-alarm feedback and threshold retraining loop
- Reliability, failover, and offline behavior
- Data model, APIs, and integration points
- Security, compliance, and multi-tenancy considerations
- Testing and validation strategy

Out of scope: sensor hardware design, mesh routing protocol internals, and GIS rendering (covered in separate documents for those subsystems). This document references their outputs as inputs to alerting.

---

## 2. Design Goals

| Goal | Description |
|---|---|
| Low latency | Critical alerts must reach operators within seconds of threshold crossing at the gateway; on-ground siren activation must be near-instantaneous and independent of network state. |
| Redundant delivery | No single channel failure (SMS gateway down, no internet) should silence a critical alert. |
| Explainability | Every alert must state *why* it fired — which nodes, sensors, and confidence level — to build operator trust and reduce alert fatigue. |
| Tiered response | Alerts must be proportionate to risk; not every anomaly should escalate to evacuation-level notification. |
| Inclusivity | Alerts must reach non-digital, low-literacy populations near the mine, not just operators with dashboards. |
| Self-improving | The system must learn from operator feedback on false alarms without manual retraining effort. |
| Auditability | Every alert, its trigger data, and operator response must be logged for DGMS-compliant regulatory reporting. |

---

## 3. System Architecture Overview

```
                       ┌────────────────────────────┐
                       │   AI/ML Intelligence Layer   │
                       │ (Anomaly, GNN correlation,   │
                       │  severity, time-to-critical) │
                       └──────────────┬───────────────┘
                                      │ Risk Event (JSON)
                                      ▼
                       ┌────────────────────────────┐
                       │      Alert Rule Engine       │
                       │  (severity classification,   │
                       │   deduplication, escalation) │
                       └──────────────┬───────────────┘
               ┌──────────────────────┼───────────────────────┐
               ▼                      ▼                       ▼
   ┌───────────────────┐  ┌────────────────────┐   ┌─────────────────────┐
   │ On-Ground Local     │  │ Operator/Regulator  │   │ Community Alert      │
   │ Siren & Beacon      │  │ Notification Service │   │ Service (SMS/Voice)  │
   │ (edge-triggered,     │  │ (SMS, Email, Push,   │   │ (localized language) │
   │  no network needed)  │  │  Dashboard banner)   │   │                       │
   └───────────────────┘  └──────────┬───────────┘   └──────────┬───────────┘
                                      ▼                          ▼
                       ┌────────────────────────────────────────────┐
                       │   Alert & Delivery Audit Log (time-series /  │
                       │   relational store) — feeds DGMS reports and │
                       │   the false-alarm feedback loop              │
                       └────────────────────────────────────────────┘
```

**Key architectural principle:** the alerting pipeline is split into an **edge-local path** (siren/beacon, triggered directly from on-node/gateway TinyML inference, zero network dependency) and a **cloud-mediated path** (SMS/email/push/voice, dependent on gateway backhaul). This ensures the fastest possible response is never blocked by connectivity.

---

## 4. Alert Severity Model

Three tiers, consistent with the baseline system requirement for tiered SMS/email/app alerts:

| Tier | Trigger Condition | Recipients | Channels | Target Latency |
|---|---|---|---|---|
| **Advisory** | Minor deviation from baseline in a single node/sensor; low confidence anomaly; early-stage trend detected by LSTM forecast | Site operators, planners | Dashboard notification, daily digest email | < 5 min |
| **Warning** | Cross-node/cross-sensor correlated anomaly; GNN spatial correlation confirms a spreading pattern; medium-to-high confidence; time-to-critical estimate > defined safe threshold (configurable, e.g. > 48 hrs) | Site operators, safety officers, regulators | SMS, email, push notification, dashboard banner | < 60 sec |
| **Critical** | High-confidence multi-node correlated anomaly; time-to-critical estimate below safety threshold (e.g. < configurable hours); rapid progression rate detected | Site operators, safety officers, regulators, DGMS-registered authority, community in affected zone | On-ground siren (immediate, edge-triggered), SMS, push, email, automated voice call, community SMS/voice | Siren: near-instant; digital: < 30 sec |

Severity is not purely threshold-based on raw sensor values — it is the output of the AI/ML Intelligence Layer's severity estimation, which combines anomaly score, spatial correlation strength, progression rate, and the time-to-critical countdown. The Alert Rule Engine consumes this pre-classified severity and applies the delivery matrix above.

---

## 5. Alert Triggering & Escalation Logic

### 5.1 Trigger Sources
1. **Edge/TinyML trigger** — runs on gateway (and select nodes) even with zero connectivity. Uses a lightweight, pre-trained anomaly threshold model. Can independently fire the local siren/beacon for Critical-tier, node-local events without waiting for cloud confirmation.
2. **Cloud AI trigger** — the full anomaly detection, GNN correlation, LSTM forecasting, and time-to-critical models run cloud-side once gateway data syncs, producing a richer, corroborated risk event that may upgrade, downgrade, or confirm the edge-level classification.

### 5.2 Rule Engine Responsibilities
- **Deduplication:** suppress repeated alerts for the same ongoing event within a configurable cool-down window (avoids alert flooding from a single sustained deformation event).
- **Escalation:** if a Warning-tier event's time-to-critical countdown drops below threshold on a subsequent evaluation cycle, escalate automatically to Critical without requiring a new independent trigger.
- **De-escalation:** if corroborating cloud-side analysis downgrades an edge-triggered alert (e.g., sensor fault ruled out as false positive), issue a retraction/update notice to all channels that received the original alert.
- **Correlation window:** batches events from the same risk zone within a short time window into a single alert to avoid fragmenting one physical event into many notifications.

### 5.3 Pseudocode — Rule Engine Core Loop
```
on new_risk_event(event):
    zone = event.risk_zone_id
    if is_duplicate(event, zone, cooldown_window):
        merge_into_existing_alert(event, zone)
        return

    severity = classify_severity(event.anomaly_score,
                                  event.correlation_strength,
                                  event.progression_rate,
                                  event.time_to_critical)

    alert = create_alert(zone, severity, event.confidence,
                          event.explanation, event.contributing_nodes)

    if severity == CRITICAL and event.source == EDGE:
        trigger_local_siren(zone)          # immediate, no network dependency

    dispatch_to_channels(alert, severity_channel_matrix[severity])
    log_alert(alert)
    schedule_reevaluation(alert, interval=REEVAL_INTERVAL)
```

---

## 6. Notification Channel Architecture

### 6.1 On-Ground Local Siren/Beacon
- Triggered directly by node/gateway TinyML inference — does not depend on cloud roundtrip.
- Provides immediate audible/visual warning to workers physically present at a high-risk node before any remote alert is delivered.
- State (armed/triggered/reset) is reported back to the cloud once connectivity resumes, for audit logging.

### 6.2 Operator & Regulator Notifications
- **SMS Gateway:** integrates with a telecom SMS API/aggregator; used for Warning and Critical tiers.
- **Email Service:** transactional email service for Advisory digests and Warning/Critical detailed reports (includes explanation, confidence score, contributing sensors, and a dashboard deep-link).
- **Push Notifications:** mobile app push (Firebase Cloud Messaging or equivalent) to the operator/regulator mobile dashboard app.
- **Dashboard Banner:** real-time in-app banner/alert center entry, visible immediately on next dashboard load or via WebSocket push if the dashboard is already open.

### 6.3 Community Alert Channel
- **Localized-language SMS:** templated messages in the regional language of the affected population, sent to residents pre-registered (opt-in) in the affected geofenced zone.
- **Automated Voice Calls:** IVR-based voice call in the local language for low-literacy or non-digital residents, triggered for Critical-tier events in populated zones.
- Community alerts are geofenced strictly to the affected risk zone using the GIS layer's zone boundary output, to avoid unnecessary panic outside the actual risk area.

### 6.4 Channel Failover
- If the primary SMS aggregator fails (timeout/non-2xx response), the system automatically retries via a secondary aggregator.
- If all digital channels are unreachable due to backhaul outage, the gateway continues buffering the alert and the on-ground siren remains the sole live safety mechanism until connectivity is restored — at which point queued alerts flush immediately with an original-timestamp marker.

---

## 7. Explainability & Confidence Scoring

Every alert payload includes:
- **Confidence score** (0–100%) from the AI/ML layer, reflecting model certainty.
- **Contributing nodes/sensors** — explicit list of which physical nodes and sensor types (tilt, vibration, displacement, crack) triggered the correlation.
- **Trigger summary** — a short, human-readable explanation (e.g., "Correlated tilt and vibration anomaly detected across 4 adjacent nodes; deformation rate trending upward over 6 hours").
- **Time-to-critical estimate** — the AI-generated countdown window, where applicable.

This addresses the false-alarm and black-box AI concerns identified in the problem statement, and gives operators enough context to make an informed override or acknowledgment decision rather than blindly trusting or dismissing an alert.

---

## 8. False-Alarm Feedback & Threshold Learning Loop

1. Operator marks a delivered alert as **Confirmed**, **False Positive**, or **Unclear** via the dashboard.
2. Feedback is logged against the specific alert record, including which nodes/sensors were implicated.
3. A scheduled retraining/threshold-adjustment job periodically ingests this feedback to:
   - Adjust anomaly-detection sensitivity per node/zone (nodes prone to false positives get threshold recalibration).
   - Update the correlation model's confidence calibration.
4. Updated thresholds/models are version-controlled and pushed to gateways (and edge TinyML models, where feasible) during the next connectivity window.
5. All threshold changes are logged with the feedback data that justified them, for auditability.

---

## 9. Data Model (Alert Domain)

### 9.1 Core Entities

**Alert**
| Field | Type | Description |
|---|---|---|
| alert_id | UUID | Primary key |
| tenant_id | UUID | Mine site / operator (multi-tenant isolation) |
| risk_zone_id | UUID | Associated GIS risk zone |
| severity | Enum(Advisory, Warning, Critical) | Current severity |
| status | Enum(Active, Escalated, De-escalated, Resolved, Retracted) | Lifecycle state |
| confidence_score | Float | 0.0–1.0 |
| time_to_critical_hours | Float, nullable | AI-estimated countdown |
| explanation | Text | Human-readable trigger summary |
| contributing_nodes | Array[node_id] | Nodes implicated |
| contributing_sensors | Array[sensor_type] | Sensor types implicated |
| source | Enum(Edge, Cloud) | Origin of trigger |
| created_at / updated_at | Timestamp | — |

**AlertDelivery**
| Field | Type | Description |
|---|---|---|
| delivery_id | UUID | Primary key |
| alert_id | UUID | FK → Alert |
| channel | Enum(Siren, SMS, Email, Push, DashboardBanner, VoiceCall, CommunitySMS) | — |
| recipient_ref | String | Operator ID, phone number, or zone-registered-resident ID |
| delivery_status | Enum(Queued, Sent, Delivered, Failed, Retrying) | — |
| attempted_at / delivered_at | Timestamp | — |

**AlertFeedback**
| Field | Type | Description |
|---|---|---|
| feedback_id | UUID | Primary key |
| alert_id | UUID | FK → Alert |
| operator_id | UUID | Who provided feedback |
| verdict | Enum(Confirmed, FalsePositive, Unclear) | — |
| notes | Text, nullable | — |
| submitted_at | Timestamp | — |

**CommunityRegistrant**
| Field | Type | Description |
|---|---|---|
| registrant_id | UUID | Primary key |
| tenant_id | UUID | Mine site |
| risk_zone_id | UUID | Geofenced zone |
| phone_number | String | — |
| preferred_language | String | For SMS/voice templating |
| opted_in | Boolean | Consent flag |

---

## 10. API Surface (Representative)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/alerts` | POST | Internal — Rule Engine creates a new alert |
| `/api/v1/alerts/{id}` | GET | Retrieve alert detail, including explanation and delivery status |
| `/api/v1/alerts/{id}/feedback` | POST | Operator submits Confirmed/FalsePositive/Unclear verdict |
| `/api/v1/alerts/{id}/retract` | POST | Issue a de-escalation/retraction notice |
| `/api/v1/alerts?zone_id=&severity=&status=` | GET | Filtered alert listing for dashboard |
| `/api/v1/community/registrants` | POST/GET | Manage community opt-in registrants per zone |
| `/api/v1/alerts/{id}/deliveries` | GET | Delivery audit trail per channel |
| `/webhooks/sms-gateway/status` | POST | Inbound delivery-status callback from SMS aggregator |
| `/webhooks/voice-gateway/status` | POST | Inbound delivery-status callback from IVR provider |

All endpoints are scoped by `tenant_id` (multi-tenant isolation) and require role-based authorization (Operator, Safety Officer, Regulator, Admin).

---

## 11. Reliability, Offline Behavior & Failover

- **Edge independence:** the siren/beacon path never depends on cloud reachability — it is the last line of defense during total connectivity loss.
- **Gateway buffering:** alerts generated during a backhaul outage are timestamped and queued locally; on reconnection, they are flushed with original timestamps preserved (not re-timestamped as "now") to maintain accurate audit trails.
- **Multi-provider SMS/voice failover:** primary/secondary aggregator configuration per tenant, with automatic retry and provider health tracking.
- **At-least-once delivery guarantee:** delivery attempts are retried with exponential backoff up to a configurable maximum; permanently failed deliveries are flagged for manual operator follow-up.
- **Idempotency:** alert creation and delivery dispatch are idempotent keyed on `(risk_zone_id, event_window)` to prevent duplicate notifications from retried upstream events.

---

## 12. Multi-Tenancy Considerations

- All alert, delivery, feedback, and registrant data is partitioned by `tenant_id` at the database and API layer.
- Channel configuration (SMS aggregator credentials, voice IVR provider, language templates) is tenant-configurable, allowing each mine site/operator to use region-appropriate providers and languages.
- Cross-tenant data isolation is enforced at the query layer (row-level security or equivalent) to prevent one operator from viewing another site's alerts — required for the platform's national multi-coalfield scaling goal.

---

## 13. Security & Compliance

- All alert payloads and delivery logs are encrypted at rest and in transit (TLS for API/webhook traffic).
- Role-based access control restricts who can acknowledge, retract, or override alerts.
- Full audit trail (alert lifecycle + delivery attempts + operator feedback) is retained to support DGMS-compliant regulatory report generation (Step 7 of the overall SubSense workflow).
- Community registrant phone numbers are stored with explicit opt-in consent and are usable only for zone-relevant safety alerts, not general communication.

---

## 14. Testing & Validation Strategy

| Test Type | Focus |
|---|---|
| Unit tests | Severity classification logic, deduplication, escalation/de-escalation rules |
| Integration tests | End-to-end flow from simulated AI risk event → rule engine → all channel dispatchers |
| Chaos/failover tests | Simulated SMS aggregator outage, backhaul disconnection, gateway offline buffering and flush-on-reconnect |
| Load tests | Burst of correlated risk events across many nodes/zones to validate deduplication and no channel flooding |
| Field simulation | Historical replay mode (dashboard feature) used to replay past deformation events and verify correct alert tiering would have been produced |
| Community alert tests | Language template correctness, geofencing accuracy of registrant targeting |

---

## 15. Summary

The SubSense Alerting System is designed as a two-path architecture — an always-available edge-triggered local safety mechanism, and a richer cloud-mediated multi-channel notification system — bound together by a severity-tiered, explainable, and self-improving rule engine. It extends safety awareness beyond the control room to on-site workers and surrounding communities, while maintaining the auditability required for DGMS regulatory compliance and the multi-tenant scalability required for nationwide rollout across Indian coalfields.
