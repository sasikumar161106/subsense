# SubSense Life-Safety Alerting & Decision Support System

[![Tests: 66 Passed](https://img.shields.io/badge/Tests-66%20Passed-brightgreen.svg)]()
[![DGMS Compliant](https://img.shields.io/badge/DGMS-Compliant-blue.svg)]()
[![AES-256-GCM](https://img.shields.io/badge/Security-AES--256--GCM-darkgreen.svg)]()
[![Dual-Path Edge/Cloud](https://img.shields.io/badge/Architecture-Dual--Path%20Edge%2FCloud-orange.svg)]()

**Smart India Hackathon Submission — DGMS-Compliant Mine Subsidence Life-Safety Alerting Platform**

SubSense is a real-time life-safety alerting and decision support system engineered for coal mine subsidence monitoring. Operating downstream of spatial AI/ML models (Graph Neural Networks for strata spatial correlation, LSTM velocity forecasting, and TinyML edge anomaly detectors), SubSense provides classified, deduplicated, escalation-aware alerting, physical edge siren actuation (< 1.2s), resilient omni-channel dispatch, closed-loop human feedback, and DGMS-compliant immutable auditing.

---

## 🚀 Cold Clone Quickstart (One Setup Command, One Start Command)

From the root repository directory:

```bash
# 1. Install all dependencies across backend and frontend
npm run setup

# 2. Launch Backend API (port 3000) & Frontend React Console (port 5173) concurrently
npm start
```

- **Operator Console UI**: `http://localhost:5173`
- **Backend REST API**: `http://localhost:3000/api/v1`
- **Edge WebSocket Feed**: `ws://localhost:3000/ws/alerts`

> [!NOTE]
> All repositories, mock coalfield tenants, risk zones, and operator credentials are automatically initialized in-memory on startup. No manual database setup or Docker dependencies are required for demonstration.

---

## 🏛️ System Architecture

SubSense enforces a **Dual-Path Edge/Cloud Architecture**:
- **Autonomous Edge Path**: Edge gateway at the pit-head triggers physical sirens/strobes in **< 1.2s** via local GPIO simulation and emits pure WebSocket edge events (`siren ACTIVE`). This path operates independently of internet connectivity or cloud database availability.
- **Cloud Omni-Channel Path**: High-throughput multi-channel distribution (SMS Broadcast, Voice IVR automated telephone calls, Community Geofenced SMS across 5 Indian languages, Mobile Push, Email Digests) backed by circuit-breaker failover and an offline backlog buffer.

For detailed sequence diagrams, state models, and circuit breaker flowcharts, refer to [ARCHITECTURE.md](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/ARCHITECTURE.md).

---

## 🔑 Authentication, RBAC & Multi-Tenancy

Authentication uses signed JSON Web Tokens (JWT). Two pre-seeded operational roles provide strict multi-tenant data isolation:

| User | Password | Role | Entitled Scope | Key Permissions |
|---|---|---|---|---|
| `officer_jharia` | `subsense123` | Mine Safety Officer | Jharia Block II (`tenant-jharia-01`) | View Jharia alerts, submit feedback, issue retractions |
| `officer_raniganj` | `subsense123` | Mine Safety Officer | Raniganj Deep Mining (`tenant-raniganj-02`) | View Raniganj alerts, submit feedback, issue retractions |
| `dgms_inspector` | `dgms2026` | Regulator / DGMS Inspector | Multi-Tenant (All Coalfields) | Cross-mine read-only access, one-click DGMS Audit CSV export |

### Tenant Isolation Guarantee
SubSense implements repository-level query scoping guards. Cross-tenant access requests or unauthorized feedback submissions immediately return HTTP `403 Forbidden`. The console header allows instantaneous switching between users to demonstrate zero data leakage.

---

## 💻 Live Operator Console (React + Leaflet)

The Operator Console is a dark industrial, glassmorphic decision support dashboard designed for high-stress control rooms:

1. **Interactive Mine Map**: OpenStreetMap dark tiles plotting live risk zones with radar pulse markers:
   - 🔴 **Pulsing Red**: Critical Subsidence Hazard (immediate evacuation required).
   - 🟡 **Pulsing Amber**: Warning (bench tension cracking).
   - 🔵 **Pulsing Blue**: Advisory (instrument drift or minor settlement).
   - 🟢 **Green**: Normal Strata Baseline.
2. **Autonomous Edge Siren Banner**: Driven purely by local WebSocket edge events (`siren ACTIVE`), completely decoupled from cloud database polling. Includes audio siren tone generator and visual strobe.
3. **Live Alert Feed**: Real-time cards featuring:
   - Client-side ticking **Time-to-Critical Countdown** (`XXh XXm XXs`).
   - Composite AI confidence scores.
   - Sensor attribution tags (e.g. `Tiltmeter +4.2°`, `Extensometer 18.4 mm`).
4. **Alert Explainability & Delivery Matrix Modal**:
   - Technical narrative explaining the kinematics and multi-sensor correlation.
   - Per-channel delivery receipt tracking (Siren, SMS, Voice, Push, Community SMS).
   - One-click feedback form generating cryptographic SHA-256 integrity hashes.
   - Strictly guarded Retraction Notice submission (only permitted for false positives).
5. **Historical Log & Statutory Audit Export**:
   - Multi-field filtering (Zone, Severity, Status, Date).
   - **One-Click DGMS Audit Export**: Instant RFC-4180 CSV export formatted for DGMS Annual Safety Audit filings.

---

## 🛡️ Security & Compliance Highlights

- **AES-256-GCM Encryption at Rest**: All civilian community phone numbers are encrypted at rest using AES-256 in Galois/Counter Mode with 128-bit authentication tags and unique initialization vectors (IV).
- **HTTPS / TLS Support**: Optional TLS termination enabled via `USE_HTTPS=true` in `backend/.env`.
- **API Rate Limiting & Input Validation**: Inbound public webhooks (`/webhooks/*`) protected by `express-rate-limit` (100 req/min) and strict payload schema validators.
- **Cryptographic Sign-Off**: Every feedback acknowledgment and sensor recalibration commits a deterministic SHA-256 payload hash to an append-only audit trail.

---

## 🧪 Resiliency Proof Scripts

SubSense includes 3 standalone, runnable resilience scripts:

### 1. Gateway Network Outage & Edge Autonomy (`npm run test:outage`)
```bash
npm run test:outage
```
- Sever the gateway's network access (`SIMULATE_GATEWAY_OUTAGE = true`).
- Ingest a local Critical event: **Edge Siren actuates in < 1.2s autonomously**.
- Digital channels buffer in the encrypted local `BacklogBuffer`.
- Network reconnected: Buffered deliveries flush to cloud store, **preserving the original alert creation timestamp**.

### 2. Historical Slope-Failure Replay (`npm run test:replay`)
```bash
npm run test:replay
```
- Streams 48 hours of progressive slope displacement readings from `synthetic_slope_failure_curve.csv`.
- Validates that the rule engine auto-escalates to Critical at **T+33h**, providing **15 hours of evacuation lead time** ahead of physical bench failure at T+48h.

### 3. High-Throughput Load Test (`npm run test:load`)
```bash
npm run test:load
```
- Concurrently pushes **10,000 RiskEvents** across **50 mine risk zones**.
- Verifies 0 dropped events, zero deadlocks, and ~50–60 events/second sustained throughput.

---

## 🔬 Automated Test Suite (66 Tests across 10 Suites)

Run the full automated test suite:
```bash
npm test
```

Individual targeted suites:
```bash
npm run test:unit         # Severity boundaries, deduplication, cooldown, encryption
npm run test:integration  # JWT auth, RBAC permissions, cross-tenant isolation, deliveries
npm run test:chaos        # Automated network severance, edge siren, buffer replay
```

---

## 📖 Live Demonstration Guide for Judges

For the exact, chronological sequence to follow during a hackathon evaluation, see:
👉 **[DEMO_SCRIPT.md](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/DEMO_SCRIPT.md)**

---

## 📂 Project Repository Structure

```
Alert_System/
├── package.json              # Root npm scripts (setup, start, test, outage, load, replay)
├── ARCHITECTURE.md           # System design & dual-path edge/cloud specifications
├── DEMO_SCRIPT.md            # Step-by-step judge demonstration walkthrough
├── README.md                 # Primary system documentation
├── backend/
│   ├── src/
│   │   ├── api/              # Express REST server, JWT middleware, routes & webhooks
│   │   ├── audit/            # DGMS immutable audit logger & RFC-4180 CSV exporter
│   │   ├── channels/         # Adapters (Siren, SMS, Voice, Community, Email, Push)
│   │   ├── db/               # Repository layer with query-level tenant isolation guards
│   │   ├── models/           # Domain schemas, RBAC types, RiskZone metadata
│   │   ├── rule-engine/      # Severity classifier, deduplication, cooldown, escalation
│   │   ├── scripts/          # Resiliency proof scripts (outage, load-test, replay)
│   │   ├── security/         # AES-256-GCM cipher and JWT authentication tokens
│   │   └── simulator/        # 8-scenario interactive simulator
│   ├── tests/                # 10 Jest test suites (unit, integration, chaos)
│   └── data/                 # Synthetic progressive slope-failure time series
└── frontend/
    ├── src/
    │   ├── components/       # Map, LiveFeed, SirenBanner, AlertModal, HistoricalLog
    │   ├── types.ts          # Frontend domain types
    │   ├── App.tsx           # React root coordinator & WebSocket consumer
    │   └── index.css         # Dark glassmorphic styling & pulsing radar CSS
    └── vite.config.ts        # Vite build & proxy config
```
