# SubSense Platform — Comprehensive Repository Content & Architecture Specification
**Document Version:** SUBSENSE-REPO-SPEC-1.0  
**Specification Baseline:** SUBSENSE-TDD-APP-006, Rev 2.1  
**Layer Focus:** Layer 6 Application Layer (Backend-For-Frontend Gateway & Multi-Tenant Progressive Dashboard)

---

## 1. Executive Overview & System Architecture

SubSense is a mission-critical, safety-first smart mine subsidence monitoring platform. Within the overall 6-layer SubSense system architecture, this repository implements **Layer 6 (Application Layer)**:

```
┌────────────────────────────────────────────────────────────────────────┐
│               LAYER 6: MULTI-TENANT PROGRESSIVE APPLICATION            │
│  React 18 + Vite Web Dashboard ◄────────► Fastify BFF Gateway (Port 3001)│
└────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ (WebSocket & REST JSON Contracts)
┌────────────────────────────────────────────────────────────────────────┐
│     LAYER 4: AI/ML SUBSIDENCE ENGINE  │  LAYER 5: GIS & DIGITAL TWIN   │
│  BiLSTM Quantile Forecast (P10/P50/P90)│  GeoJSON Mine Boundaries, Map  │
└────────────────────────────────────────────────────────────────────────┘
                                    ▲
┌────────────────────────────────────────────────────────────────────────┐
│      LAYER 1-3: PHYSICAL MESH, GATEWAYS & TELEMETRY INGESTION          │
│  Sub-GHz / LoRaWAN Mesh Nodes (Tilt, Vibration, Displacement, Crack)   │
└────────────────────────────────────────────────────────────────────────┘
```

### The 5 Architectural Pillars

1. **One Platform, Many Mines (Multi-Tenant RLS & 3-Tier Hierarchy):**
   - **Jurisdiction:** Regulatory boundary (e.g., `JUR-DGMS-EAST`, Directorate General of Mines Safety Eastern Zone).
   - **Operating Company (Tenant):** Mining corporation (e.g., `OPCO-ECL-01` Eastern Coalfields Limited, `OPCO-BCCL-02` Bharat Coking Coal Limited).
   - **Mine Site / Mining Panel:** Specific extraction panel (e.g., `PANEL7-JHARIA`, `RANIGANJ-SEAM-4`, `MOONIDIH-SEAM-16`).
   - Enforced in PostgreSQL 16 via Row-Level Security (RLS) using session variables (`app.current_tenant_id`, `app.current_user_id`, `app.is_regulator`). Zero cross-tenant data leakage.
   - Dynamic Regulator Scoping via the `regulator_permits` table (inspectors access multiple tenants only with active permits).
   - Strict S3 prefix isolation: `/tenants/{tenant_id}/{site_id}/{resource_category}/`.
   - Zero-Downtime Site Provisioning via JSON metadata with no server restart or redeploy.

2. **Role-Appropriate Progressive UX (4 Distinct Stakeholder Personas):**
   - **Mine Operator (`mine_operator`):** Real-time sensor stream, active warning/critical alerts, audible acknowledgement modal, manual evacuation siren trigger, local Sub-GHz mesh status.
   - **Geotechnical Planner (`geotech_planner`):** Downsampled historical trends, BiLSTM quantile forecast uncertainty cones (10th, 50th, 90th percentile), interactive event markers (blasts, rainfall, false alarms), and sandboxed what-if simulations.
   - **DGMS Safety Regulator (`dgms_regulator`):** Multi-mine safety rollups across permitted operating companies, statutory compliance report exports (PDF/JSON/CSV), chronological audit inspection. Strictly read-only safeguards.
   - **Site Administrator (`site_admin`):** Metadata panel provisioning, edge gateway onboarding, user MFA management, notification route governance.

3. **Alert-First Information Architecture & Closed-Loop Safety:**
   - Active Warning and Critical alerts structurally preempt background analytics.
   - **Server-Enforced Escalation Timer:** 5-minute countdown runs server-side in the BFF. If unacknowledged by operators, the server automatically updates alert state to `escalated` and fires phone dispatch and physical mine sirens.
   - **False Alarm Retraining Loop:** Structured noise categorization ("Surface Blasting", "Heavy Vehicle Impact", "Thermal Expansion", "Sensor Glitch", etc.) emits structured feature vectors to Layer 4 AI retraining queues.
   - **Cryptographic Tamper-Proof Audit Ledger:** SHA-256 hash-chained block sequence (`prev_hash` -> `record_hash`) recording all acknowledgements, alerts, false alarm categorizations, and siren activations.

4. **Zero Silent Staleness:**
   - Real-time heartbeat tracking with the `<StalenessBadge>` component.
   - Heartbeat threshold SLA of 90 seconds. Packets exceeding 90 seconds immediately switch to an amber warning badge.

5. **Formal Shared Data Contracts (Zod Schemas & TypeScript Types):**
   - **Contract 14.1:** Real-time node telemetry & health record (WebSocket broadcast).
   - **Contract 14.2:** Alert lifecycle event (REST & WebSocket).
   - **Contract 14.3:** DGMS statutory report request payload.

---

## 2. Complete Repository Tree Structure

