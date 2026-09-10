# SubSense Life-Safety Alerting System: Judge Live Demo Script

This script walks judges through a complete, step-by-step verification of the **SubSense Alerting & Decision Support System**. Every step is reproducible from a cold clone with zero manual database configuration.

---

## 📋 Quick Reference Credentials

| Role | Username | Password | Tenant / Scope |
|---|---|---|---|
| **Mine Safety Officer (Jharia)** | `officer_jharia` | `subsense123` | Jharia Block II (`tenant-jharia-01`) |
| **Mine Safety Officer (Raniganj)** | `officer_raniganj` | `subsense123` | Raniganj Deep Mining Complex (`tenant-raniganj-02`) |
| **DGMS Regulator / Inspector** | `dgms_inspector` | `dgms2026` | Multi-Tenant (All Coalfields - Read-Only) |

---

## ⚡ Phase 0: Cold Clone Setup & Startup

From a terminal in the root repository directory:

```bash
# 1. Install dependencies for both backend and frontend (single command)
npm run setup

# 2. Launch both Backend (API + WS) and Frontend (Vite Console) concurrently
npm start
```

- **Backend API & Edge WebSocket**: Running at `http://localhost:3000` (WebSocket: `ws://localhost:3000/ws/alerts`)
- **Operator Console UI**: Open `http://localhost:5173` in your browser.

> [!NOTE]
> All in-memory fallback repositories and pre-configured tenant configurations are seeded automatically on boot. No PostgreSQL installation or Docker configuration is required for this live demo.

---

## 🎯 Step 1: Live Operator Console & Edge Siren Verification

1. In your browser at `http://localhost:5173`:
   - Notice the **Header**: Select active user `officer_jharia` (Jharia Coalfield Block II).
   - The WebSocket indicator should show green: **`EDGE WS CONNECTED`**.
2. **Interactive Mine Map**:
   - Leaflet map shows Jharia risk zones (`zone-jharia-01: Pit Head Bench A`, `zone-jharia-02: South Overburden Dump`).
   - Radar markers display live severity pulses (Green: Normal, Blue: Advisory, Amber: Warning, Red: Critical).
3. **Trigger the Real-Time Multi-Scenario Simulator**:
   - Open a secondary terminal window in the project directory and run:
     ```bash
     npm run simulate
     ```
4. **Observe the Live Console Reacting Instantly**:
   - **Autonomous Edge Siren**:
     - At Step 4 of the simulator (Critical Subsidence Event), the top of the UI triggers the **flashing red strobe `Autonomous Edge Siren ACTIVE` banner** with audible emergency frequency pulses.
     - *Key Judge Defense Point*: This banner is driven **purely by the local WebSocket event** emitted by the edge GPIO actuator, completely decoupled from database polling.
   - **Ticking Time-To-Critical Countdown**:
     - Critical alerts display a client-side ticking countdown (`XXh XXm XXs`) warning operators of imminent bench failure.
   - **Sensor Explainability Attribution**:
     - Sensor chips show which instruments contributed to the alert (`InSAR Displacement`, `Borehole Extensometer`, `Piezometer`).

---

## 🛡️ Step 2: Tenant Isolation & Multi-Tenancy Verification

*Objective: Prove that tenant data never leaks across coalfields or roles.*

1. In the console header dropdown, switch the active user to:
   - **`officer_raniganj` (Raniganj Deep Mining Complex)**.
2. **Verify Data Isolation**:
   - The map pans automatically to Raniganj coordinates (`23.6210° N, 87.1245° E`).
   - The Live Feed and Historical Table show **zero Jharia alerts**. Only Raniganj zones (`zone-raniganj-01: Shaft 4 Incline`, `zone-raniganj-02: North Pit Wall`) appear.
3. Switch back to **`officer_jharia`**:
   - Only Jharia alerts and zones are displayed.
4. Switch to **`dgms_inspector` (Regulator / DGMS Inspector)**:
   - The Inspector has a comprehensive multi-tenant view showing alerts from **both Jharia and Raniganj**.
   - Notice that the **Retraction** and **Feedback** submission buttons are disabled or clearly marked as read-only. Attempting to submit feedback as a regulator triggers an HTTP `403 Forbidden` guard.

---

## 🤝 Step 3: Human-in-the-Loop Feedback & Retraction Flow

*Objective: Show operator decision support, cryptographic audit trail, and false alarm retraction.*

1. As **`officer_jharia`**, click on any alert card in the **Live Feed** to open the **Alert Explainability Modal**.
2. Review the **Delivery Matrix**:
   - Check the per-channel dispatch status (Siren, SMS, Voice IVR, Dashboard, Community SMS) showing delivery timestamps and confirmation IDs.
