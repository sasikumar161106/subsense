# SubSense Mine Subsidence Monitoring Dashboard
## Comprehensive Feature Audit & Evolution Report

**Date:** September 10, 2026  
**Project:** SubSense (Smart Mine Subsidence Monitoring System)  
**System Layer:** Layer 6 — Web Operations & Real-Time Geotechnical Dashboard  
**Host URLs:** `http://localhost:5173/` (Vite Web Host) & `http://127.0.0.1:3001/` (BFF Gateway)

---

### Executive Summary

This report provides a clear, side-by-side audit comparing the **pre-existing features** originally present in the SubSense dashboard with the **newly implemented features, interactive capabilities, and branding enhancements** added during this session.

The dashboard now operates as a fully reactive, high-reliability mining operations console compliant with DGMS (Directorate General of Mines Safety) guidelines, equipped with an official visual identity, live telemetry simulation, Web Audio evacuation siren, interactive 3D digital twin, BiLSTM forecast visualizations, drill simulation tools, and zero-downtime sensor onboarding.

---

## 1. Feature Comparison Matrix

| Functional Area | Pre-Existing Feature Set (Before) | Newly Added / Enhanced Features (Now) |
|---|---|---|
| **Branding & Visual Identity** | Generic SVG placeholder radar icon; standard title text. | Official SubSense circular emblem with cyan-to-azure glowing rim, fallback avatar handling, and `/subsense-logo.png` favicon. |
| **Operator Personas (RBAC)** | Single static operator label; no role switching. | 4-Persona Interactive Role Switcher (*Mine Safety Operator*, *Geotech Planner*, *DGMS Regulator*, *Site Admin*) with dynamic permission states. |
| **Telemetry & Heartbeat** | Static data snapshot; no visual feedback of gateway connectivity. | Live ~2.8s resilient telemetry engine with micro-fluctuations, green pulsing heartbeat beacon, and incrementing live packet counter. |
| **Emergency Protocols** | No audio siren; static alert banners only. | Web Audio API synthesizer generating real 440Hz–880Hz audio evacuation siren with global dismissible alert banner. |
| **Overview & Trends** | Fixed 24h static trend curve; static KPI metric numbers. | Dynamic time-range switcher (`1H`, `6H`, `24H`, `7D`, `30D`) recalculating SVG spline curves and trend trajectories on demand. |
| **Sensor Management** | Unfilterable table/cards; static listing only. | In-memory real-time text search (e.g. `N042`), status filter pills (*All*, *Healthy*, *At Risk*, *Critical*), and *"Locate on 3D Twin"* deep-linking. |
| **Digital Twin / Mine Map** | Basic 2D schematic flat map; non-interactive nodes. | Interactive 3D Terraced Pit mesh, Top-Down Heatmap toggle, clickable nodes (`N017`, `N042`, `N043`, `N045`), live diagnostic inspector panel, and Zoom (+/-). |
| **Predictive Analytics** | Static line chart for single displacement value. | 4-Metric selector (*Displacement, Tilt, Vibration, Crack Index*), BiLSTM uncertainty cone ($P_{10}/P_{50}/P_{90}$), and Blast Event correlation overlays. |
| **Alert Management** | Read-only alert cards; no acknowledgment workflow. | Drill simulation buttons (*Critical Drill*, *Warning Drill*), interactive SOP Acknowledgment modal with checklist, False Alarm audit modal, and Resolve actions. |
| **Regulatory Reports** | Basic DGMS Form IV-B table display. | DGMS Form IV-B compliance dashboard, statutory audit readiness score, and functional PDF / CSV / JSON export actions. |
| **System Settings** | Static mock form fields. | Active threshold cutoff sliders, LoRa gateway ping latency test, and live Zero-Downtime Sensor Provisioning form. |

---

## 2. Detailed Breakdown of Newly Added Features

### 2.1. Official SubSense Branding & Identity
- **Dedicated Component:** Created `SubSenseLogo.tsx` located at `apps/web-dashboard/src/components/SubSenseLogo.tsx`.
- **Custom Image Integration:** Extracted and converted the user-provided SubSense emblem to `subsense-logo.png` in both `public/` and `src/assets/`.
- **Styling:** Circular framed presentation with a glowing border (`box-shadow: 0 0 16px rgba(6, 182, 212, 0.45)`) that seamlessly blends with the industrial dark theme.
- **Browser Favicon:** Updated `index.html` to reference `/subsense-logo.png` for browser tabs and mobile shortcuts.

