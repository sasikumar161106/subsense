# SubSense Alerting & Decision Support System (Layer 6)
## Complete Repository Details & Technical Architecture Specification

---

## 1. Executive Summary & Life-Safety Mandate

The **SubSense Alerting & Decision Support System (Layer 6)** is the mission-critical life-safety and operational decision-support layer of the **SubSense Smart Coal Mine Subsidence Platform** (developed for the Smart India Hackathon 2026). Operating directly downstream of the spatial AI/ML intelligence layers (Graph Neural Networks for strata spatial correlation, LSTM velocity forecasting, Kriging geostatistical surfaces, and TinyML edge anomaly detectors), SubSense converts complex geomechanical inferences into immediate, actionable, and auditable life-safety interventions.

In open-cast and underground coal mining, sudden strata shear, bench tensile fracturing, or goaf collapse can trigger catastrophic slope failures and shaft failures with very little warning. SubSense closes the gap between **detection** (sensor anomaly identified) and **action** (evacuation siren, automated conveyor cutoff, emergency SMS broadcast, community geofenced alert) with sub-second edge latency and zero single points of failure.

### Core System Attributes:
- **Repository Location**: `c:\Users\sasik\Desktop\SIH 2026\Subsense\Alert_System`
- **Regulatory Framework**: Directorate General of Mines Safety (DGMS) Guidelines (India) — Coal Mines Regulations (CMR) 2017 (Regulations 104 & 105) for Strata Control and Monitoring Plans (SCAMP)
- **Architectural Tenet**: **Dual-Path Edge/Cloud Principle** (Autonomous Edge Siren $< 1.2\text{s}$ + Cloud Omni-Channel Distribution)
- **Technology Stack**:
  - **Backend**: Node.js, TypeScript, Express, WebSockets (`ws`), Jest, Supertest
  - **Frontend**: React 18, TypeScript, Vite, Leaflet, OpenStreetMap, Lucide Icons, Glassmorphic Dark Industrial CSS
  - **Security**: AES-256-GCM Encryption at Rest, SHA-256 Cryptographic Audit Chain, JWT RBAC
- **Test Suite Status**: **66 / 66 Passed (100%)** across 10 comprehensive Jest test suites
- **SLA Performance**: Autonomous Edge Siren actuation in **$< 1.2\text{ s}$**; Sustained throughput of **50–60 events/second** without dropped alerts

---

## 2. End-to-End System Architecture & Dual-Path Principle

In deep coal mining environments, terrestrial communication backhauls (cellular base stations, microwave towers, fiber runs) are routinely severed by strata deformation, heavy monsoon storms, or pit-wall slumping. Relying on cloud round-trips to trigger life-safety sirens is unacceptable.

SubSense enforces a **Dual-Path Edge/Cloud Architecture**:
1. **Autonomous Edge Path (Low Latency / Offline Resilient)**:
   - Deployed at the edge gateway node physically positioned at the pit head or mine substation.
   - Upon detecting a **Critical** subsidence vector, the **Siren Actuator triggers autonomously** via local GPIO simulation in **under 1.2 seconds**.
   - Operates with **zero dependence** on external internet transit, cellular towers, or cloud database availability.
   - Pushes an immediate `siren ACTIVE` event on the local edge WebSocket feed.
2. **Cloud Orchestration & Omni-Channel Path (High Throughput / Multi-Tier)**:
   - Distributes alerts across external public communication channels (Broadcast SMS, Voice IVR automated telephone calls, Community geofenced SMS across 5 Indian languages, Mobile Push, Email Digests).
   - Governed by an intelligent **Circuit Breaker** (50ms fast failover) and an encrypted **Offline Backlog Buffer**: queued alerts flush to cloud storage upon reconnection with **original incident timestamps preserved**.

