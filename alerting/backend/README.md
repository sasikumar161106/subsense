# SubSense Alerting & Decision Support System (Phase 1 & Phase 2)

**Smart India Hackathon Submission — DGMS-Compliant Mine Subsidence Alerting Platform**

SubSense provides a real-time, life-safety alerting and decision support platform for coal-mine subsidence monitoring. Built downstream of AI/ML edge and cloud models (GNN spatial correlation, LSTM forecasting, TinyML edge anomaly detection), SubSense transforms raw risk anomalies into classified, deduplicated, escalation-aware alerts, dispatches them across resilient omni-channel adapters, and guarantees closed-loop human feedback and continuous sensor recalibration.

---

## Architecture Overview

```
                          ┌────────────────────────────┐
                          │   AI/ML Intelligence Layer │
                          │ (GNN, LSTM, Edge TinyML)   │
                          └──────────────┬─────────────┘
                                         │ RiskEvent JSON
                                         ▼
                          ┌────────────────────────────┐
                          │     Alert Rule Engine      │
                          │ - Classify Severity        │
                          │ - Deduplication & Cooldown │
                          │ - Auto-Escalation (< 6h)   │
                          │ - Node Recalibration Decays│
                          │ - Explainability Generator │
                          └──────────────┬─────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
      ┌─────────────────────────┐                 ┌─────────────────────────┐
      │   Autonomous Edge Bus   │                 │   Digital Dispatcher    │
      │  (Hardware Siren/Strobe)│                 │   (Concurrent Fanout)   │
      │   Latency: < 1.2s       │                 └────────────┬────────────┘
      │   Zero Network Dep      │                              │
      └─────────────────────────┘             ┌────────────────┼────────────────┐
                                              ▼                ▼                ▼
                                      ┌───────────────┐┌───────────────┐┌───────────────┐
                                      │ Resilient SMS ││Email & Push   ││Community SMS &│
                                      │Circuit Breaker││Multipart Brief││Voice IVR Call │
                                      │Failover < 8s  ││Daily Digest   ││5 Languages    │
                                      └───────────────┘└───────────────┘└───────────────┘
                                              │                │                │
                                              └────────────────┼────────────────┘
                                                               ▼
                                              ┌─────────────────────────────────┐
                                              │   Real-time WebSocket Server    │
                                              │     (/ws/alerts broadcast)      │
                                              └────────────────┬────────────────┘
                                                               ▼
                                              ┌─────────────────────────────────┐
                                              │    DGMS Append-Only Audit Log   │
                                              │ (SHA-256 Feedback & Recalibrate)│
                                              └─────────────────────────────────┘
```

---

## 1. Severity → Channel Matrix (Phase 2)

| Severity | Dispatched Channels | Delivery Characteristic |
|---|---|---|
| **Advisory** | `DashboardBanner`, `Email` | Daily digest email batching (not sent per alert); real-time UI banner broadcast. |
| **Warning** | `SMS`, `PushNotification`, `DashboardBanner`, `Email` | High-priority SMS with Circuit Breaker; rich HTML email brief with one-click ack; WebSocket banner; FCM mock. |
| **Critical** | `Siren`, `SMS`, `VoiceIVR`, `DashboardBanner`, `CommunitySMS` | Autonomous edge GPIO siren (< 1.2s guaranteed); SMS broadcast; Voice IVR automated phone call with DTMF ack; geofenced localized Community SMS. |

---

## 2. Channel Adapters & Resilience Architecture

Every channel implements a uniform `send(alert, recipient)` interface with strict error boundaries:

### 1. `SirenActuator` (Edge Autonomous Actuator)
- **Local Edge GPIO Simulation**: Actuates on-ground sirens and strobes.
- **Strict Latency**: Guaranteed execution well under **1.2s** (measured at ~0.1ms to 200ms in simulation).
- **Network Independence**: Does **not** block on or depend on internet/cloud network calls.
- **WebSocket Event**: Pushes immediate `siren ACTIVE` event on the local WebSocket topic for frontend visibility.
- **Never Retried**: Fire-and-forget local hardware logic prevents cascading edge delays.

### 2. `SmsAdapter` & Circuit Breaker Failover
- **Primary SMS Gateway**: Dispatches high-priority SMS alerts to mine operators and control rooms.
- **Circuit Breaker**: Tracks provider health. If primary returns 5xx errors or takes `> 8.0s` to respond:
  - Trips circuit to `OPEN`.
  - Automatically routes traffic to **Secondary SMS Gateway** (Satellite / GSM backup).
  - Cools down for 30s before testing recovery with `HALF_OPEN`.
- **Failover Tested**: Failover verified to trigger and deliver within `6ms` in automated simulation tests.

### 3. `EmailAdapter` (Multipart HTML Brief & Daily Digest)
- **Advisory Batching**: Batches advisory alerts into a daily digest queue rather than bombarding control room inboxes.
- **Warning/Critical Immediate Dispatch**: Sends rich multipart HTML briefs containing:
  - Time-to-critical countdown badge.
  - Contributing sensor attribution table.
  - GIS subsidence contour map placeholder.
  - One-click feedback acknowledgment link directing to `/api/v1/alerts/{id}/feedback`.

### 4. `PushNotificationAdapter`
- Realistic FCM (Firebase Cloud Messaging) mock adapter generating message IDs, high-priority payloads, and vibration tickets.