```
e:/project/sih subsense/
├── package.json                               # Root monorepo workspace configuration & runner scripts
├── package-lock.json                          # Pinned dependency lockfile
├── README.md                                  # Platform overview & quick start documentation
│
├── packages/
│   └── shared/                                # Monorepo Shared Package (@subsense/shared)
│       ├── package.json                       # Shared package metadata & dependencies (zod)
│       ├── tsconfig.json                      # TypeScript build configuration
│       └── src/
│           ├── index.ts                       # Main barrel export for @subsense/shared
│           ├── contracts/
│           │   ├── telemetry.ts               # Contract 14.1 Zod schema & TypeScript types
│           │   ├── alerts.ts                  # Contract 14.2 Zod schema, lifecycle state & false alarm types
│           │   └── reports.ts                 # Contract 14.3 Zod schema & DGMS report payloads
│           ├── rbac/
│           │   ├── roles.ts                   # Role definitions (4 personas) & role metadata
│           │   └── capabilities.ts            # Granular RBAC capabilities & assertCapability helper
│           └── tenancy/
│               └── types.ts                   # 3-tier hierarchy types & site provisioning schemas
│
├── services/
│   └── bff-gateway/                           # Layer 6 Backend-For-Frontend Fastify Service
│       ├── package.json                       # Service dependencies (Fastify, PGlite, JWT, otplib)
│       ├── tsconfig.json                      # TypeScript compilation settings
│       ├── vitest.config.ts                   # Vitest unit & integration test configuration
│       ├── src/
│       │   ├── server.ts                      # BFF Gateway HTTP/WS network listener entrypoint
│       │   ├── app.ts                         # Fastify application builder, CORS, hooks, route registration
│       │   ├── alert-engine/
│       │   │   ├── audit-ledger.ts            # SHA-256 hash-chained tamper-proof audit ledger engine
│       │   │   └── escalation-timer.ts        # Server-side 5-minute escalation countdown engine
│       │   ├── auth/
│       │   │   ├── mfa.ts                     # TOTP generator & validator (otplib)
│       │   │   ├── rbac-engine.ts             # Capability checking & regulator permit validation
│       │   │   └── service.ts                 # JWT signing and verification (12h session tokens)
│       │   ├── db/
│       │   │   ├── client.ts                  # PGlite client & withTenantScope RLS query interceptor
│       │   │   ├── schema.sql                 # PostgreSQL 16 DDL with tables, roles & RLS policies
│       │   │   └── seed.ts                    # Idempotent database seeder (jurisdictions, tenants, nodes)
│       │   ├── notifications/
│       │   │   ├── dispatcher.ts              # Multi-channel dispatcher (Browser, FCM, SMS, Siren relay)
│       │   │   └── quiet-hours.ts             # Quiet-hours filter with Critical severity hard override
│       │   ├── routes/
│       │   │   ├── alerts.ts                  # REST API for alerts, audible ack, false alarm, siren trigger
│       │   │   ├── auth.ts                    # Login, MFA verification, role metadata, session info
│       │   │   ├── contracts.ts               # Sample payloads and Zod validation endpoints for 14.x
│       │   │   ├── mesh.ts                    # Mesh topology, node health, battery decay regression, SLA
│       │   │   ├── provisioning.ts            # Zero-downtime metadata site provisioning endpoint
│       │   │   ├── regulator.ts               # Cross-mine rollup, statutory report generation, audit trail
│       │   │   ├── tenants.ts                 # Tenant listing & real-time sensor node telemetry query
│       │   │   └── trends.ts                  # Downsampled trends, BiLSTM quantile forecast & event markers
│       │   ├── storage/
│       │   │   └── tenant-s3.ts               # Tenant-isolated S3 path generator & pre-signed URL mock
│       │   └── ws/
│       │       └── gateway-ws.ts              # WebSocket server streaming Contract 14.1 & alert events
│       └── tests/
│           ├── contracts-and-lifecycle.test.ts # Tests for 14.1/14.2/14.3 schemas, sirens & 5m escalation
│           ├── rls-leakage.test.ts            # Tests verifying zero cross-tenant leakage under RLS
│           └── site-provisioning.test.ts      # Tests verifying zero-downtime metadata site onboarding
│
└── apps/
    └── web-dashboard/                         # Layer 6 React 18 + Vite Web Dashboard
        ├── index.html                         # Single Page Application HTML root entry
        ├── package.json                       # Dashboard dependencies (React 18, ECharts, TailwindCSS)
        ├── postcss.config.js                  # PostCSS plugins (Tailwind, Autoprefixer)
        ├── tailwind.config.js                 # Tailwind CSS design system tokens and color definitions
        ├── tsconfig.json                      # Frontend TypeScript config
        ├── vite.config.ts                     # Vite build configuration, server proxy (/api, /ws) & host
        ├── public/
        │   └── open_pit_mine.jpg              # High-resolution visual asset of open pit mining sector
        └── src/
            ├── main.tsx                       # React DOM root bootstrapping & render entrypoint
            ├── index.css                      # Global styles, Tailwind directives, dark theme tokens
            ├── App.tsx                        # Master layout orchestrator with providers & role synchronization
            ├── contexts/
            │   ├── AuthContext.tsx            # Global user authentication, MFA state & role switching
            │   └── TenantContext.tsx          # Multi-tenant hierarchy state, tenant & site selector
            ├── services/
            │   ├── api.ts                     # REST client injecting tenant, role & JWT auth headers
            │   └── socket.ts                  # WebSocket client & Web Audio API alert chime synthesizer
            ├── components/
            │   ├── AlertPriorityRegion.tsx    # High-priority banner with 5-minute countdown & siren button
            │   ├── AudibleAckModal.tsx        # Modal dialog for mandatory audible alert acknowledgement
            │   ├── FalseAlarmModal.tsx        # Structured modal for Layer 4 AI retraining categorization
            │   ├── GlobalHeader.tsx           # Global header with status indicators, tenant/role switcher
            │   ├── Layer5MapStub.tsx          # 2D/3D mine site geospatial representation & sensor nodes
            │   ├── LiveSensorTable.tsx        # Real-time tabular sensor readouts with StalenessBadges
            │   ├── PrimaryNavigation.tsx      # Tab-based sub-navigation for operational sections
            │   ├── RoleAwareNav.tsx           # Dynamic top navigation adapting to active user role
            │   ├── SensorSummaryKpis.tsx      # Summary metric cards (active nodes, tilt, displacement, vib)
            │   ├── Sidebar.tsx                # Collapsible side navigation with quick role/section links
            │   ├── SiteContextHeader.tsx      # Breadcrumbs (Jurisdiction -> Tenant -> Site) & site status
            │   └── StalenessBadge.tsx         # Heartbeat badge indicating LIVE vs STALE (>90s)
            └── views/
                ├── AdminProvisioningView.tsx  # Zero-downtime site & node metadata provisioning form
                ├── AlertLogView.tsx           # Searchable alert history with filterable lifecycle states
                ├── ContractInspectorView.tsx  # Interactive live schema inspector for Contracts 14.1/14.2/14.3
                ├── GeotechTrendsView.tsx      # ECharts historical trends & BiLSTM quantile forecast cones
                ├── MeshHealthView.tsx         # Sub-GHz mesh node topology, hop graph, battery discharge
                ├── OperationsCockpit.tsx      # Main Mine Operator view with live telemetry, table & map
                ├── OperatorCockpit.tsx        # Alternative high-density operations view
                ├── RegulatorView.tsx          # DGMS multi-tenant rollup, report generator & audit ledger
                └── SubSenseAnalyticsDashboard.tsx # Comprehensive all-in-one interactive command cockpit
```

---

## 3. Detailed File-by-File Breakdown

### Root Configuration & Documentation Files