```
                           +-------------------------------------------------------+
                           |              UPSTREAM SPATIAL AI/ML LAYER             |
                           |   InSAR, Tiltmeters, Extensometers, Piezometers       |
                           |   (GNN Mesh Correlation + LSTM + Kriging + TinyML)    |
                           +---------------------------+---------------------------+
                                                       | RiskEvent JSON
                                                       v
+-----------------------------------------------------------------------------------------------------------------------+
|                                    SUBSENSE MINE GATEWAY (PIT-HEAD SUBSTATION)                                        |
|                                                                                                                       |
|  [Ingestion / Webhooks] ──> [Rule Engine Core]                                                                        |
|  (/api/v1/events/risk-event)     │                                                                                    |
|                                  ├──> 1. Severity Classifier (DGMS 3-Tier Matrix: Advisory, Warning, Critical)        |
|                                  ├──> 2. Deduplication & Cooldown Engine (Velocity Jump > 1.5x Override)               |
|                                  ├──> 3. Escalation Evaluator (P-Delta Acceleration & Multi-Sensor Concordance)       |
|                                  └──> 4. Explainability Payload Generator (Kinematics & Sensor Attribution)          |
|                                                  │                                                                    |
|               +----------------------------------+----------------------------------+                                 |
|               │                                                                     │                                 |
|               v Critical Subsidence Vector                                          v Omni-Channel Dispatch           |
|  +─────────────────────────────────────+                         +─────────────────────────────────────+              |
|  |     AUTONOMOUS EDGE PATH            |                         |    CLOUD OMNI-CHANNEL DISPATCHER    |              |
|  | - GPIO Pit-Head Siren (< 1.2s)      |                         | - Primary SMS Gateway               |              |
|  | - Local Edge WebSocket Feed         |                         | - Voice IVR Telephony Gateway       |              |
|  | - Complete Backhaul Independence   |                         | - Geofenced Community SMS           |              |
|  +──────────────────┬──────────────────+                         | - Mobile Push & Email Digest        |              |
|                     │                                            +──────────────────┬──────────────────+              |
|                     v                                                               │                                 |
|          +─────────────────────+                                                    v                                 |
|          | Physical 120dB Horn |                                 +─────────────────────────────────────+              |
|          | & Emergency Strobe  |                                 |   GATEWAY RESILIENCE SUBSYSTEM      |              |
|          +─────────────────────+                                 | - Circuit Breaker (50ms failover)   |              |
|                                                                  | - Secondary Satellite Uplink        |              |
|                                                                  | - Offline Encrypted Backlog Buffer  |              |
|                                                                  +──────────────────┬──────────────────+              |
+-------------------------------------------------------------------------------------|---------------------------------+
                                                                                      │
                                                                                      v Reconnection Flush
                                                                   +─────────────────────────────────────+
                                                                   | CLOUD DATABASE & AUDIT SUBSYSTEM    |
                                                                   | - PostgreSQL / TimescaleDB Store    |
                                                                   | - SHA-256 Cryptographic Audit Trail |
                                                                   | - Original Incident Timestamps Kept |
                                                                   +──────────────────┬──────────────────+
                                                                                      │
                                                                                      v
+-----------------------------------------------------------------------------------------------------------------------+
|                                    OPERATOR CONSOLE & REGULATORY PORTAL (REACT 18)                                    |
|                                                                                                                       |
|  - Live Leaflet Mine Map with Severity Radar Pulses (Red, Amber, Blue, Green)                                         |
|  - Client-Side Ticking Time-to-Critical (TTC) Countdown (XXh XXm XXs)                                                 |
|  - Explainability & Channel Delivery Matrix Modal                                                                     |
|  - Strict Human-in-the-Loop Feedback & Official Retraction Workflow                                                   |
|  - Multi-Tenant Isolation (Jharia Block II vs. Raniganj Deep Mining)                                                  |
|  - One-Click DGMS Statutory Annual Audit CSV Export (RFC-4180 Compliant)                                              |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Complete Directory & File Inventory

The `Alert_System` folder contains **67 total source code, configuration, documentation, and asset files** organized into a modular full-stack architecture:

```
Alert_System/
│
├── ARCHITECTURE.md                            # Comprehensive technical architecture & sequence diagrams
├── DEMO_SCRIPT.md                             # Step-by-step evaluation script for hackathon live judging
├── README.md                                  # Executive summary, quickstart guide, and feature matrix
├── SubSense_Alerting_System_Technical_...md   # Source technical design specification document
├── package.json                               # Root package orchestration (setup, start, test, outage, replay)
│
├── backend/                                   # Backend Node.js / TypeScript service
│   ├── .env / .env.example                    # Environment configuration (ports, JWT secret, AES key, TLS)
│   ├── docker-compose.yml                     # Optional container deployment for Postgres/Redis
│   ├── jest.config.js                         # Jest test framework configuration
│   ├── package.json                           # Backend dependencies & script targets
│   ├── tsconfig.json                          # TypeScript compiler options
│   ├── README.md                              # Backend module documentation
│   │
│   ├── src/                                   # Application source code
│   │   ├── api/                               # Express REST API & HTTP/WS server
│   │   │   ├── app.ts                         # Express app bootstrap, CORS, rate limits, route mounting
│   │   │   ├── server.ts                      # HTTP & WebSocket server initialization on port 3000
│   │   │   └── routes/                        # REST endpoint controllers
│   │   │       ├── alerts.ts                  # Alert ingestion, listing, detail, feedback & retraction routes
│   │   │       ├── audit.ts                   # DGMS audit log retrieval & RFC-4180 CSV export
│   │   │       ├── auth.ts                    # User login, JWT issuance, and user context validation
│   │   │       ├── community.ts               # Civilian community registrant management
│   │   │       └── webhooks.ts                # Inbound public webhooks for external risk events
│   │   │
│   │   ├── audit/                             # Regulatory compliance auditing
│   │   │   └── logger.ts                      # DGMS audit logger, SHA-256 cryptographically linked transactions
│   │   │
│   │   ├── channels/                          # Omni-channel notification subsystem
│   │   │   ├── circuit-breaker.ts             # 3-state circuit breaker (Closed, Open, Half-Open) with 50ms trip
│   │   │   ├── dispatcher.ts                  # Multi-channel orchestrator, backlog buffer queue, retraction sender
│   │   │   └── adapters/                      # Channel delivery adapters
│   │   │       ├── base.ts                    # ChannelAdapter abstract interface
│   │   │       ├── siren.ts                   # Autonomous Edge Siren adapter (GPIO simulation, <1.2s actuation)
│   │   │       ├── sms.ts                     # High-priority broadcast SMS adapter (SMPP/SMSC simulator)
│   │   │       ├── voice.ts                   # Automated IVR telephone call dispatch adapter
│   │   │       ├── community-sms.ts           # Geofenced multilingual community SMS (5 Indian languages)
│   │   │       ├── dashboard.ts               # Real-time WebSocket event broadcaster with strobe/audio payloads
│   │   │       ├── email.ts                   # Direct multipart briefs & batched daily digest briefs
│   │   │       └── push.ts                    # FCM high-priority mobile push notification adapter
│   │   │
│   │   ├── db/                                # Storage layer & multi-tenancy
│   │   │   ├── client.ts                      # Database client connector
│   │   │   └── repository.ts                  # Query-level tenant isolation guards, seed data, in-memory fallback
│   │   │
│   │   ├── models/                            # Shared domain data models
│   │   │   └── types.ts                       # RiskEvent, Alert, DeliveryRecord, CommunityRegistrant, Feedback
│   │   │
│   │   ├── rule-engine/                       # Core analytical rule engine
│   │   │   ├── index.ts                       # RuleEngine facade orchestrating full alert lifecycle
│   │   │   ├── classifier.ts                  # DGMS 3-tier severity classifier (Advisory, Warning, Critical)
│   │   │   ├── deduplication.ts               # Temporal cooldown window & velocity jump threshold > 1.5x
│   │   │   ├── escalation.ts                  # P-Delta velocity acceleration & multi-sensor corroboration
│   │   │   ├── deescalation.ts                # Automatic de-escalation & retraction dispatch
│   │   │   ├── explainability.ts              # Natural-language kinematics & sensor attribution synthesizer
│   │   │   ├── idempotency.ts                 # SHA-256 event fingerprint deduplication
│   │   │   ├── spatial.ts                     # Geofenced risk zone distance calculator for evacuations
│   │   │   ├── recalibration.ts               # False-alarm feedback aggregator & dynamic sensitivity attenuation
│   │   │   ├── reevaluation.ts                # Periodic re-evaluation of ticking Time-to-Critical countdowns
│   │   │   └── dispatchers.ts / actuators.ts  # Low-level channel dispatch helpers
│   │   │
│   │   ├── scripts/                           # Runnable resiliency & load verification proofs
│   │   │   ├── simulate-outage.ts             # Gateway network severance, edge siren, and backlog buffer flush
│   │   │   ├── historical-replay.ts           # 48-hour progressive slope failure curve replay (15h lead time)
│   │   │   └── load-test.ts                   # 10,000 events across 50 zones benchmark (0 dropped alerts)
│   │   │
│   │   ├── security/                          # Security, cryptography, and access control
│   │   │   ├── auth.ts                        # JWT issuance, verification, RBAC middleware (MSO vs Regulator)
│   │   │   ├── encryption.ts                  # AES-256-GCM cipher/decipher for community phone numbers
│   │   │   └── https.ts                       # TLS / HTTPS server configuration
│   │   │
│   │   └── simulator/                         # Multi-scenario demonstration engine
│   │       ├── index.ts                       # Simulator runner orchestrating 5 standard demo scenarios
│   │       └── scenarios.ts                   # Scenario definitions (Settlement, Warning, Critical, Retract, Deescalate)
│   │
│   └── tests/                                 # Automated Jest test suite (66 tests)
│       ├── api.test.ts                        # REST API endpoint integration tests
│       ├── channels.test.ts                   # Omni-channel dispatchers and adapter unit tests
│       ├── explainability.test.ts             # Sensor attribution and plain-language summary tests
│       ├── feedback-retract.test.ts           # Cryptographic feedback, retraction, and recalibration tests
│       ├── phase3-chaos.test.ts               # Network severance, edge siren decoupling, backlog buffer recovery
│       ├── phase3-integration.test.ts         # JWT auth, RBAC, tenant isolation, end-to-end integration tests
│       ├── phase3-unit.test.ts                # Severity classification, deduplication, cooldown, AES-256-GCM
│       ├── rule-engine.test.ts                # Rule engine transitions and life-safety escalation logic tests
│       ├── simulator.test.ts                  # Execution of all 5 simulator scenarios
│       └── webhooks.test.ts                   # Webhook ingestion and validation tests
│
└── frontend/                                  # Operator Decision Support Console (React 18 + Vite)
    ├── index.html                             # Single-page application entry HTML
    ├── package.json                           # Frontend dependencies (React 18, Leaflet, Lucide)
    ├── tsconfig.json                          # TypeScript configuration
    ├── vite.config.ts                         # Vite build & proxy configuration
    ├── dist/                                  # Production compiled bundle (388 KB JS, 3.7 KB CSS)
    │
    └── src/                                   # Frontend source code
        ├── main.tsx                           # Application entry point
        ├── App.tsx                            # Root console layout, WebSocket hook, user switching, tabs
        ├── App.css / index.css                # Dark industrial design system, glassmorphism, radar animations
        ├── types.ts                           # Client domain types matching backend contracts
        │
        └── components/                        # UI Component library
            ├── Header.tsx                     # Tenant switcher (Jharia, Raniganj, DGMS), edge WS status badge
            ├── SirenBanner.tsx                # Flashing red strobe banner & audio tone generator
            ├── Map.tsx                        # Leaflet map with dark tiles, risk polygons, radar pulse markers
            ├── LiveFeed.tsx                   # Live alert feed with ticking TTC countdown (XXh XXm XXs)
            ├── AlertDetailModal.tsx           # Explainability narrative, delivery matrix, feedback & retraction form
            └── HistoricalLog.tsx              # Historical alert audit table with One-Click DGMS CSV export