3. **Submit Operator Feedback**:
   - Select disposition: `Confirmed Subsidence Movement` (or `False Positive`).
   - Enter notes: `Subsurface crack confirmed along Bench 4 haul road by shift supervisor.`
   - Click **`Submit Operator Acknowledgment`**.
   - The alert moves to Acknowledged status, and the SHA-256 integrity hash is permanently committed to the DGMS audit trail.
4. **Issue an Official Retraction**:
   - For an active alert, select `False Alarm / Hardware Glitch` in feedback and submit a **Retraction Notice**.
   - Watch the system dispatch a **Retraction Notice across EVERY channel originally contacted** (SMS, Push, Dashboard, Email) to ensure miners and safety teams are informed of the all-clear.

---

## ⚡ Step 4: Resiliency Proof 1 — Telecom Severance & Edge Autonomy

*Objective: Prove that the edge siren works with zero network connectivity, digital messages buffer locally, and flushed records retain original incident timestamps.*

In your terminal, execute:
```bash
npm run test:outage
```

**What the judge sees in terminal output**:
1. **Network Severed**: The primary telecom gateway and internet links are deliberately disabled (`SIMULATE_GATEWAY_OUTAGE = true`).
2. **Autonomous Siren Actuated**: The edge siren fires in **< 1.2 seconds** locally via GPIO and pushes the `siren ACTIVE` frame.
3. **Digital Channels Buffered**: SMS, Community SMS, and Voice IVR fail the primary and secondary links and are stored in the local encrypted `BacklogBuffer`.
4. **Network Restored**: Uplink connectivity is re-established.
5. **Timestamp Preservation Verified**:
   ```
   [BACKLOG BUFFER] Flushing 3 buffered deliveries...
   [VERIFICATION SUCCESS] Cloud Alert Delivery created_at matches original edge alert timestamp!
   ```
   *Judge Defense Point*: The timestamp on the cloud alert record is the exact moment of strata displacement, not the delayed reconnection time. This prevents distortion in accident investigations.

---

## 📈 Step 5: Resiliency Proof 2 — Historical Progressive Slope-Failure Replay

*Objective: Prove the rule engine escalates to Critical 15 hours before physical slope failure on a realistic synthetic slope curve.*

In your terminal, run:
```bash
npm run test:replay
```

**What the judge sees**:
- Streams 48 hours of time-series sensor data (`backend/data/synthetic_slope_failure_curve.csv`).
- Hours 1–18: Anomaly score stays low (< 0.40) -> Status: `NORMAL`.
- Hour 19: Anomaly reaches 0.44 -> Escalates to `ADVISORY`.
- Hour 27: Anomaly reaches 0.72 -> Escalates to `WARNING`.
- Hour 33: Anomaly reaches 0.88, velocity delta spikes to 2.45 mm/h -> **Escalates to `CRITICAL`**.
- **Result**: System alerts Critical at **T+33 hours**, providing **15 full hours of evacuation lead time** ahead of the synthetic failure point at T+48 hours.

---

## 🚀 Step 6: Resiliency Proof 3 — High-Throughput Load Test

*Objective: Prove zero dropped alerts and no deadlock under extreme stress.*

In your terminal, run:
```bash
npm run test:load
```

**What the judge sees**:
- Ingests **10,000 simulated RiskEvents** across **50 mine zones**.
- Metric summary:
  - Total Events Ingested: `10,000`
  - Dropped Events: `0`
  - Deadlocks Detected: `0`
  - Total Alert Deliveries Dispatched: `15,000+`
  - Average Throughput: `~50–60 events/second`

---

## 📑 Step 7: One-Click DGMS Annual Safety Audit Export (CSV)

*Objective: Demonstrate statutory DGMS regulatory compliance with one click.*

1. In the Operator Console (`http://localhost:5173`), scroll to the **Historical Alerts & Statutory DGMS Audit Trail** table.
2. Click the green button: **`Download DGMS Audit Report (CSV)`**.
3. Open the downloaded `DGMS_Annual_Safety_Audit_Report.csv` in Excel or a text editor:
   - Includes full immutable transition records: `created`, `merged`, `escalated`, `acknowledged`, `retracted`, `recalibrated`.
   - Contains exact event timestamps, actor IDs, transition reason, and SHA-256 payload integrity hashes.

---

## 🧪 Step 8: Full Automated Test Suite

Run the full automated test suite containing 66 automated tests across 10 suites:
```bash
npm test
```
All 66 tests pass cleanly, covering:
- Unit tests: Severity threshold boundaries, cooldown deduplication, escalation triggers, AES-256-GCM encryption at rest.
- Integration tests: JWT authentication, RBAC permission barriers, tenant isolation rejection, full channel delivery matrix, DGMS CSV export.
- Chaos tests: Automated telecom gateway failure, edge siren autonomy, and backlog buffer replay.