#### `package.json`
- **Location:** `e:/project/sih subsense/package.json`
- **Purpose:** Root npm workspace manifest orchestrating all multi-package builds, test executions, and dev servers.
- **Key Configuration & Scripts:**
  - `workspaces`: `["packages/*", "services/*", "apps/*"]`
  - `"build"`: Compiles all workspaces (`npm run build --workspaces`).
  - `"test"`: Executes BFF gateway test suite (`vitest run`).
  - `"dev:bff"`: Runs BFF gateway with hot reload via `tsx watch src/server.ts`.
  - `"dev:web"`: Runs Vite web dashboard in dev mode with `--host`.
  - `"dev"`: Runs the backend BFF gateway.
  - `"host"`: Runs the web dashboard with host exposed to LAN/network.

#### `package-lock.json`
- **Location:** `e:/project/sih subsense/package-lock.json`
- **Purpose:** Deterministic npm dependency lockfile pinning exact versions of all dependencies across the workspaces.

#### `README.md`
- **Location:** `e:/project/sih subsense/README.md`
- **Purpose:** Comprehensive engineering README documenting the SubSense Layer 6 specification (SUBSENSE-TDD-APP-006 Rev 2.1), the 5 architectural pillars, test verification results, and startup commands.

---

### `packages/shared/` — Common Domain Models, RBAC & Contracts

#### `packages/shared/package.json`
- **Location:** `e:/project/sih subsense/packages/shared/package.json`
- **Purpose:** Package definition for `@subsense/shared`, defining library exports for both frontend and backend.
- **Key Dependencies:** `zod` (runtime schema validation).

#### `packages/shared/tsconfig.json`
- **Location:** `e:/project/sih subsense/packages/shared/tsconfig.json`
- **Purpose:** TypeScript configuration configuring module resolution (`NodeNext`), target (`ES2022`), declarations, and strict type checking.

#### `packages/shared/src/index.ts`
- **Location:** `e:/project/sih subsense/packages/shared/src/index.ts`
- **Purpose:** Main entry barrel exporting all shared submodules:
  ```ts
  export * from "./contracts/telemetry";
  export * from "./contracts/alerts";
  export * from "./contracts/reports";
  export * from "./rbac/roles";
  export * from "./rbac/capabilities";
  export * from "./tenancy/types";
  ```

#### `packages/shared/src/contracts/telemetry.ts` (Contract 14.1)
- **Location:** `e:/project/sih subsense/packages/shared/src/contracts/telemetry.ts`
- **Purpose:** Canonical schema and type definition for real-time sensor node telemetry broadcast over WebSocket.
- **Key Schemas & Types:**
  - `NodeReadingsSchema`:
    - `tilt_deg` (number): Sensor tilt angle in degrees.
    - `vibration_rms_mm_s` (number): Root mean square vibration in mm/s.
    - `displacement_mm` (number): Borehole extensometer subsidence displacement in mm.
    - `crack_index` (number [0, 1]): Normalized crack propagation index.
  - `NodeHealthSchema`:
    - `battery_pct` (number [0, 100]): Remaining battery level.
    - `rssi_dbm` (number): Received signal strength indicator.
    - `hop_count` (int >= 0): Mesh radio hop count to edge gateway.
    - `predicted_maintenance_days` (number >= 0): Linear regression battery discharge prediction.
  - `NodeTelemetryRecordSchema`:
    - `tenant_id` (string): Operating company ID (e.g., `OPCO-ECL-01`).
    - `site_id` (string): Panel identifier (e.g., `PANEL7-JHARIA`).
    - `node_id` (string): Node identifier (e.g., `SS-PANEL7-N042`).
    - `as_of` (datetime): ISO 8601 UTC timestamp.
    - `is_stale` (boolean): Flag indicating if packet latency exceeds the 90s SLA threshold.
    - `readings` (`NodeReadings`): Sensor measurements.
    - `anomaly_score` (number [0, 1]): Layer 4 AI confidence score.
    - `health` (`NodeHealth`): Hardware health metrics.

#### `packages/shared/src/contracts/alerts.ts` (Contract 14.2)
- **Location:** `e:/project/sih subsense/packages/shared/src/contracts/alerts.ts`
- **Purpose:** Canonical schema and types for alert events, lifecycle state transitions, acknowledgement payloads, and false alarm submissions.
- **Key Schemas & Types:**
  - `AlertSeveritySchema`: Enum of `"info" | "warning" | "critical"`.
  - `AlertStateSchema`: Enum of `"new" | "acknowledged" | "escalated" | "resolved" | "false_alarm"`.
  - `FalseAlarmReasonSchema`: Enum of 7 operational noise sources:
    - `"surface_blasting"`
    - `"heavy_vehicle_impact"`
    - `"thermal_expansion_anomaly"`
    - `"sensor_hardware_glitch"`
    - `"telecom_packet_jitter"`
    - `"unrelated_seismic_activity"`
    - `"other_operational_noise"`
  - `AlertLifecycleEventSchema`:
    - `alert_id`, `tenant_id`, `site_id`, `zone_id`
    - `severity`, `state`, `raised_at`
    - `acknowledged_by`, `acknowledged_at`
    - `time_to_critical_hours` (tuple `[min, max]` in hours)
    - `confidence_score` (number [0, 1])
    - `contributing_sensors` (string array of sensor fields)
    - `explanation_summary` (human-readable AI rationale)
    - Lifecycle metadata: `escalated_at`, `resolved_at`, `resolved_by`, `false_alarm_reason`, `false_alarm_notes`.
  - `AlertAcknowledgePayloadSchema`: Payload schema for operator audible acknowledgements.
  - `FalseAlarmSubmissionSchema`: Payload schema capturing structured noise vectors for Layer 4 retraining.

#### `packages/shared/src/contracts/reports.ts` (Contract 14.3)
- **Location:** `e:/project/sih subsense/packages/shared/src/contracts/reports.ts`
- **Purpose:** Canonical schema and types for DGMS statutory report generation and responses.
- **Key Schemas & Types:**
  - `ReportingPeriodSchema`: `start_date` and `end_date` in ISO 8601 UTC.
  - `DgmsReportRequestPayloadSchema`:
    - `tenant_id`, `site_id`, `report_type`
    - `reporting_period`: Object containing start/end date.
    - `requested_by`: Regulator or auditor ID (e.g., `USR-REG-4412`).
    - `output_format`: Enum of `"application/pdf" | "application/json" | "text/csv"`.
    - `include_kriging_risk_maps` (boolean): Flag to attach 2D spatial kriging heatmaps.
    - `include_audit_trail` (boolean): Flag to attach cryptographic audit records.
  - `DgmsReportResponseSchema`:
    - `report_id`, `tenant_id`, `site_id`, `status` (`pending`, `generating`, `ready`, `failed`), `download_url`, `s3_key`, `hash_signature`.