```

---

## 4. In-Depth Subsystem Analysis

### 4.1 Rule Engine Core & Alert Lifecycle (`backend/src/rule-engine/`)
The rule engine governs the complete lifecycle of ground subsidence events, converting multi-sensor kinematic vectors into classified alerts:

```
[RiskEvent Ingested]
         │
         ├──> Deduplication Engine ──> [Merged into Existing Active Alert]
         │    (Within Cooldown & Velocity < 1.5x)
         │
         └──> Severity Classifier
              │
              ├── Advisory ─────────> [Dashboard Banner + Batched Email Digest]
              │
              ├── Warning ──────────> [Broadcast SMS + Mobile Push + Immediate Email + Audio-Visual UI]
              │
              └── Critical ─────────> 1. [Autonomous Edge Siren (< 1.2s GPIO / WS)]
                                      2. [High-Priority SMS Broadcast]
                                      3. [Automated Voice IVR Callout]
                                      4. [Geofenced Community Multilingual SMS]
                                      5. [Persistent Strobe on Operator Console]
```

- **Severity Classification (`classifier.ts`)**:
  - Implements the DGMS 3-tier severity matrix:
    - **`Advisory`**: Anomaly score $> 0.40$, confidence $> 0.50$. Indicates minor instrument drift or localized settlement without immediate failure risk.
    - **`Warning`**: Anomaly score $> 0.65$, confidence $> 0.70$. Indicates correlated strata movement with tension crack opening.
    - **`Critical`**: Anomaly score $> 0.85$, confidence $> 0.85$ **OR** Time-to-Critical $< 15\text{ minutes}$ **OR** kinematic velocity $> 5.0\text{ mm/hr}$. Requires immediate siren activation and evacuation.
- **Deduplication & Cooldown (`deduplication.ts`)**:
  - Prevents operator alarm fatigue by suppressing repeated alerts for the same physical risk zone within a configurable cooldown window (default: 30 minutes).
  - **P-Delta Velocity Jump Override**: If displacement velocity increases by $> 1.5\times$ over the previous reading, cooldown is bypassed immediately to escalate the alert.
- **Escalation & De-escalation (`escalation.ts`, `deescalation.ts`)**:
  - Automatically escalates an existing Warning to Critical if subsequent sensor cycles detect accelerating strain or if the predictive Time-to-Critical drops below threshold.
  - When ground stabilization is verified or a cloud retrain disproves an edge anomaly, the engine issues an official **Retraction Notice** to all previously contacted recipients.
- **Dynamic Sensitivity Recalibration (`recalibration.ts`)**:
  - Automatically incorporates operator feedback on false alarms.
  - Decrements localized node sensitivity by **$15.0\%$** for nodes identified in false positive reviews, raising the baseline threshold without manual engineering intervention.

---

### 4.2 Omni-Channel Notification Subsystem (`backend/src/channels/`)
The notification subsystem delivers multi-tier alerts across 7 distinct delivery channels:

| Channel | Adapter | Target Audience | Mechanism & Latency |
| :--- | :--- | :--- | :--- |
| **Autonomous Edge Siren** | `siren.ts` | Underground miners & pit-head workers | Simulated GPIO output triggering 120 dB acoustic horn and visual strobe in **$< 1.2\text{s}$** via local edge bus; emits WebSocket `siren ACTIVE` event |
| **Primary Broadcast SMS** | `sms.ts` | Safety officers, mine managers, shift supervisors | High-priority SMSC broadcast dispatching standardized DGMS incident codes within $< 30\text{s}$ |
| **Voice IVR Telephony** | `voice.ts` | Resident Geotechnical Manager, Mine Agent | Automated telephone callout playing synthesized text-to-speech evacuation instructions with mandatory DTMF key acknowledgment |
| **Community Geofenced SMS**| `community-sms.ts` | Nearby village populations within geofenced risk buffer | Multilingual SMS translated into **5 Indian regional languages** (Hindi, Bengali, Odia, Santali, English) based on recipient preference |
| **Dashboard WebSocket** | `dashboard.ts` | Control room operators | Real-time WebSocket push triggering flashing red strobe banner, radar pulse map markers, and audio alarm tone |
| **Mobile Push (FCM)** | `push.ts` | Field inspection teams & mobile engineers | High-priority Firebase Cloud Messaging (FCM) push payload triggering device wakeup and vibration |
| **Email Digest** | `email.ts` | Corporate management & regulatory inspectors | Multipart HTML/plain-text incident brief with kinematic graphs, or batched daily digest for Advisory events |

---

### 4.3 Gateway Resilience & Circuit Breaker (`backend/src/channels/`)
- **Circuit Breaker (`circuit-breaker.ts`)**:
  - Protects the system from cascading failures during external telecom outages.
  - Maintains 3 states: `CLOSED` (normal operation), `OPEN` (telecom failure detected), `HALF-OPEN` (probing recovery).
  - **Trip Threshold**: 3 consecutive failed dispatch attempts trigger the breaker `OPEN` within **$50\text{ ms}$**.
  - Automatically diverts traffic to the secondary satellite uplink.
- **Offline Encrypted Backlog Buffer (`dispatcher.ts`)**:
  - If all external communication links fail, outbound notifications are encrypted and queued in an in-memory/disk ring buffer.
  - **Original Timestamp Preservation**: When network connectivity is restored, buffered events flush to the cloud database preserving their original detection timestamps—crucial for post-disaster DGMS statutory inquiries.

---

### 4.4 Multi-Tenancy & Query-Level Isolation (`backend/src/db/repository.ts`)
- **Repository-Level Guard Architecture**:
  - Rather than relying on cloud PostgreSQL Row-Level Security (which breaks when edge gateways run disconnected in-memory fallbacks), SubSense enforces query-level tenancy filters in the repository layer.
  - Every database query and write operation validates the caller's `tenant_id` context.
  - Unauthorized cross-tenant access returns HTTP `403 Forbidden` instantly.
- **Pre-Seeded Operational Coalfield Tenants**:
  1. **`tenant-jharia-01`**: Jharia Coalfield Block II (Risk Zones: `zone-jharia-01: Pit Head Bench A`, `zone-jharia-02: South Overburden Dump`).
  2. **`tenant-raniganj-02`**: Raniganj Deep Mining Complex (Risk Zones: `zone-raniganj-01: Shaft 4 Incline`, `zone-raniganj-02: North Pit Wall`).
  3. **Multi-Tenant Regulator Scope**: DGMS regulatory inspection view across all coalfield concessions.

---

### 4.5 Security & Cryptographic Compliance (`backend/src/security/`)
- **AES-256-GCM Encryption at Rest (`encryption.ts`)**:
  - In compliance with Indian data privacy mandates, civilian phone numbers stored in `CommunityRegistrant` records are encrypted using **AES-256-GCM** with 128-bit authentication tags and unique initialization vectors (IV).
  - Raw phone numbers are never persisted in plaintext. The UI strictly renders masked phone strings (`+91 •••• 1234`).
- **Cryptographic Audit Hash Chain (`backend/src/audit/logger.ts`)**:
  - Every alert state change (`created`, `escalated`, `acknowledged`, `retracted`, `recalibrated`) generates an immutable audit entry.
  - Computes a deterministic SHA-256 digest of the alert payload:
    $$\text{Hash} = \text{SHA-256}(\text{alert\_id} \,\|\, \text{timestamp} \,\|\, \text{severity} \,\|\, \text{actor\_id} \,\|\, \text{action})$$
  - Enables regulatory authorities to mathematically prove that incident records have not been tampered with post-accident.
- **Role-Based Access Control (`auth.ts`)**:
  - **Mine Safety Officer (`MSO`)**: Full write access for assigned mine tenant; can acknowledge alerts, submit ground inspection notes, and issue retractions.
  - **Regulator (`REGULATOR`)**: Multi-tenant cross-mine visibility; **strictly read-only** (feedback submission and retraction routes return HTTP `403 Forbidden`).

---

### 4.6 Standalone Resiliency Proof Scripts (`backend/src/scripts/`)
The repository includes three automated, runnable resiliency proof scripts:

1. **Telecom Outage & Edge Autonomy (`simulate-outage.ts` / `npm run test:outage`)**:
   - Programmatically cuts external internet transit (`SIMULATE_GATEWAY_OUTAGE = true`).
   - Ingests a Critical risk event: **Autonomous Edge Siren actuates in $< 1.2\text{s}$**.
   - Digital notifications queue in the encrypted backlog buffer.
   - Reconnects network: Backlog flushes to cloud store with original creation timestamps preserved.
2. **Historical Slope-Failure Replay (`historical-replay.ts` / `npm run test:replay`)**:
   - Replays 48 hours of progressive slope displacement telemetry from an open-cast failure curve.
   - Proves that the rule engine auto-escalates to Critical at **T+33h**, providing **15 hours of evacuation lead time** ahead of physical bench collapse at T+48h.
3. **High-Throughput Load Benchmark (`load-test.ts` / `npm run test:load`)**:
   - Pushes **10,000 concurrent RiskEvents** across 50 simulated mine risk zones.
   - Proves zero dropped alerts, zero channel deadlocks, and sustained throughput of **50–60 events/second**.

---

### 4.7 Frontend Operator Decision Support Console (`frontend/src/`)
Built with React 18, TypeScript, and Vite, the console provides an intuitive, high-contrast dark industrial interface tailored for high-stress mine control rooms:

1. **Interactive Leaflet Mine Map (`Map.tsx`)**:
   - Dark OpenStreetMap tiles with custom SVG radar pulse markers representing risk zones:
     - 🔴 **Pulsing Red**: Critical Subsidence Hazard (immediate evacuation).
     - 🟡 **Pulsing Amber**: Warning (bench tension cracking).
     - 🔵 **Pulsing Blue**: Advisory (instrument drift or settlement).
     - 🟢 **Green**: Normal Strata Baseline.
   - Bounding polygon overlays tracing geotechnical panel perimeters.
2. **Autonomous Edge Siren Banner (`SirenBanner.tsx`)**:
   - Driven **purely by local edge WebSocket events** (`siren ACTIVE`), completely decoupled from database polling.
   - Features a high-visibility flashing red strobe and an embedded Web Audio API emergency tone synthesizer.
3. **Live Alert Feed (`LiveFeed.tsx`)**:
   - Real-time alert cards featuring a client-side ticking **Time-to-Critical Countdown** (`XXh XXm XXs`).
   - Displays AI confidence percentages and sensor attribution tags (e.g. `Tiltmeter +4.2°`, `Extensometer 18.4 mm`).
4. **Explainability & Delivery Matrix Modal (`AlertDetailModal.tsx`)**:
   - Plain-language technical narrative detailing strata kinematics and multi-sensor correlation.
   - Per-channel delivery receipt matrix tracking exact dispatch timestamps and confirmation IDs across all 7 channels.
   - Human-in-the-loop acknowledgment form committing SHA-256 signed feedback.
   - Official **Retraction Notice Issuer** (strictly guarded: only permitted for false alarms / hardware faults).
5. **Historical Audit Table (`HistoricalLog.tsx`)**:
   - Multi-field filtering by risk zone, severity tier, status, and date range.
   - **One-Click DGMS Audit Export**: Generates an RFC-4180 compliant CSV file formatted for statutory DGMS Annual Safety Audit filings.

---

## 5. Formal Data Contracts & REST API Reference

### 5.1 Inbound Risk Event Contract (`POST /api/v1/events/risk-event`)
Published by the upstream AI/ML inference layer into the alerting pipeline:

```json
{
  "event_id": "EVT-20260910-001",
  "site_id": "SITE-JHARIA-04",
  "zone_id": "zone-jharia-01",
  "anomaly_score": 0.89,
  "correlation_score": 0.82,
  "forecast_trend": "accelerating",
  "time_to_critical_hours": 0.25,
  "confidence_score": 0.91,
  "contributing_sensors": ["borehole_extensometer", "wireless_tiltmeter", "piezometer"],
  "explanation_text": "Correlated extensometer bed separation (+18.4mm) and tilt sag (+4.2 deg) across 3 adjacent nodes. Accelerating tertiary creep phase.",
  "event_timestamp": "2026-09-10T11:30:00Z"
}
```

### 5.2 Emitted Alert Domain Object
```json
{
  "id": "ALT-f86403b0-96e4-4de7-88cd-46d46691cfe0",
  "tenant_id": "tenant-jharia-01",
  "zone_id": "zone-jharia-01",
  "severity": "Critical",
  "status": "Active",
  "anomaly_score": 0.89,
  "confidence_score": 0.91,
  "time_to_critical_seconds": 900,
  "contributing_sensors": ["borehole_extensometer", "wireless_tiltmeter"],
  "explanation": "Correlated extensometer bed separation (+18.4mm) and tilt sag (+4.2 deg).",
  "siren_actuated": true,
  "siren_actuation_time_ms": 780,
  "created_at": "2026-09-10T11:30:00.780Z"
}
```

### 5.3 REST API Endpoints

| HTTP Method | Route | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | None | Authenticate user credentials; returns JWT token and tenant context |
| `GET`  | `/api/v1/auth/me` | Bearer JWT | Returns current authenticated user profile, role, and assigned tenant scope |
| `POST` | `/api/v1/alerts` | Bearer JWT | Ingests a new RiskEvent and evaluates rule engine classification |
| `GET`  | `/api/v1/alerts` | Bearer JWT | Lists alerts filtered by tenant, severity, zone, and operational status |
| `GET`  | `/api/v1/alerts/:id` | Bearer JWT | Returns full alert details including sensor attributions and audit timeline |
| `GET`  | `/api/v1/alerts/:id/deliveries` | Bearer JWT | Returns per-channel delivery records (status, timestamps, message IDs) |
| `POST` | `/api/v1/alerts/:id/feedback` | MSO Only | Submits operator verdict (Confirmed, FalsePositive, HardwareDefect) |
| `POST` | `/api/v1/alerts/:id/retract` | MSO Only | Issues official Retraction Notice across all originally dispatched channels |
| `GET`  | `/api/v1/audit/alerts` | Bearer JWT | Returns chronological DGMS audit trail with SHA-256 cryptographic hashes |
| `GET`  | `/api/v1/audit/export-csv` | Bearer JWT | Exports statutory RFC-4180 CSV audit file for DGMS regulatory reporting |
| `POST` | `/api/v1/community/registrants` | Bearer JWT | Registers civilian contact with AES-256-GCM encrypted phone number |
| `GET`  | `/api/v1/community/registrants` | Bearer JWT | Lists community registrants with masked phone numbers (`+91 •••• 1234`) |
| `POST` | `/api/v1/webhooks/risk-events` | API Key / Public | Public webhook endpoint accepting inbound AI/ML risk events |

---

## 6. Automated Test Suite & Verification Results

### 6.1 Jest Test Suite Performance
The backend test suite contains **66 automated tests across 10 test files** covering unit logic, integration paths, security boundaries, and chaos resilience:

```bash
cd backend && npm test
```

```
Test Suites: 10 passed, 10 total
Tests:       66 passed, 66 total
Snapshots:   0 total
Time:        18.423 s
```

### 6.2 Test Suite Coverage Breakdown

| Test Suite File | Tests | Coverage Scope | Result |
| :--- | :--- | :--- | :--- |
| [`tests/phase3-unit.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/phase3-unit.test.ts) | 12 | DGMS 3-tier severity thresholds, deduplication cooldown, AES-256-GCM encryption/decryption, rate limiting | **PASSED** |
| [`tests/rule-engine.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/rule-engine.test.ts) | 8 | P-Delta velocity escalation, multi-sensor concordance, automated de-escalation, idempotency | **PASSED** |
| [`tests/channels.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/channels.test.ts) | 8 | All 7 channel adapters, Circuit Breaker 3-state transitions, 50ms fast failover | **PASSED** |
| [`tests/explainability.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/explainability.test.ts) | 5 | Multi-sensor attribution extraction, plain-language kinematics summary generator | **PASSED** |
| [`tests/feedback-retract.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/feedback-retract.test.ts) | 4 | SHA-256 feedback linking, retraction notice multi-channel broadcast, -15% recalibration | **PASSED** |
| [`tests/api.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/api.test.ts) | 9 | REST API endpoints, input validation, 404/403 handlers, delivery tracking, CSV export | **PASSED** |
| [`tests/phase3-integration.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/phase3-integration.test.ts) | 8 | JWT authentication, RBAC enforcement, query-level tenant isolation, zero data leakage | **PASSED** |
| [`tests/phase3-chaos.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/phase3-chaos.test.ts) | 5 | Gateway network severance, autonomous edge siren (<1.2s), offline backlog queue and flush | **PASSED** |
| [`tests/simulator.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/simulator.test.ts) | 1 | End-to-end execution of all 5 lifecycle demonstration scenarios | **PASSED** |
| [`tests/webhooks.test.ts`](file:///c:/Users/sasik/Desktop/SIH%202026/Subsense/Alert_System/backend/tests/webhooks.test.ts) | 6 | Inbound webhook schema validation, rate-limiting guards, malformed payload rejection | **PASSED** |

---

## 7. Operational Runbook & Execution Guide

### 7.1 Cold Clone Quickstart (One Setup, One Start)
From the `Alert_System` root directory:

```bash
# 1. Install all dependencies across backend and frontend
npm run setup

# 2. Launch Backend API (port 3000) & Frontend Console (port 5173) concurrently
npm start
```

- **Operator Console UI**: `http://localhost:5173`
- **Backend REST API**: `http://localhost:3000/api/v1`
- **Edge WebSocket Feed**: `ws://localhost:3000/ws/alerts`

### 7.2 Pre-Seeded Demonstration Accounts

| Username | Password | Role | Coalfield Concession | Key Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| `officer_jharia` | `subsense123` | Mine Safety Officer | Jharia Block II (`tenant-jharia-01`) | Scoped Jharia view, feedback submission, retraction notices |
| `officer_raniganj` | `subsense123` | Mine Safety Officer | Raniganj Deep Mining (`tenant-raniganj-02`) | Scoped Raniganj view, zero cross-tenant leakage |
| `dgms_inspector` | `dgms2026` | DGMS Regulator | Multi-Tenant (All Mines) | Multi-mine read-only access, one-click DGMS CSV audit export |

### 7.3 Executing Resiliency Proof Scripts
```bash
# Run Telecom Network Outage & Edge Autonomy Proof
npm run test:outage

# Run 48-Hour Historical Slope-Failure Replay (15h lead time verification)
npm run test:replay

# Run High-Throughput Load Benchmark (10,000 events)
npm run test:load

# Run Real-Time 5-Scenario Demonstration Simulator
npm run simulate
```

### 7.4 Running Automated Tests
```bash
# Run complete test suite (66 tests)
npm test

# Run unit tests only
npm run test:unit

# Run integration & RBAC tests only
npm run test:integration

# Run chaos & network severance tests only
npm run test:chaos
```