### 5. `DashboardBannerAdapter`
- Embedded WebSocket server running at `/ws/alerts`.
- Broadcasts real-time alert JSON and edge siren actuation frames to all connected UI clients.

### 6. `VoiceIvrAdapter`
- Simulates emergency automated telephone calls to mine managers.
- Logs call placement, 28-second simulated duration, and DTMF keypress `'1'` (evacuation acknowledged).

### 7. `CommunitySmsAdapter` (Geofenced & Localized)
- Geofenced to send evacuation alerts **only** to registered residents (`CommunityRegistrant`) in the affected `risk_zone_id`.
- Localized templates across **5 mining region languages**:
  - `hi` (Hindi)
  - `bn` (Bengali)
  - `sat` (Santali)
  - `or` (Odia)
  - `en` (English)

### 8. Backlog Buffer & Digital Retry Backoff
- **Exponential Backoff**: Base 2.0 multiplier, up to 5 attempts for failed digital channels.
- **Offline Backlog Buffer**: If digital channels are completely unreachable, pending deliveries are buffered in memory and flushed when connectivity recovers, **preserving the original `alert_created_at` timestamp**.

---

## 3. Explainability Engine

Generated dynamically at alert creation:
- **`composite_confidence`**: Calibrated percentage string (e.g., `"94.2%"`).
- **`contributing_sensor_attribution`**: Array of concrete sensor readings with engineering units:
  ```json
  [
    { "node_id": "20000000-0000-0000-0000-000000000201", "modality": "tilt", "reading": "+4.2°" },
    { "node_id": "20000000-0000-0000-0000-000000000202", "modality": "displacement", "reading": "18.4 mm" },
    { "node_id": "20000000-0000-0000-0000-000000000203", "modality": "velocity", "reading": "2.45 mm/h" }
  ]
  ```
- **`trigger_narrative`**: Dynamically interpolated from real event metrics:
  `"Cross-correlated 3-point shear strain detected along Underground Longwall Seam IV; displacement rate accelerated 45% over 6h."`
- **`time_to_critical_hours`**: Pass-through from event, supplemented with kinematic extrapolation fallback (`distance / velocity_delta`) when LSTM predictions are unavailable.

---

## 4. Feedback Loop & DGMS Recalibration

### Cryptographically Linked Feedback (`POST /api/v1/alerts/:id/feedback`)
- Writes an `AlertFeedback` row.
- Calculates and stores a deterministic cryptographic SHA-256 hash:
  `SHA-256(alert_id + raw_payload)`
  guaranteeing tamper-proof operator sign-offs for DGMS safety compliance.

### Strictly Guarded Retraction (`POST /api/v1/alerts/:id/retract`)
- Enforces strict safety compliance: an alert can **only** be retracted if a prior `FalsePositive` or `HardwareDefect` verdict was recorded. Requests without this verdict are rejected with HTTP 400.
- Automatically fans out a **Retraction Notice** across **every single channel** that the original alert used (SMS, Push, Email, DashboardBanner).

### Sensor Sensitivity Recalibration Job
- Manually or periodically triggered script (`run_recalibration_job(sign_off_person)`).
- Aggregates false alarms per sensor node and decays node sensitivity weights (e.g. from `1.0` to `0.85`).
- Feeds back into `classify_severity`, dynamically discounting noisy sensors during future risk evaluations.
- Emits an append-only `AuditLog` entry recording the DGMS-required human sign-off name.

---

## 5. Inbound Webhooks

- `POST /webhooks/sms-gateway/status`: Inbound SMS delivery status callback updating `AlertDelivery` status to `Delivered` or `Failed` with timestamp.
- `POST /webhooks/voice-gateway/status`: Inbound Voice gateway callback updating call duration, status, and DTMF response.

---

## 6. Getting Started & Verification

### Prerequisites
- Node.js 18+
- Docker (optional for PostgreSQL + TimescaleDB)

### Step 1: Install Dependencies
```bash
npm install
```

### Step 2: Run Full Automated Test Suite (41 Tests across 7 Suites)
```bash
npm test
```
Validates:
- Rule engine classification, deduplication, escalation, idempotency.
- Siren actuation latency (< 1.2s).
- SMS circuit breaker failover (< 8s).
- Localized community SMS across all 5 languages.
- Email daily digest batching.
- Backlog buffer timestamp preservation.
- Cryptographic feedback hash & guarded retraction.
- Inbound webhooks for SMS and Voice.
- Full end-to-end simulator.

### Step 3: Run the 8-Step Interactive Simulator
```bash
npm run simulate
```
Executes all real-world scenarios:
1. Low-confidence single-node anomaly → Advisory + explainability.
2. GNN-correlated multi-node anomaly → Warning + 4-channel fanout.
3. Cooldown window suppression → Merged telemetry without duplicates.
4. Accelerating tension crack → Auto-flip to Critical + Autonomous Edge Siren (< 1.2s).
5. SMS Gateway Outage → Circuit Breaker triggers failover to Secondary within 8s.
6. Operator Feedback + Retraction Notice fanout on all original channels.
7. Node Recalibration job with Chief Inspector sign-off.
8. DGMS Audit Trail validation across all transitions.

### Step 4: Start the API Server
```bash
npm run dev
```
Binds HTTP REST API to `http://localhost:3000` and WebSocket server to `ws://localhost:3000/ws/alerts`.