#### `packages/shared/src/rbac/roles.ts`
- **Location:** `e:/project/sih subsense/packages/shared/src/rbac/roles.ts`
- **Purpose:** Defines the 4 user roles and their associated metadata, scopes, and restrictions:
  - `mine_operator`: Mine Operator (scope: assigned panels). Focuses on live sensor telemetry, acknowledgement of alerts, and manual siren triggers.
  - `geotech_planner`: Geotechnical Planner (scope: subsidence models, forecasting). Has access to trends, LSTM quantiles, digital twin 3D manipulation, and sandboxed what-if simulations.
  - `dgms_regulator`: DGMS Safety Regulator (scope: jurisdiction-wide oversight). Strictly read-only safeguards across permitted operating company tenants.
  - `site_admin`: Site Administrator (scope: tenant configuration, identity). Manages zero-downtime site onboarding, hardware gateway provisioning, and MFA governance.
- **Data Export:** `ROLE_DEFINITIONS: Record<UserRole, RoleMetadata>`.

#### `packages/shared/src/rbac/capabilities.ts`
- **Location:** `e:/project/sih subsense/packages/shared/src/rbac/capabilities.ts`
- **Purpose:** Enumerates 22 granular capabilities (e.g., `sensors:live_view`, `alerts:acknowledge`, `siren:trigger_manual`, `sites:provision_zero_downtime`).
- **Key Functions:**
  - `hasCapability(role: UserRole, capability: Capability): boolean`: Returns whether a role possesses a capability.
  - `assertCapability(role: UserRole, capability: Capability): void`: Throws a `Forbidden` error if unauthorized.

#### `packages/shared/src/tenancy/types.ts`
- **Location:** `e:/project/sih subsense/packages/shared/src/tenancy/types.ts`
- **Purpose:** Defines types for the 3-tier hierarchy and dynamic site provisioning schemas:
  - `Jurisdiction`: Interface for regulatory tiers (`id`, `name`, `code`, `regional_office`).
  - `OperatingCompany`: Interface for corporate mining tenants (`id`, `jurisdiction_id`, `name`, `short_code`).
  - `SiteProvisioningMetadataSchema`: Zod validation schema for zero-downtime panel onboarding (`site_id`, `name`, `boundaries_geojson`, `gateway_credentials`, `node_ids`, `seam_depth_meters`, `extraction_method`).
  - `MineSite`: Interface representing a provisioned mining panel.
  - `RegulatorPermit`: Interface representing cross-tenant access grants for DGMS inspectors.

---

### `services/bff-gateway/` — Layer 6 Backend-For-Frontend Gateway

#### `services/bff-gateway/package.json`
- **Location:** `e:/project/sih subsense/services/bff-gateway/package.json`
- **Purpose:** Service configuration and dependencies for the Fastify server.
- **Key Dependencies:** `@electric-sql/pglite` (embedded PostgreSQL 16 WASM database with full SQL & RLS support), `fastify`, `@fastify/cors`, `@fastify/rate-limit`, `@fastify/websocket`, `jsonwebtoken`, `otplib`, `zod`.
- **Scripts:**
  - `"dev"`: `tsx watch src/server.ts`
  - `"start"`: `tsx src/server.ts`
  - `"test"`: `vitest run`
  - `"build"`: `tsc`

#### `services/bff-gateway/tsconfig.json` & `vitest.config.ts`
- **Locations:** `e:/project/sih subsense/services/bff-gateway/tsconfig.json`, `vitest.config.ts`
- **Purpose:** TypeScript build setup and Vitest test runner configuration.

#### `services/bff-gateway/src/server.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/server.ts`
- **Purpose:** Application network entrypoint. Boots `buildApp()` and listens on `HOST = process.env.HOST || "0.0.0.0"` and `PORT = parseInt(process.env.PORT || "3001", 10)`.

#### `services/bff-gateway/src/app.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/app.ts`
- **Purpose:** Fastify application builder factory function (`buildApp()`):
  - Registers `@fastify/cors` with credentials support.
  - Registers `@fastify/rate-limit` (1000 req/min).
  - Registers `@fastify/websocket`.
  - Installs global authentication hook (`onRequest`): extracts `Authorization: Bearer <token>` or developer convenience headers (`x-user-role`, `x-tenant-id`, `x-user-id`).
  - Initializes database schema and seeds initial data via `seedDatabase()`.
  - Registers WebSocket stream handler via `GatewayWebSocketServer.register(app)`.
  - Registers all REST sub-routes (`authRoutes`, `provisioningRoutes`, `contractsRoutes`, `alertsRoutes`, `trendsRoutes`, `meshRoutes`, `tenantsRoutes`, `regulatorRoutes`).
  - Implements `/health` endpoint returning server status.

#### `services/bff-gateway/src/alert-engine/audit-ledger.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/alert-engine/audit-ledger.ts`
- **Purpose:** Implements the `AuditLedger` class managing the tamper-proof cryptographic audit trail.
- **Key Mechanics:**
  - `record(entry: AuditEntryInput): Promise<string>`: Queries the latest block's `record_hash`, generates a unique ID and timestamp, computes a SHA-256 hash chaining payload:
    `${prevHash}|${id}|${timestamp}|${entry.tenantId}|${entry.userId}|${entry.action}|${JSON.stringify(entry.details)}`
    and inserts the record into `tamper_proof_audit_ledger`.
  - `verifyIntegrity(): Promise<boolean>`: Iterates chronologically over all audit rows and verifies that each entry's `prev_hash` strictly equals the preceding record's `record_hash`.

#### `services/bff-gateway/src/alert-engine/escalation-timer.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/alert-engine/escalation-timer.ts`
- **Purpose:** Implements the `AlertEscalationEngine` enforcing server-side safety escalation countdowns.
- **Key Mechanics:**
  - Standard safety rule: 5-minute (300,000 ms) timeout for `warning` and `critical` alerts.
  - `registerAlert(alert, customTimeoutMs)`: Arms a Node.js `setTimeout`. If unacknowledged within the timeout, triggers `handleEscalationTimeout()`.
  - `handleEscalationTimeout(alertId)`: Updates alert state from `new` to `escalated`, records the event in the cryptographic audit ledger, and immediately invokes `NotificationDispatcher.dispatchAlert()` to trigger emergency SMS and physical mine sirens.
  - `acknowledgeAlert(alertId, userId, comment)`: Disarms the timer, transitions state to `acknowledged`, logs the operator acknowledgement to the audit ledger, and emits an event.
  - `flagFalseAlarm(alertId, userId, reason, notes, featureVector)`: Disarms the timer, updates state to `false_alarm`, records the event, and emits the structured noise vector for Layer 4 model fine-tuning.
  - `resolveAlert(alertId, userId)`: Marks the alert `resolved`.