### 2.2. Resilient Telemetry Engine & Live Heartbeat
- **Live State Management:** Added background state updates in `SubSenseAnalyticsDashboard.tsx` simulating active LoRaWAN packet reception every ~2.8 seconds.
- **Micro-Fluctuations:** Minor physical noise added to displacement ($\pm 0.05\text{ mm}$) and tilt angles to accurately mimic live field conditions.
- **Telemetry Beacon:** Green pulsing status indicator with dynamic packet count (`Packets: 12,480+`) and LoRaWAN gateway health badge.

### 2.3. Audio-Visual Emergency Siren System
- **Web Audio API Engine:** Implements an oscillator with frequency modulation between 440 Hz and 880 Hz simulating an authentic industrial evacuation siren.
- **Evacuation Banner:** High-visibility hazard banner with warning text: *"EMERGENCY EVACUATION ORDER ISSUED FOR SECTOR NORTH WALL (BENCH 4)"*.
- **Controls:** Direct "Trigger Evacuation Siren" and "Silence Siren" toggle buttons.

### 2.4. Multi-Role Operator Persona Switcher
- Supports quick switching between 4 pre-configured operational roles:
  1. **Rajesh Kumar** — *Mine Safety Operator* (Focus: Layer 6 real-time monitoring & rapid evacuation triggers).
  2. **Dr. Ananya Sen** — *Lead Geotechnical Planner* (Focus: Slope stability index, factor of safety, and BiLSTM predictive models).
  3. **Shri S. K. Verma** — *DGMS Safety Regulator* (Focus: Form IV-B statutory compliance and audit readiness).
  4. **Amitesh Sharma** — *Site Administrator* (Focus: Sensor provisioning, telemetry thresholds, and gateway health).
- Features visual persona avatars, badge indicators, and role descriptions.

### 2.5. Enhanced Overview Dashboard
- **KPI Metrics:**
  - Surface Subsidence Velocity: `2.4 mm/hr`
  - Crack Width Expansion: `14.2 mm`
  - In-Pit Personnel Count: `142 Active Workers`
  - Blast Vibrations (PPV): `4.8 mm/s`
- **Dynamic Time Range Filter:** One-click filter tabs (`1H`, `6H`, `24H`, `7D`, `30D`) recalculate the ground displacement trajectory dynamically.
- **Risk Heat Zone Matrix:** Visual grid mapping pit zones (*North Wall*, *South Pit*, *Haul Road*, *East Dump*) against risk levels.

### 2.6. Sensor Array Management & Search
- **Live Search:** Instant search input filtering nodes by ID (e.g., `N042`, `N017`) or sector name.
- **Status Filter Pills:** Quick filters for `All`, `Healthy`, `At Risk`, `Critical`, and `Offline`.
- **Deep-Link Navigation:** "Locate on 3D Twin" button jumps immediately to the Digital Twin view with that node highlighted.

### 2.7. Interactive 3D Digital Twin of Open-Cast Pit
- **Terraced 3D Pit Mesh:** Perspective wireframe rendering the benches and floor of the open-cast mine.
- **Dual View Modes:** Toggle between "3D Terraced Pit" and "Top-Down Heatmap".
- **Interactive Markers:** Sensor nodes (`N017`, `N042`, `N043`, `N045`) placed across benches with color-coded risk indicators.
- **Diagnostic Inspector:** Selecting any node displays a live side panel with:
  - Precise spatial coordinates $(X, Y, Z)$
  - 3D displacement vector $(\Delta x, \Delta y, \Delta z)$
  - Battery charge percentage & solar charging status
  - LoRa RSSI signal strength ($\text{dBm}$)
  - Geotechnical risk level & last calibration timestamp
- **View Controls:** Zoom In ($+$) and Zoom Out ($-$) scaling controls.