#### `services/bff-gateway/src/auth/mfa.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/auth/mfa.ts`
- **Purpose:** TOTP Multi-Factor Authentication implementation using `otplib`.
- **Functions:**
  - `generateMfaSecret(email)`: Produces a random secret and an `otpauth://` URI.
  - `verifyMfaToken(token, secret)`: Verifies 6-digit TOTP codes (supports `"123456"` for automated tests and demonstrations).

#### `services/bff-gateway/src/auth/rbac-engine.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/auth/rbac-engine.ts`
- **Purpose:** Access control evaluation class.
- **Functions:**
  - `checkCapability(session, capability)`: Validates role capabilities.
  - `verifyRegulatorPermit(regulatorUserId, targetTenantId)`: Queries `regulator_permits` to verify if an active, unexpired permit exists granting a DGMS regulator access to a tenant.
  - `getPermittedTenantsForRegulator(regulatorUserId)`: Returns the array of tenant IDs currently permitted for a given regulator.

#### `services/bff-gateway/src/auth/service.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/auth/service.ts`
- **Purpose:** JWT token management with 12-hour session lifetime, signed with `JWT_SECRET`.
- **Functions:**
  - `signUserToken(user: UserSession): string`
  - `verifyUserToken(token: string): UserSession | null`

#### `services/bff-gateway/src/db/client.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/db/client.ts`
- **Purpose:** PGlite database connection manager and mandatory RLS query interceptors.
- **Key Mechanics:**
  - `getDb()`: Lazily initializes an in-memory PGlite instance and runs `initSchema()`.
  - `withTenantScope<T>(context, operation)`: Transaction wrapper that executes:
    1. `BEGIN;`
    2. `SET ROLE subsense_app_user;` (switches from superuser to unprivileged role to force RLS evaluation).
    3. `SELECT set_config('app.current_tenant_id', ...), set_config('app.current_user_id', ...), set_config('app.is_regulator', ...);`
    4. Executes callback query operations.
    5. `RESET ROLE; COMMIT;`
  - `withSystemScope<T>(operation)`: Transaction wrapper for bootstrapping, seeding, and system daemons.

#### `services/bff-gateway/src/db/schema.sql`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/db/schema.sql`
- **Purpose:** Full relational schema DDL defining 10 core tables and PostgreSQL 16 Row-Level Security policies:
  1. `jurisdictions`: Regulatory tiers.
  2. `tenants`: Mining operating companies.
  3. `users`: Multi-tenant users with role and TOTP secret.
  4. `regulator_permits`: Explicit cross-tenant access grants.
  5. `sites`: Mining panels with GeoJSON boundaries and S3 report paths.
  6. `nodes`: Sensor nodes deployed across panel zones.
  7. `node_telemetry`: Real-time sensor metrics (Contract 14.1).
  8. `alert_lifecycle_events`: Active alerts, severity, and states (Contract 14.2).
  9. `dgms_reports`: Statutory regulatory reports (Contract 14.3).
  10. `tamper_proof_audit_ledger`: SHA-256 hash-chained immutable audit ledger.
  - **RLS Policies:** Configured on `sites`, `nodes`, `node_telemetry`, `alert_lifecycle_events`, `dgms_reports`, and `tamper_proof_audit_ledger` granting access if:
    `tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')`
    **OR**
    `app.is_regulator = 'true'` AND an active record exists in `regulator_permits` for `app.current_user_id`.

#### `services/bff-gateway/src/db/seed.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/db/seed.ts`
- **Purpose:** Idempotent database seeder that populates initial data:
  - 2 Jurisdictions (`JUR-DGMS-EAST`, `JUR-DGMS-CENTRAL`).
  - 2 Operating Companies (`OPCO-ECL-01` Eastern Coalfields, `OPCO-BCCL-02` Bharat Coking Coal).
  - 5 Default Users spanning all 4 roles.
  - 2 Regulator Permits granting `USR-REG-4412` access to ECL and BCCL.
  - 3 Mine Sites (`PANEL7-JHARIA`, `RANIGANJ-SEAM-4`, `MOONIDIH-SEAM-16`).
  - 6 Sensor Nodes (`SS-PANEL7-N042` to `N045`, `SS-MOON-N101`, `N102`).
  - Initial telemetry records, initial alerts, a sample DGMS report, and the Genesis audit block (`LEDGER-GENESIS`).

#### `services/bff-gateway/src/notifications/dispatcher.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/notifications/dispatcher.ts`
- **Purpose:** Implements `NotificationDispatcher` orchestrating multi-channel dispatch across 4 channels:
  1. `browser_push`: Broadcast to active web dashboard operators.
  2. `mobile_push_fcm`: Push notifications dispatched to on-call safety officers.
  3. `sms_twilio`: High-priority SMS/voice broadcast for Warning and Critical alerts.
  4. `physical_siren_relay`: Hardware relay firing surface and underground sirens for Critical severity or escalated alerts.
  - Records cryptographic audit ledger entries for every dispatch channel.

#### `services/bff-gateway/src/notifications/quiet-hours.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/notifications/quiet-hours.ts`
- **Purpose:** Silences non-critical notifications during configured quiet-hours windows (e.g. 22:00 to 06:00 UTC).
- **Safety Critical Rule:** Critical severity alerts ALWAYS override quiet hours:
  ```ts
  if (severity === "critical") {
    return { silenced: false, reason: "CRITICAL_SEVERITY_OVERRIDE_QUIET_HOURS" };
  }
  ```

#### `services/bff-gateway/src/storage/tenant-s3.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/storage/tenant-s3.ts`
- **Purpose:** Enforces tenant-isolated cloud object storage path generation:
  - Pattern: `tenants/{tenant_id}/{site_id}/{resource_category}/{filename}`.
  - Pre-signed URL generation helper (`generatePresignedUrl`) with tenant scope metadata.

#### `services/bff-gateway/src/ws/gateway-ws.ts`
- **Location:** `e:/project/sih subsense/services/bff-gateway/src/ws/gateway-ws.ts`
- **Purpose:** Implements `GatewayWebSocketServer` at `/ws/live`.
- **Key Features:**
  - Real-time broadcast of live node telemetry (Contract 14.1) every 2500ms to subscribed clients matching tenant and site.
  - Emits simulated stale node (`SS-PANEL7-N045`) with a 140-second timestamp lag to demonstrate Zero Silent Staleness in the frontend.
  - Listens to `AlertEscalationEngine` events and broadcasts alert updates (`alert_raised`, `alert_escalated`, `alert_acknowledged`, `alert_false_alarm`) within 1.5 seconds.
  - Handles client ping/pong and `subscribe_site` event filtering.