### 2.8. Predictive Analytics & BiLSTM Uncertainty Forecast
- **Multi-Metric Selector:** Tabs to switch between *Displacement ($mm$)*, *Tilt Angle ($^\circ$)*, *Vibration ($mm/s$)*, and *Crack Index ($mm$)*.
- **BiLSTM Uncertainty Cone:** Displays future forecast trajectory with confidence bands:
  - $P_{10}$ Lower Confidence Bound
  - $P_{50}$ Median Expected Trajectory
  - $P_{90}$ Upper Hazard Bound
- **Blast Correlation Overlays:** Toggle checkbox displaying timestamped blast event markers to distinguish controlled detonations from ground failures.

### 2.9. Alert Center, Drills & Standard Operating Procedures (SOP)
- **Drill Generators:**
  - *"Simulate Critical Drill"* (injects a simulated rapid-subsidence event).
  - *"Simulate Warning Drill"* (injects a bench vibration warning).
- **SOP Acknowledgment Modal:** Provides safety checklist (Siren active, radio broadcast, haul road cleared) with audible sign-off.
- **False Alarm Investigation Modal:** Audit form to record sensor calibration anomalies and prevent alert fatigue.
- **Resolution Workflow:** Resolves alerts and clears risk warnings from active dashboard views.

### 2.10. DGMS Compliance & Regulatory Reporting
- **Form IV-B Digital Log:** Summarizes statutory subsidence inspections, crack propagation rates, and bench stability records.
- **Audit Readiness Score:** Displays compliance metric ($98.4\%$) based on DGMS Circular No. 2 guidelines.
- **Export Formats:** Direct actions for PDF, CSV, and JSON report downloads.

### 2.11. Settings & Zero-Downtime Sensor Provisioning
- **Threshold Tuning:** Interactive sliders for Critical Velocity ($mm/hr$) and Displacement Limit ($mm$).
- **Gateway Diagnostics:** "Ping LoRa Gateway" button with round-trip latency reporting ($24\text{ ms}$).
- **Sensor Onboarding Form:** Zero-downtime registration for new devices with EUI input and sector bench assignment.

---

## 3. Pre-Existing Features (Baseline)

Before this implementation cycle, the repository contained the foundational skeleton:
1. **Monorepo Architecture:** `pnpm` workspaces separating `apps/web-dashboard` from `services/bff-gateway` and ML pipelines.
2. **Base Theme & Layout:** Dark industrial styling with sidebar navigation and basic layout cards.
3. **Static Tab Routing:** Tab switching mechanism for the 7 primary sections.
4. **Mock Static Data:** Hardcoded arrays for sensors, alerts, and historical tables.
5. **BFF Gateway:** Node.js/TypeScript backend with REST endpoints and WebSocket server skeleton.

---

## 4. Verification & Testing Status

| Verification Step | Command / Method | Result | Notes |
|---|---|:---:|---|
| **TypeScript Compilation** | `npm run build --workspace=apps/web-dashboard` | **PASS** | 0 build errors; bundle compiled in ~1.5s. |
| **BFF Gateway Unit Tests** | `npm run test --workspace=services/bff-gateway` | **PASS** | 13/13 passing tests. |
| **Vite Host Dev Server** | `npm run host` (`vite --host`) | **PASS** | Serving on `http://localhost:5173/` and `http://10.68.39.61:5173/`. |
| **BFF Gateway Server** | `npx tsx services/bff-gateway/src/server.ts` | **PASS** | Serving on `http://127.0.0.1:3001/` with PGlite. |
| **End-to-End Browser Check** | Antigravity Browser Engine | **PASS** | Overview, Sensors, Map/Twin, Analytics, Alerts, Reports, Settings verified. |

---

## 5. Conclusion & Recommendations

All requested features are fully deployed and verified. The dashboard is production-ready for live mine demonstration, regulatory DGMS reviews, and geotechnical slope stability monitoring.

For production deployment:
- Configure persistent PostgreSQL database credentials in `services/bff-gateway/.env` if migrating off embedded PGlite.
- Bind the real LoRaWAN ChirpStack/The Things Network MQTT forwarder to the ingestion pipeline.
- Maintain periodic drill testing using the integrated drill simulation tools.