#### REST API Routes in `services/bff-gateway/src/routes/`

1. **`routes/alerts.ts`:**
   - `GET /api/v1/alerts`: Queries alerts in current tenant scope with remaining countdown timers.
   - `POST /api/v1/alerts/:alertId/acknowledge`: Disarms countdown upon operator acknowledgement.
   - `POST /api/v1/alerts/:alertId/false-alarm`: Flags alert as false alarm with structured noise reasons.
   - `POST /api/v1/alerts/:alertId/resolve`: Resolves an alert.
   - `POST /api/v1/alerts/simulate`: Emits a test drill alert (Warning or Critical) into the escalation engine.
   - `POST /api/v1/siren/trigger`: Manual evacuation siren trigger (Mine Operator capability).

2. **`routes/auth.ts`:**
   - `GET /api/v1/auth/roles`: Returns all role metadata and capability definitions.
   - `POST /api/v1/auth/login`: Authenticates user by role or credentials, validates optional MFA, issues JWT token.
   - `POST /api/v1/auth/mfa/verify`: Validates TOTP token.
   - `GET /api/v1/auth/me`: Returns active session details and role metadata.

3. **`routes/contracts.ts`:**
   - `POST /api/v1/contracts/validate/14.1-telemetry`: Validates request body against `NodeTelemetryRecordSchema`.
   - `GET /api/v1/contracts/sample/14.1-telemetry`: Returns a valid sample 14.1 telemetry payload.
   - `POST /api/v1/contracts/validate/14.2-alert`: Validates request body against `AlertLifecycleEventSchema`.
   - `GET /api/v1/contracts/sample/14.2-alert`: Returns a valid sample 14.2 alert payload.
   - `POST /api/v1/contracts/validate/14.3-dgms-report`: Validates request body against `DgmsReportRequestPayloadSchema`.
   - `GET /api/v1/contracts/sample/14.3-dgms-report`: Returns a valid sample 14.3 DGMS report payload.

4. **`routes/mesh.ts`:**
   - `GET /api/v1/mesh/health`: Returns mesh node topology (`gateway`, `repeater`, `sensor_node`), hop counts, RSSI, battery levels, linear regression discharge days, and overall packet delivery SLA.

5. **`routes/provisioning.ts`:**
   - `POST /api/v1/tenants/:tenantId/sites`: Zero-downtime metadata provisioning endpoint for new mine panels and sensor nodes. Logs action to the cryptographic audit ledger.
   - `GET /api/v1/tenants/:tenantId/sites`: Lists sites for a tenant within RLS scope.

6. **`routes/regulator.ts`:**
   - `GET /api/v1/regulator/permits`: Returns active permits for the authenticated regulator.
   - `GET /api/v1/regulator/rollup`: Cross-mine safety rollup querying permitted tenants through RLS.
   - `POST /api/v1/regulator/reports/generate`: Generates a DGMS statutory report (PDF/JSON/CSV) with S3 pre-signed URL and SHA-256 digital signature.
   - `GET /api/v1/regulator/audit-ledger`: Returns chronological records from `tamper_proof_audit_ledger`.

7. **`routes/tenants.ts`:**
   - `GET /api/v1/tenants`: Lists all operating companies.
   - `GET /api/v1/tenants/:tenantId/sites/:siteId/sensors`: Returns deployed nodes, current telemetry, and staleness details (amber warning if age > 90s).

8. **`routes/trends.ts`:**
   - `GET /api/v1/geotech/trends`: Returns downsampled historical trends (`1h`, `24h`, `7d`, `30d`), BiLSTM quantile forecasts (P10, P50, P90 uncertainty cones), and geological event markers (blasts, rainfall, false alarms).

#### Backend Test Suite (`services/bff-gateway/tests/`)

1. **`tests/rls-leakage.test.ts`:**
   - Proves zero cross-tenant leakage between ECL (`OPCO-ECL-01`) and BCCL (`OPCO-BCCL-02`) for sites and alert events under RLS policies without manual `WHERE tenant_id = ...` clauses.
   - Verifies dynamic regulator scoping: DGMS inspector queries cross-tenant sites when permits are active, and access is revoked dynamically when permits are marked inactive.

2. **`tests/site-provisioning.test.ts`:**
   - Verifies that onboarding a new panel (`PANEL9-RANIGANJ`) via metadata is immediately accessible to the owning tenant with correct S3 prefix paths, while remaining strictly invisible to other tenants under RLS.

3. **`tests/contracts-and-lifecycle.test.ts`:**
   - Validates Contract 14.1, Contract 14.2, and Contract 14.3 schemas with positive and negative test cases.
   - Validates that server-side 5-minute unacknowledged alert timeouts escalate the alert, fire phone notifications, and trigger physical mine siren relays.
   - Validates closed-loop lifecycle: audible acknowledgements disarm countdowns and log to the cryptographic audit ledger.
   - Validates false alarm noise vector emission for Layer 4 retraining.
   - Validates quiet-hours notification suppression and Critical severity emergency overrides.
   - Validates cryptographic SHA-256 block chain integrity across the audit ledger.

---

### `apps/web-dashboard/` — Progressive React 18 + Vite Web Dashboard

#### Configuration & Build Files

#### `apps/web-dashboard/index.html`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/index.html`
- **Purpose:** SPA entrypoint with Google Fonts preloading (`Inter`, `JetBrains Mono`), dark background styling, and React mount root (`<div id="root"></div>`).

#### `apps/web-dashboard/package.json`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/package.json`
- **Purpose:** Frontend package configuration.
- **Key Dependencies:** `react` 18.3, `react-dom` 18.3, `lucide-react` 0.436, `echarts` 5.5, `echarts-for-react` 3.0, `@subsense/shared`.
- **Scripts:** `"dev": "vite --host"`, `"build": "tsc && vite build"`, `"preview": "vite preview --host"`.

#### `apps/web-dashboard/postcss.config.js` & `tailwind.config.js`
- **Locations:** `e:/project/sih subsense/apps/web-dashboard/postcss.config.js`, `tailwind.config.js`
- **Purpose:** PostCSS configuration and Tailwind CSS styling system. Custom color palettes tailored for high-contrast geotechnical safety dashboards (slate dark modes, warning ambers, emergency reds, nominal emeralds, cyan metrics).

#### `apps/web-dashboard/tsconfig.json`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/tsconfig.json`
- **Purpose:** Client TypeScript compilation config with JSX support.

#### `apps/web-dashboard/vite.config.ts`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/vite.config.ts`
- **Purpose:** Vite dev and production build configuration:
  - Resolves `@subsense/shared` path alias to `../../packages/shared/src/index.ts`.
  - Configures `server`:
    - `host: true`: Exposes server on local host and local area network.
    - `port: 5173`.
    - `proxy`: Proxies `/api` to `http://127.0.0.1:3001` and `/ws` to `ws://127.0.0.1:3001`.

#### `apps/web-dashboard/src/index.css`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/index.css`
- **Purpose:** Tailwind base, components, and utilities directives, custom scrollbars, and pulsing glow animations (`glow-red`, `glow-amber`).

#### Core Application & State Management

#### `apps/web-dashboard/src/main.tsx`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/main.tsx`
- **Purpose:** React entry file initializing `ReactDOM.createRoot` and rendering `<App />`.

#### `apps/web-dashboard/src/App.tsx`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/App.tsx`
- **Purpose:** Root application component that wraps providers (`AuthProvider`, `TenantProvider`) and renders the layout:
  - Synchronizes user roles to default navigation tabs.
  - Manages active alerts state, loads active alerts via REST, and subscribes to real-time alerts via WebSocket.
  - Renders top `<AlertPriorityRegion>` with the 5-minute countdown and audible acknowledgement modal.
  - Renders `<AudibleAckModal>`, `<FalseAlarmModal>`, `<Sidebar>`, `<SiteContextHeader>`, and views.
  - Provides a toggle between `<SubSenseAnalyticsDashboard>` (rich all-in-one cockpit) and modular view tabs.

#### `apps/web-dashboard/src/contexts/AuthContext.tsx`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/contexts/AuthContext.tsx`
- **Purpose:** React context managing user identity and role state:
  - State: `currentUser` (`userId`, `name`, `email`, `role`, `tenantId`, `jurisdictionId`, `mfaVerified`).
  - Methods: `switchRole(newRole)`, `verifyMfa(token)`, `can(capability)`.
  - Seamlessly switches between the 4 stakeholder profiles.

#### `apps/web-dashboard/src/contexts/TenantContext.tsx`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/contexts/TenantContext.tsx`
- **Purpose:** React context managing multi-tenant hierarchy selection:
  - State: `currentTenantId`, `currentSiteId`, `availableTenants`, `availableSites`.
  - Automatically loads and refreshes mine panels from `/api/v1/tenants/:tenantId/sites`.

#### `apps/web-dashboard/src/services/api.ts`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/services/api.ts`
- **Purpose:** REST API fetch wrapper:
  - Automatically attaches `Authorization: Bearer <jwt>`, `x-tenant-id`, `x-user-role`, and `x-user-id` headers.
  - Handles response parsing and errors.

#### `apps/web-dashboard/src/services/socket.ts`
- **Location:** `e:/project/sih subsense/apps/web-dashboard/src/services/socket.ts`
- **Purpose:** Client WebSocket connection service and Web Audio API synthesizer:
  - `playAudibleAlertChime(severity)`: Synthesizes alert chimes using the Web Audio API without requiring external audio files (sawtooth waveform at 880Hz/440Hz for Critical; triangle waveform at 587Hz for Warning).
  - `WebSocketService`: Manages WebSocket lifecycle, auto-reconnection (every 3s), telemetry subscriptions, and alert listeners.

#### Frontend UI Components (`apps/web-dashboard/src/components/`)

1. **`AlertPriorityRegion.tsx`:**
   - Alert banner placed at the very top of the interface.
   - When an unacknowledged Warning or Critical alert is active, it renders a high-visibility gradient banner, 5-minute countdown clock, "Audible Acknowledge" button, "False Alarm" button, "Resolve" button, and "Trigger Siren" emergency evacuation button.
   - When no alerts are active, displays a nominal status banner with drill simulation triggers.

2. **`AudibleAckModal.tsx`:**
   - Mandatory modal dialog requiring the operator to confirm having heard the audible console alarm, input a commentary log, and submit to disarm the countdown and sign the cryptographic ledger.

3. **`FalseAlarmModal.tsx`:**
   - Dialog allowing operators to categorize false alarms from 6 structured noise sources, add field verification notes, and submit the feature vector to the Layer 4 AI retraining queue.

4. **`GlobalHeader.tsx`:**
   - Top application bar displaying the SubSense brand, tenant selector, active role switcher, and live user MFA verification status badge.

5. **`Layer5MapStub.tsx`:**
   - 2D geospatial map representation of the mine panel boundary and deployed sensor nodes with color-coded status rings (green = online, amber = stale, red = breach).

6. **`LiveSensorTable.tsx`:**
   - High-density tabular display of all sensor nodes across the panel. Displays Node ID, Zone, Tilt angle, Vibration RMS, Displacement, Crack Index, Anomaly Score, Battery, RSSI, Hop Count, and an embedded `<StalenessBadge>`.

7. **`PrimaryNavigation.tsx`:**
   - Tab strip switching between Sensor Overview, Geotechnical Trends, Mesh Health, Alert History, and Statutory Reports.

8. **`RoleAwareNav.tsx`:**
   - Adaptive top navigation bar that shows only the tabs relevant to the current user role (`mine_operator`, `geotech_planner`, `dgms_regulator`, `site_admin`).

9. **`SensorSummaryKpis.tsx`:**
   - KPI cards displaying Total Nodes, Max Tilt Angle, Max Subsidence Displacement, Mean Vibration RMS, and Active Critical Alerts.

10. **`Sidebar.tsx`:**
    - Collapsible left navigation sidebar with links to Operations Cockpit, Trends & Analytics, Mesh Health, Alerts, Reports, and Admin Provisioning.

11. **`SiteContextHeader.tsx`:**
    - Breadcrumb navigation showing the 3-tier hierarchy (`Jurisdiction` -> `Operating Company` -> `Panel`), total nodes count, mesh health label, and last updated time.

12. **`StalenessBadge.tsx`:**
    - Real-time heartbeat indicator implementing Zero Silent Staleness. Computes elapsed time since the packet's `as_of` timestamp. If latency exceeds 90s (or `is_stale === true`), transitions to an animated amber warning badge (`STALE (Xs ago)`). Includes a hover tooltip showing packet timestamp, age, and SLA threshold.

#### Frontend Views (`apps/web-dashboard/src/views/`)

1. **`OperationsCockpit.tsx`:**
   - Primary operations cockpit for Mine Operators, combining `<SensorSummaryKpis>`, `<Layer5MapStub>`, and `<LiveSensorTable>` connected to the live WebSocket feed.

2. **`GeotechTrendsView.tsx`:**
   - Geotechnical view rendering interactive ECharts historical trends across customizable ranges (`1h`, `24h`, `7d`, `30d`), BiLSTM quantile forecast uncertainty cones (P10, P50, P90), and geological event markers (blasts, rainfall, false alarms).

3. **`MeshHealthView.tsx`:**
   - Sub-GHz wireless sensor mesh network view showing node topology, gateway EUIs, link RSSI quality percentages, hop counts, and battery discharge projections using linear regression.

4. **`AlertLogView.tsx`:**
   - Comprehensive audit log of all alert lifecycle events across the mine panel with state filters (`new`, `acknowledged`, `escalated`, `resolved`, `false_alarm`).

5. **`RegulatorView.tsx`:**
   - Specialized view for DGMS Safety Regulators showing cross-mine multi-site rollups, permit validations, statutory report generation form (Contract 14.3), and the cryptographic audit ledger.

6. **`AdminProvisioningView.tsx`:**
   - Administrative view for Site Administrators supporting zero-downtime metadata onboarding of new mine sites and sensor nodes without server restarts.

7. **`ContractInspectorView.tsx`:**
   - Interactive developer and auditor tool displaying live Zod schemas, test payloads, and real-time schema validation for Contracts 14.1, 14.2, and 14.3.

8. **`OperatorCockpit.tsx`:**
   - Alternative high-density operations view tailored for rapid multi-panel monitoring.

9. **`SubSenseAnalyticsDashboard.tsx`:**
   - 2,300+ line interactive command dashboard unifying role switching, digital twin map canvas, real-time ECharts graphs, BiLSTM uncertainty cones, audio chimes, modal workflows, mesh visualizers, and report exports.

---

## 4. Shared Data Contracts Reference (14.x)

### Contract 14.1: Real-Time Node Telemetry & Health Record
- **Channel:** WebSocket Broadcast (`/ws/live`)
- **JSON Schema / Structure:**
```json
{
  "tenant_id": "OPCO-ECL-01",
  "site_id": "PANEL7-JHARIA",
  "node_id": "SS-PANEL7-N042",
  "as_of": "2026-09-09T04:15:00.000Z",
  "is_stale": false,
  "readings": {
    "tilt_deg": 0.183,
    "vibration_rms_mm_s": 1.42,
    "displacement_mm": 3.70,
    "crack_index": 0.02
  },
  "anomaly_score": 0.86,
  "health": {
    "battery_pct": 78,
    "rssi_dbm": -71,
    "hop_count": 3,
    "predicted_maintenance_days": 21
  }
}
```

### Contract 14.2: Alert Lifecycle Event
- **Channel:** REST (`/api/v1/alerts`) & WebSocket (`alert_raised`, `alert_escalated`, etc.)
- **JSON Schema / Structure:**
```json
{
  "alert_id": "ALERT-PANEL7-20260909-0412",
  "tenant_id": "OPCO-ECL-01",
  "site_id": "PANEL7-JHARIA",
  "zone_id": "PANEL7-ZONE-C",
  "severity": "warning",
  "state": "acknowledged",
  "raised_at": "2026-09-09T04:12:00.000Z",
  "acknowledged_by": "USR-OP-8492",
  "acknowledged_at": "2026-09-09T04:14:10.000Z",
  "time_to_critical_hours": [6.0, 14.0],
  "confidence_score": 0.79,
  "contributing_sensors": ["tilt_deg", "displacement_mm"],
  "explanation_summary": "Sustained tilt increase at N042, corroborated by 3 neighboring nodes over 40 minutes.",
  "false_alarm_reason": null,
  "false_alarm_notes": null
}
```

### Contract 14.3: DGMS Statutory Report Request Payload
- **Channel:** REST (`POST /api/v1/regulator/reports/generate`)
- **JSON Schema / Structure:**
```json
{
  "tenant_id": "OPCO-ECL-01",
  "site_id": "PANEL7-JHARIA",
  "report_type": "dgms_statutory_subsidence_summary_v2",
  "reporting_period": {
    "start_date": "2026-08-01T00:00:00.000Z",
    "end_date": "2026-08-31T23:59:59.000Z"
  },
  "requested_by": "USR-REG-4412",
  "output_format": "application/pdf",
  "include_kriging_risk_maps": true,
  "include_audit_trail": true
}
```

---

## 5. Row-Level Security (RLS) & Multi-Tenant Data Isolation

### Mechanism Overview
PostgreSQL 16 enforces data isolation through Row-Level Security:
1. Every query executed via `withTenantScope()` sets session context:
   ```sql
   SET ROLE subsense_app_user;
   SELECT set_config('app.current_tenant_id', 'OPCO-ECL-01', true);
   SELECT set_config('app.current_user_id', 'USR-OP-8492', true);
   SELECT set_config('app.is_regulator', 'false', true);
   ```
2. The database automatically appends policy filters to all queries on secured tables (`sites`, `nodes`, `node_telemetry`, `alert_lifecycle_events`, `dgms_reports`, `tamper_proof_audit_ledger`):
   ```sql
   CREATE POLICY sites_tenant_isolation_policy ON sites
   FOR ALL
   USING (
     tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')
     OR
     (
       current_setting('app.is_regulator', true) = 'true'
       AND EXISTS (
         SELECT 1 FROM regulator_permits rp
         WHERE rp.regulator_user_id = NULLIF(current_setting('app.current_user_id', true), '')
           AND rp.tenant_id = sites.tenant_id
           AND rp.active = true
           AND NOW() BETWEEN rp.valid_from AND rp.valid_to
       )
     )
   );
   ```
3. Developers never need to write manual `WHERE tenant_id = ...` clauses.

---

## 6. Verification & Execution Commands

### Running the Test Suite
```bash
npm test
```
Executes all 13 integration tests across `rls-leakage.test.ts`, `site-provisioning.test.ts`, and `contracts-and-lifecycle.test.ts`.

### Starting the Services
- **Start Backend BFF Gateway:**
  ```bash
  npm run dev:bff
  ```
  Runs Fastify server at `http://0.0.0.0:3001` and WebSocket at `ws://0.0.0.0:3001/ws/live`.
- **Start React Web Dashboard:**
  ```bash
  npm run dev:web
  # or
  npm run host
  ```
  Runs Vite dev server at `http://localhost:5173/` and on the local network (`http://<local-ip>:5173/`).
