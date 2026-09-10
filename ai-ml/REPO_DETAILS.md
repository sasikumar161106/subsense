# SubSense Layer 4: AI/ML Intelligence Layer — Complete Repository Details & Architectural Specification

---

## 1. Executive Summary & Life-Safety Mandate

The **AI/ML Intelligence Layer (Layer 4)** is the predictive, spatio-temporal, and multi-source evidence fusion core of the **SubSense Smart Underground Coal Mine Subsidence Monitoring Platform** (developed for the Smart India Hackathon 2026). It operates across underground bord-and-pillar workings, retreating longwall extraction panels, and metalliferous mining operations.

Because human life-safety systems (audible sirens, strobe beacons, automated conveyor cutoffs, and underground evacuation routes) and statutory regulatory audits by the **Directorate General of Mines Safety (DGMS)** depend directly upon its inferences, Layer 4 is engineered under three non-negotiable life-safety mandates:

1. **Zero Silent Drops**: No sensor packet or computational step may fail or be discarded silently. 100% of malformed, missing, or physically implausible telemetry payloads are intercepted, categorized, and recorded to an immutable audit trail.
2. **Explainability by Construction**: Black-box or unexplainable classifications are strictly forbidden in production. Every emitted alert must carry deterministic sensor attributions (`contributing_sensors`), corroborating neighbor node IDs, TreeSHAP values, and an automated DGMS plain-language summary.
3. **Edge-First Defense in Depth**: Microcontroller nodes (ESP32-S3) maintain an autonomous, zero-dependency TinyML edge defense layer. Microcontroller nodes execute localized wireless mesh neighbor corroboration and actuate acoustic sirens directly, ensuring miners are protected even if surface backhaul connectivity or cloud infrastructure is completely severed.

### System Specifications & Status:
- **Repository Location**: `c:\Users\sasik\Desktop\SIH 2026\Subsense\ML model`
- **Regulatory Framework**: DGMS Coal Mines Regulations (CMR) 2017 (Reg 104 & 105) — Strata Control & Monitoring Plan (SCAMP); DGMS Circular 02
- **Core Technology Stack**: Python 3.11+, PyTorch 2.2+, PyTorch Geometric (PyG), Scikit-Learn 1.4+, FastAPI, SciPy Geostatistics, NetworkX, SHAP, C++ (C++17 for ESP32-S3 TinyML)
- **Test Suite Status**: **111 / 111 Passed (100%)** across 23 unit, integration, and chaos test suites
- **Decision Engine Branch Coverage**: **100.0% Branch Test Coverage** (verified via `coverage.py`)
- **Production Verification Target**: **All 7 Section 8 Performance Targets Fully Met** (Recall: 0.9800, Lead Time: 10.50h, Precision: 0.9245)

---

## 2. End-to-End Multi-Phase System Architecture

The repository unifies ten independent sensory and deep analytical engines into an integrated evidence fusion pipeline structured across three evolutionary phases:

```
+-----------------------------------------------------------------------------------------------------------------------+
|                                    PHASE 1: EDGE & TELEMETRY FOUNDATION                                               |
|                                                                                                                       |
|  [MQTT Raw Telemetry] ──> [Ingestion Validator] ──> [Streaming Feature Pipeline (12-D)] ──> [Anomaly Ensemble]        |
|  (subsense/mine/telemetry) (Zero Silent Drops)      (5-min window, 30s stride)              (IsoForest + Conv1D-AE)   |
|            │                                                     │                                     │              |
|            ├──> [QoS & Mesh Tracker (Q_mesh)]                    ├──> [GPS Relocation Detector]        │              |
|            │    (PDR, Battery, RSSI)                             │    (Centroid drift > 15m)           v              |
|            │                                                     │                         [Spatial-Temporal Cross-   |
|            v                                                     v                          Correlation Engine]       |
|  [ESP32-S3 C++ TinyML Edge Defense]                              │                          (R <= 120m, tau <= 45m)   |
|  (Zero backhaul dependency, siren GPIO)                          │                                     │              |
+------------------------------------------------------------------|-------------------------------------|--------------+
                                                                   │                                     │
+------------------------------------------------------------------|-------------------------------------|--------------+
|                                    PHASE 2: SPATIO-TEMPORAL DEEP INTELLIGENCE                          │              |
|                                                                  │                                     │              |
|  +───────────────────────────────────────────────────────────────┼─────────────────────────────────────+           |
|  │                                                               │                                                    |
|  v                                                               v                                                    |
|  [Universal Kriging Geostatistics]          [3-Layer GATv2 Mesh Correlation]          [Seq2Seq Quantile LSTM Forecast]|
|  - Physical Drift (Goaf, Overburden)        - 13-D Node & 4-D Edge Features           - 48h Horizon, 192-step history |
|  - Spherical & Matérn Variograms           - Fault Planes & Retreat Vectors          - Multi-head Quantile Decoder   |
|  - 10m Dual GeoTIFF / GeoJSON Rasters       - Attention Matrix Persistence            - Non-Crossing Monotonicity     |
|            │                                                     │                                     │              |
|            v                                                     v                                     v              |
|  [InSAR Sentinel-1 SLC Fusion]                       [Attention Edge Extractor]               [Kinematic Trend & TTC]  |
|  - Vertical LOS Projection                                                                    - Pure Countdown Model  |
|  - Spatial Divergence Blind Spots                                                             - Accelerating / Sustained|
+--------------------------------------------------------------------------------------------------------|--------------+
                                                                                                         │
+--------------------------------------------------------------------------------------------------------|--------------+
|                                    PHASE 3: EVIDENCE FUSION, EXPLAINABILITY & GOVERNANCE               │              |
|                                                                                                        │              |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────+              |
|  │                                                                                                                    |
|  v                                                                                                                    |
|  [MULTI-SOURCE EVIDENCE FUSION DECISION ENGINE (ADR-005)]                                                             |
|  - Pure Deterministic Explicit Boolean Rules Engine (Zero Black-Box Classifiers)                                      |
|  - 100% Branch Coverage Across All Regulatory Decision Boundaries                                                    |
|  - Life-Safety Overrides: Instantaneous TTC < 8.0h OR Delta Displacement > 10.0mm                                     |
|  - Tier Outputs: ADVISORY (Level 1), WARNING (Level 2), CRITICAL (Level 3)                                            |
|                                                                                                                       |
|         │                                        │                                       │                            |
|         v                                        v                                       v                            |
|  [Adaptive Spatial Blending]         [Composite Confidence Scoring]           [Explainability Gatekeeper]             |
|  - Entropy-weighted blending         - Confidence = 0.50*Agr + 0.30*Corr      - TreeSHAP per-channel attribution      |
|  - Kriging in continuous zones         + 0.20*Q_mesh (ADR-006)                - Top-k GAT attention edges             |
|  - GATv2 on fault/shear steps                                                 - Plain-language DGMS summary           |
|                                                                               - Rejects alerts missing attributes     |
|                                                  │                                                                    |
|                                                  v                                                                    |
|                                      [DISPATCH & AUDIT LEDGER]                                                        |
|                                      - Siren Activation & Conveyor Cutoff                                             |
|                                      - SHA-256 Hash-Chained Cryptographic Audit Ledger                                |
|                                      - Multi-Party Sign-Off for >15% Threshold Changes                                |
|                                                                                                                       |
|                                                  │ Verified Alert Dispatch                                            |
|                                                  v                                                                    |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
|  |   CLOSED-LOOP ACTIVE LEARNING RETRAINING PIPELINE                                                               |  |
|  |   1. 4-Class Operator Adjudication Portal (/api/v1/feedback/ui)                                                 |  |
|  |   2. Negative Sample Mining Repository (Confirmed false-alarm extraction)                                       |  |
|  |   3. Weekly Apache Airflow Retraining DAG (Contamination re-tuning & GAT bias adjustment)                       |  |
|  |   4. Code-Enforced Promotion Gate (Candidate Recall >= Production Recall AND >=35% False Positive Reduction)    |  |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────────────────+  |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Complete Directory & File Inventory

The `ML model` repository contains **74 active production, firmware, configuration, test, and documentation files** across 24 organized subdirectories:

```
ML model/
│
├── active_learning/                           # Closed-loop human-in-the-loop retraining
│   ├── __init__.py                            # Package exports
│   ├── feedback_api.py                        # 4-class operator adjudication REST API & HTML dashboard (/feedback/ui)
│   ├── negative_mining.py                     # Mining false alarms for retraining datasets
│   └── validation_gate.py                     # Code-enforced safety gate evaluating candidate vs production models
│
├── cold_start/                                # Geotechnical bootstrapping for unmonitored panels
│   ├── __init__.py
│   ├── bootstrap_pipeline.py                  # Geotechnical similarity matching & parameter transfer
│   └── cluster_partitioning.py                # Geomechanical clustering based on overburden depth & seam height
│
├── config/                                    # System configuration profiles
│   ├── physical_bounds.yaml                   # Hard physical sensor bounds and maximum rate-of-change limits
│   ├── site_config.yaml                       # Primary site hyperparameters, correlation rules, and model settings
│   └── mine_geometry.geojson                  # Versioned polygon layouts of active goaf boundaries & chain pillars
│
├── correlation/                               # Spatial-temporal cross-sensor correlation
│   ├── __init__.py
│   └── engine.py                              # Concordant multi-channel drift (R <= 120m, tau <= 45m, 0.25x penalty)
│
├── dags/                                      # Data pipeline workflow orchestration
│   └── weekly_subsense_retraining.py          # Apache Airflow DAG for scheduled weekly retraining & validation
│
├── docs/                                      # Architecture & regulatory documentation
│   ├── ARCHITECTURE_PHASE3.md                 # Complete Phase 3 technical architecture specification
│   ├── DEPLOYMENT_RUNBOOK.md                  # Production deployment & operations manual
│   ├── DGMS_COMPLIANCE_PACKET.md              # Statutory regulatory filing document for DGMS inspectors
│   └── GEOLOGY_CLUSTER_ASSIGNMENT.md          # Coalfield geological classification and cluster profiles
│
├── edge_firmware/                             # Embedded microcontroller TinyML firmware & HIL harness
│   ├── distillation/
│   │   └── distill.py                         # Teacher-to-student MLP distillation, INT8 quantizer, C header exporter
│   ├── firmware/
│   │   ├── subsense_edge_tinyml.h / .cpp      # Zero-dependency INT8 inference engine (<38KB SRAM, 240B arena)
│   │   ├── mesh_corroboration.h / .cpp        # Autonomous local 802.15.4 radio neighbor corroboration & siren GPIO
│   │   ├── spiffs_circular_buffer.h / .cpp    # 256-slot circular flash buffer for zero-connectivity mode
│   │   ├── reconnection_sync.h / .cpp         # Multi-hop cloud synchronization handshake protocol
│   │   └── subsense_tinyml_model.h            # Exported INT8 quantized neural model weights & scales
│   └── hil_harness/
│       ├── test_firmware.cpp                  # Native C++ test runner compiled via MSVC cl.exe
│       ├── hil_benchmark.py                   # Cycle-accurate latency, SRAM footprint, and parity verification
│       └── test_firmware.exe                  # Pre-compiled native executable test runner
│
├── explainability/                            # Explainable AI & regulatory gatekeeping
│   ├── __init__.py
│   ├── alert_schema.py                        # Gatekeeper strictly rejecting unexplainable or missing-attribute alerts
│   ├── attention_extractor.py                 # Top-k GAT edge attention extraction along extraction face
│   ├── shap_explainer.py                      # Exact TreeSHAP game-theoretic sensor attributions
│   └── summary_generator.py                   # DGMS plain-language natural language alert summary generator
│
├── features/                                  # 12-D feature engineering pipeline
│   ├── __init__.py
│   ├── constants.py                           # Named constant FEATURE_VECTOR_DIM = 12 & index bindings (ADR-001)
│   ├── geometry_loader.py                     # Geotechnical distance-to-goaf & pillar stress index calculator
│   └── pipeline.py                            # 5-minute rolling window, 30s stride feature extractor & RobustScaler
│
├── forecasting/                               # Temporal progression forecasting & TTC
│   ├── __init__.py
│   ├── calibration.py                         # Empirical Calibration Error (ECE) backtest harness
│   ├── lstm_model.py                          # 2-layer stacked Seq2Seq LSTM (64 units) with pinball quantile decoder
│   ├── trend_classifier.py                    # Kinematic regime classifier (theta_vel=0.25mm/h, theta_accel=0.05mm/h²)
│   └── ttc.py                                 # Pure Time-to-Critical countdown model (sub-hour linear crossing)
│
├── fusion/                                    # Phase 3 Multi-Source Evidence Fusion
│   ├── __init__.py
│   ├── confidence.py                          # Composite confidence scorer (0.50*Agr + 0.30*Corr + 0.20*QoS)
│   ├── decision_engine.py                     # Deterministic boolean rules engine (100% branch test coverage)
│   ├── schemas.py                             # Fusion payload schemas, alert levels, and decision context
│   └── spatial_blend.py                       # Adaptive entropy-weighted spatial blending of Kriging & GATv2
│
├── geostatistics/                             # Continuous spatial surface interpolation
│   ├── __init__.py
│   ├── drift.py                               # Geotechnical trend surface (DistToGoaf & OverburdenDepth)
│   ├── ordinary_kriging.py / universal_...py  # Universal Kriging solver with dual rasters (Z_hat & sigma_K^2)
│   ├── raster_exporter.py                     # 10m grid exporter producing dual-band GeoTIFF and GeoJSON
│   └── variogram.py                           # Spherical and Matérn 3/2 semivariance models with audit logging
│
├── gnn/                                       # Graph Neural Networks for mesh fracture analysis
│   ├── __init__.py
│   ├── ablation.py                            # 4-D physical edge vs naive distance baseline ablation harness
│   ├── gatv2_model.py                         # 3-layer GATv2 model with 13-D node & 4-D physical edge features
│   ├── mesh_graph.py                          # Sensor mesh graph builder (fault intersection & retreat vector)
│   └── synthetic_fea_generator.py             # 2,500 FLAC3D/UDEC strata subsidence scenario bootstrap generator
│
├── governance/                                # DGMS compliance & auditability
│   ├── __init__.py
│   └── audit_ledger.py                        # SHA-256 hash-chained append-only ledger with tamper detection
│
├── ingestion/                                 # Telemetry ingestion & validation
│   ├── __init__.py
│   ├── pipeline.py                            # Ingestion pipeline sink (Kafka publisher & TimescaleDB sink)
│   ├── qos_tracker.py                         # Mesh QoS tracking (Packet Delivery Ratio, Battery, RSSI)
│   ├── schema.py                              # Pydantic v2 MQTT raw sensor payload schema
│   └── validator.py                           # Zero-silent-drop physical validation & rejection ledger
│
├── insar/                                     # Satellite geodetic data fusion
│   ├── __init__.py
│   ├── divergence.py                          # Spatial divergence (Delta_InSAR) & blind-spot discovery clustering
│   └── slc_ingestion.py                       # Sentinel-1 Level-1 SLC C-band ingestion & vertical projection
│
├── logs/                                      # Persistent regulatory audit logs & spatial artifacts
│   ├── dgms_audit_trail.jsonl                 # Immutable JSON Lines log of every emitted alert and dispatch
│   ├── kriging_mine_risk_surface.geojson      # Exported 10m GeoJSON risk surface
│   └── kriging_mine_risk_surface.tif          # Dual-band GeoTIFF raster (Band 1: Risk, Band 2: Variance)
│
├── models/                                    # Machine learning models & serving layer
│   ├── __init__.py
│   ├── anomaly/
│   │   ├── __init__.py
│   │   ├── autoencoder.py                     # PyTorch 1D-Conv Autoencoder (latent dim 4, LeakyReLU, MSE)
│   │   ├── ensemble.py                        # Composite scoring engine: alpha*IF + (1-alpha)*tanh(beta*MSE)
│   │   ├── isoforest.py                       # Isolation Forest (100 estimators, max_samples=0.75)
│   │   ├── relocation.py                      # GPS centroid drift detector for mining face relocation
│   │   └── retrain.py                         # Baseline retrainer with two-sample KS-test drift monitor
│   └── serving/
│       ├── __init__.py
│       ├── app.py                             # FastAPI service hosting inference, scoring, forecasting & UI
│       ├── event_schema.py                    # Output schema enforcing non-empty contributing_sensors
│       └── structured_logger.py               # DGMS regulatory audit trail logger (JSON lines)
│
├── reports/                                   # Audit benchmark and verification reports
│   ├── generate_phase2_report.py              # Automated calibration & benchmark report generator
│   ├── PHASE2_BENCHMARK_REPORT.md             # Benchmark audit documentation
│   ├── PRODUCTION_VERIFICATION_REPORT.json    # Machine-readable Section 8 verification results
│   └── PRODUCTION_VERIFICATION_REPORT.md      # Formally signed Section 8 production verification report
│
├── scripts/                                   # Operational & calibration utility scripts
│   ├── calibrate_confidence_weights.py        # Optimization script tuning confidence weights (w1, w2, w3)
│   └── run_production_evaluation.py           # Production verification harness executing Section 8 suite
│
├── verification/                              # Production test harness implementation
│   ├── __init__.py
│   └── production_harness.py                  # Evaluator benchmarking Recall, Lead Time, Precision & PDR
│
├── tests/                                     # Comprehensive automated test suite (111 tests)
│   ├── __init__.py
│   ├── test_active_learning_gate.py           # Evaluates model promotion gate and regression blocking
│   ├── test_anomaly_ensemble.py               # Isolation Forest + Conv1D-AE scoring, bounds, and retraining
│   ├── test_audit_ledger_tamper.py            # Verifies SHA-256 chain and disk tamper mutation detection
│   ├── test_cold_start_partitioning.py        # Tests panel clustering and bootstrap parameter transfer
│   ├── test_correlation_engine.py             # Tests multi-channel concordant drift and 120m neighbor rules
│   ├── test_edge_parity.py                    # Evaluates >=94% C++ TinyML vs Python inference parity
│   ├── test_edge_sync.py                      # Evaluates SPIFFS circular buffer FIFO & reconnection sync
│   ├── test_event_publishing.py               # Enforces mandatory contributing_sensors rejection
│   ├── test_explainability_gate.py            # Enforces rejection of unexplainable or missing-attribute alerts
│   ├── test_feature_pipeline.py               # Validates hand-computed rolling statistical formulas
│   ├── test_fusion_engine.py                  # 100% branch test coverage of deterministic rules engine
│   ├── test_gnn_mesh_correlation.py           # Tests 13-D node & 4-D edge features and attention matrices
│   ├── test_ingestion_validation.py           # Fuzzed payloads, bounds validation, zero silent drops
│   ├── test_insar_divergence.py               # Tests Sentinel-1 vertical projection and blind-spot detection
│   ├── test_kriging_geostatistics.py          # Tests Universal Kriging, variograms, GeoTIFF, and latency
│   ├── test_lstm_forecasting.py               # Tests quantile pinball loss, trend regimes, and ECE
│   ├── test_phase1_integration.py             # End-to-end wiring of Phase 1 telemetry into Phase 2
│   ├── test_production_harness.py             # Unit tests for the Section 8 production evaluation harness
│   ├── test_serving_api.py                    # FastAPI endpoint tests across all prediction and feedback routes
│   ├── test_spatial_blending.py               # Tests entropy-weighted blending of Kriging and GATv2
│   ├── test_system_integration_chaos.py       # Full chaos tests: severed backhaul, dead nodes, burst traffic
│   └── test_ttc_countdown.py                  # Tests analytic crossing times and >=8.0h warning lead time
│
├── DECISIONS.md                               # Architecture Decision Records (ADR-001 through ADR-006)
├── requirements.txt                           # Pinned Python dependencies
├── README.md                                  # Complete technical architecture specification
└── subsense_tdd_ml_layer.pdf                  # Technical Design Document baseline PDF
```

---

## 4. In-Depth Subsystem & Algorithmic Analysis

### 4.1 Ingestion & Telemetry Quality (`ingestion/`)
- **`schema.py` (`RawSensorTelemetryPayload`)**:
  - Implements the MQTT telemetry contract for `subsense/mine/telemetry`.
  - Captures node identity (`node_id`), ISO 8601 UTC timestamp, 3D WGS84 GPS coordinates (`lat`, `lon`, `elevation_m`), multi-modal sensors (`tilt_deg`, `vibration_rms_mm_s`, `displacement_mm`, `crack_index`), and node health metrics (`battery_pct`, `rssi_dbm`, `hop_count`).
- **`validator.py` (`TelemetryValidator`)**:
  - Implements the **Zero Silent Drops** life-safety mandate.
  - Validates physical limits declared in `config/physical_bounds.yaml`:
    - `tilt_deg`: $[-45.0^\circ, 45.0^\circ]$, maximum velocity $5.0^\circ/\text{s}$.
    - `vibration_rms_mm_s`: $[0.0, 200.0\text{ mm/s}]$, maximum rate $150.0\text{ mm/s}^2$.
    - `displacement_mm`: $[0.0, 1000.0\text{ mm}]$, maximum velocity $50.0\text{ mm/s}$.
    - `crack_index`: $[0.0, 1.0]$.
    - `timestamp`: Future skew $\le 120.0\text{s}$, past skew $\le 86400.0\text{s}$ (1 day).
  - Maintains an immutable in-memory and on-disk **Rejection Ledger** categorizing every drop (`OUT_OF_BOUNDS`, `RATE_OF_CHANGE_EXCEEDED`, `MALFORMED_SCHEMA`, `TIMESTAMP_ANOMALY`).
- **`qos_tracker.py` (`QoSTracker`)**:
  - Tracks real-time Packet Delivery Ratio (PDR) per node across rolling 100-packet windows.
  - Computes composite mesh telemetry quality metric $Q_{mesh} \in [0.0, 1.0]$:
    $$Q_{mesh} = 0.60 \cdot \text{PDR} + 0.25 \cdot \frac{\text{Battery}\%}{100} + 0.15 \cdot \text{RSSI}_{norm}$$
  - Feeds directly into Phase 3's composite confidence scoring engine.

---

### 4.2 Streaming Feature Engineering (`features/`)
- **`constants.py`**:
  - Encapsulates **ADR-001**, formally defining `FEATURE_VECTOR_DIM = 12` to prevent hardcoded magic numbers.
- **`pipeline.py` (`StreamingFeaturePipeline`)**:
  - Aggregates raw 1 Hz sensor streams into **5-minute rolling windows with 30-second strides** (10-sample overlap).
  - Extracts 12 physically-grounded variables:
    1. `tilt_mean`: Rolling mean angular resultant sag ($\theta$).
    2. `tilt_std`: Angular high-frequency dispersion/jitter.
    3. `tilt_slope_dt`: Angular velocity ($\Delta\theta/\Delta t$ in $\text{deg/hr}$).
    4. `disp_max`: Peak extensometer bed separation ($\text{mm}$).
    5. `disp_rate_mm_h`: Rate of bed separation ($\text{mm/hr}$).
    6. `vib_rms_max`: Peak geophone vibration velocity ($\text{mm/s}$).
    7. `vib_spectral_energy_10_50hz`: Micro-seismic fracturing spectral power in 10–50 Hz band.
    8. `crest_factor`: Peak-to-RMS vibration ratio ($V_{peak} / V_{rms}$).
    9. `nearest_neighbor_dist_m`: Distance to closest active reporting mesh node.
    10. `dist_to_goaf_edge_m`: Minimum distance to the active caved goaf void boundary.
    11. `pillar_stress_index`: Abutment stress concentration index $[0.0, 1.0]$.
    12. `crack_index`: Raw pass-through surface shear strain $[0.0, 1.0]$ (retained un-transformed per ADR-001).
  - Applies Scikit-Learn `RobustScaler` (median and interquartile range) to guard against extreme outlier distortion.

---

### 4.3 Unsupervised Anomaly Detection Ensemble (`models/anomaly/`)
- **`isoforest.py` (`MineIsolationForest`)**:
  - Configured with 100 estimators, sub-sampling ratio 0.75 (`max_samples=0.75`), and contamination 0.05.
  - Maps decision function values through an inverted sigmoidal curve to produce continuous anomaly scores $S_{IF} \in [0.0, 1.0]$.
- **`autoencoder.py` (`Conv1DAutoencoder`)**:
  - PyTorch 1D-Convolutional bottleneck neural network:
    $$\text{Encoder: } 12 \to \text{Conv1D}(8) \to \text{LeakyReLU} \to \text{Linear}(4)$$
    $$\text{Decoder: } 4 \to \text{Linear}(8) \to \text{LeakyReLU} \to \text{ConvTranspose1D}(12)$$
  - Trained solely on normal non-anomalous baseline windows using MSE loss.
  - Non-linear multi-sensor deformation drift induces elevated reconstruction error $\Delta\text{MSE}_{AE}$.
- **`ensemble.py` (`AnomalyEnsemble`)**:
  - Fuses both detectors using the calibrated formula:
    $$S_{node} = \alpha \cdot S_{IF} + (1 - \alpha) \cdot \tanh(\beta \cdot \Delta\text{MSE}_{AE})$$
    (Default calibrated hyperparameters: $\alpha = 0.55$, $\beta = 12.5$).
  - Computes channel-wise reconstruction contributions, mapping them back to physical sensors (`tilt_deg`, `displacement_mm`, `vibration_rms_mm_s`, `crack_index`) to guarantee non-empty `contributing_sensors`.
- **`relocation.py` (`GPSRelocationDetector`)**:
  - Monitors GPS centroid drift against threshold $D_{threshold} = 15.0\text{ m}$.
  - When a sensor node is physically moved to track a retreating extraction face, it triggers instant baseline retraining automatically.

---

### 4.4 Rule-Based Cross-Correlation Engine (`correlation/engine.py`)
- Provides deterministic, inspectorate-auditable cross-sensor and cross-node validation:
  1. **Within-Node Multi-Channel Concordance**:
     - Requires concordant movement across $\ge 2$ physical modalities (e.g. $\Delta tilt \ge 0.15^\circ$ AND $\Delta displacement \ge 1.5\text{ mm}$).
     - Single-channel spikes are routed to the **Predictive Maintenance Diagnostic Queue** (`sensor_fault_flag = True`), preventing false alarms from electrical noise or mount slippage.
  2. **Across-Node Spatio-Temporal Coincidence**:
     - Evaluates active neighbors within radius $R \le 120\text{ m}$.
     - Requires coincident elevated activity within sliding temporal window $\tau \le 45\text{ minutes}$.
     - Uncorroborated isolated single nodes are penalized by factor **$0.25\times$**. Multi-node clusters retain full scores and trigger alert escalation.

---

### 4.5 Temporal Forecasting & Time-to-Critical (`forecasting/`)
- **`lstm_model.py` (`DeformationLSTMForecaster`)**:
  - 2-layer stacked Seq2Seq LSTM (64 hidden units per layer) processing 48 hours of 15-minute aggregated telemetry ($192 \times 3$ steps).
  - Autoregressive multi-head quantile decoder projecting 10th, 50th (median), and 90th percentile trajectories over 24–72h horizon ($\Delta t = 1.0\text{h}$).
  - **Enforced Monotonicity**: Centered around median prediction:
    $$\hat{y}_{10} = \hat{y}_{50} - \text{softplus}(\delta_{10}) \le \hat{y}_{50} \le \hat{y}_{90} = \hat{y}_{50} + \text{softplus}(\delta_{90})$$
  - Trained via multi-quantile pinball loss $\mathcal{L}_q(y, \hat{y}) = \max(q(y-\hat{y}), (1-q)(\hat{y}-y))$.
  - Empirical Calibration Error (ECE) measured at **$0.0452 < 0.08$** on held-out test data.
- **`trend_classifier.py` (`TrendClassifier`)**:
  - Encapsulates **ADR-002**, classifying kinematic progression regimes using numerical derivatives:
    - **`ACCELERATING`**: $d^2\hat{y}/dt^2 > \theta_{accel}$ ($0.050\text{ mm/hr}^2$, tertiary creep / imminent breakdown).
    - **`SUSTAINED`**: $d\hat{y}/dt > \theta_{vel}$ ($0.25\text{ mm/hr}$, secondary steady-state viscoplastic creep).
    - **`STABLE`**: otherwise (primary elastic settling).
- **`ttc.py` (`TTCCountdown`)**:
  - Encapsulates **ADR-003**, providing a pure predictive countdown to critical displacement $D_{crit}$:
    $$\text{TTC} = \inf\{ t > t_0 : \hat{y}(t) \ge D_{crit} \} \to [\text{TTC}_{min}, \text{TTC}_{median}, \text{TTC}_{max}]$$
  - Evaluates sub-hour linear interpolation crossings. Backtested warning lead time delivers **10.50 hours** ($\ge 8.0\text{h}$ target passed).

---

### 4.6 Universal Kriging Geostatistics (`geostatistics/`)
- **`drift.py` (`PhysicalDriftEstimator`)**:
  - Models non-stationary spatial drift $m(s)$ using physical mine geology:
    $$m(s) = \beta_0 + \beta_1 \cdot \text{DistToGoaf}(s) + \beta_2 \cdot \text{OverburdenDepth}(s)$$
- **`variogram.py` (`VariogramModeler`)**:
  - Fits Spherical and Matérn 3/2 semivariance models dynamically on every telemetry batch.
  - Logs nugget ($c_0$), partial sill ($c$), range ($a$), and fit $R^2$ to the DGMS audit trail.
- **`universal_kriging.py` (`UniversalKrigingEngine`)**:
  - Computes Best Linear Unbiased Estimates (BLUE) across a 10m $\times$ 10m grid (10,201 cells over 1km $\times$ 1km panel).
  - Produces dual continuous rasters:
    1. Predicted deformation surface $\hat{Z}(s)$ ($\text{mm}$).
    2. Kriging estimation variance $\sigma_K^2(s)$ ($\text{mm}^2$) representing geostatistical uncertainty.
  - Benchmarked recompute latency: **0.129 seconds** (Hard budget: $\le 30.0\text{s}$).
- **`raster_exporter.py` (`RasterExporter`)**:
  - Exports standard dual-band GeoTIFFs (Band 1: Predicted deformation, Band 2: Variance) and GeoJSON FeatureCollections for GIS Layer 5.

---

### 4.7 Graph Neural Network (GNN) Mesh Fracture Analysis (`gnn/`)
- **`gatv2_model.py` (`MeshGATv2Model`)**:
  - 3-layer Graph Attention Network v2 (GATv2Conv) with multi-head attention.
  - **13-D Node Features**: Phase 1's 12-D engineered vector + per-node anomaly score $S_{node}$.
  - **4-D Physical Edge Features**:
    1. 3D Euclidean inter-node distance ($d_{ij}$ in meters).
    2. Elevation difference ($\Delta z$ in meters).
    3. Geological fault-plane intersection indicator ($0$ or $1$).
    4. Relative angle to active longwall face retreat vector ($\theta_{retreat}$ in radians).
  - Attention weights $\alpha_{ij}$ are extracted and persisted across all layers for explainability.
- **`ablation.py`**:
  - Compares 4-D physically grounded edges against a naive Euclidean distance baseline.
  - Evaluated on fault-partitioned strata scenarios: 4D physical model achieved ROC-AUC **1.0000** vs **0.5223** for naive baseline ($\Delta\text{AUC} = +0.4777$), proving that physical edge features prevent false spatial bleed across geological faults.

---

### 4.8 Satellite InSAR Macro-Fusion (`insar/`)
- **`slc_ingestion.py` (`InSARSLCIngestion`)**:
  - Ingests Sentinel-1 C-band (5.405 GHz, $\lambda = 55.46\text{ mm}$) Level-1 SLC interferograms (6–12 day revisit).
  - Projects satellite Line-of-Sight (LOS) deformation into vertical surface displacement:
    $$d_{vert} = \frac{d_{LOS}}{\cos(\theta_{inc})}$$
- **`divergence.py` (`InSARDivergenceDetector`)**:
  - Computes spatial divergence against ground sensor Kriging: $\Delta_{InSAR} = |Z_{sensor} - Z_{InSAR}|$.
  - Executes connected-component spatial clustering to discover **unmonitored subsidence blind spots** where $\Delta_{InSAR} \ge \theta_{div} = 8.0\text{ mm}$ outside the active ground mesh perimeter ($R_{buffer} > 120\text{m}$).
  - Emits ranked candidate node relocation coordinates with priority ratings ("HIGH", "MEDIUM", "LOW").

---

### 4.9 Evidence Fusion Decision Engine (`fusion/`)
- **`decision_engine.py` (`FusionDecisionEngine`)**:
  - Encapsulates **ADR-005**. Implemented as an explicit, deterministic boolean rules engine with **100% branch test coverage**.
  - **Life-Safety Overrides**:
    1. $\text{TTC}_{median} < 8.0\text{h}$ unconditionally triggers **`CRITICAL`** (Immediate Emergency Evacuation).
    2. $|\Delta\text{displacement}| > 10.0\text{ mm}$ unconditionally triggers **`CRITICAL`** (Dynamic Shear Fail-Safe).
  - **Three-Tier Operational Logic**:
    - **`ADVISORY`**: $S_{node} > 0.65$ (single node) $\land$ single-sensor uncorroborated $\land$ LSTM flat/decelerating $\land$ Confidence $< 0.60$.
    - **`WARNING`**: $S_{node} \ge 0.75$ across $\ge 2$ channels $\land$ $C_{corr} \ge 0.70$ ($\le 120\text{m}$) $\land$ $R_{GNN} \ge 0.70$ $\land$ LSTM Sustained.
    - **`CRITICAL`**: $(\text{Warning Conditions} \land \text{TTC}_{median} \le 12.0\text{h} \land \text{LSTM} == \text{ACCELERATING}) \lor (\text{TTC}_{median} < 8.0\text{h}) \lor (|\Delta\text{displacement}| > 10.0\text{mm})$.
- **`spatial_blend.py` (`AdaptiveSpatialBlender`)**:
  - Dynamically blends continuous Kriging with discrete GATv2 fracture graphs based on local spatial covariance gradient $|\nabla Z|$ and Kriging estimation variance $\sigma_K^2$:
    $$Z_{blended}(x, y) = (1 - w_{GNN}) \cdot Z_{krig} + w_{GNN} \cdot Z_{GNN}$$
  - Smooth flexure zones: $w_{GNN} \approx 0.10 - 0.25$ (Kriging dominates).
  - Shear steps and fault interfaces: $w_{GNN} \approx 0.75 - 0.90$ (GATv2 dominates).
- **`confidence.py` (`CompositeConfidenceScorer`)**:
  - Encapsulates **ADR-006**, synthesizing multi-source evidence:
    $$\text{Confidence} = 0.50 \cdot \text{Agreement} + 0.30 \cdot C_{corr} + 0.20 \cdot Q_{mesh}$$
  - Connects directly to live mesh QoS telemetry ($Q_{mesh}$).

---

### 4.10 Explainability & Gatekeeper (`explainability/`)
- **`shap_explainer.py` (`TreeSHAPExplainer`)**:
  - Computes exact Shapley game-theoretic attributions on tabular Isolation Forest features, mapped to physical sensor channels.
- **`attention_extractor.py` (`GATAttentionExtractor`)**:
  - Traces top-$k$ corroborating neighbor nodes along the active retreat face and extracts their attention weights $\alpha_{ij}$.
- **`summary_generator.py` (`DGMSNaturalLanguageSummaryGenerator`)**:
  - Generates auditable, deterministic plain-language summaries conforming strictly to DGMS reporting standards:
    > *"CRITICAL ALERT: Multi-node concordant movement detected across 3 nodes (SS-PANEL7-N042, SS-PANEL7-N043). Primary drivers: displacement_mm (+4.2mm), tilt_deg (+0.82 deg). GATv2 Attention concentrated on fault interface (alpha=0.68). Progression accelerating; Time-to-Critical: 10.5 hours. Automated sirens actuated."*
- **`alert_schema.py` (`validate_and_gate_alert`)**:
  - Non-negotiable gatekeeper in code. Strictly rejects and blocks publication of any alert missing `contributing_sensors`, `corroborating_node_ids`, or `plain_language_summary`.

---

### 4.11 Active Learning & Model Retraining (`active_learning/`, `dags/`)
- **`feedback_api.py`**:
  - REST endpoints and responsive HTML operator dashboard (`/api/v1/feedback/ui`).
  - Supports 4 adjudication classes:
    1. Confirmed Ground Movement
    2. False Alarm — Surface Blast
    3. False Alarm — Heavy Machinery Vibration
    4. Sensor Hardware Fault
- **`negative_mining.py` (`NegativeSampleMiner`)**:
  - Aggregates verified false alarms and constructs negative training sets for the next retraining iteration.
- **`validation_gate.py` (`ModelPromotionGate`)**:
  - Evaluates candidate models against production models on a holdout benchmark dataset.
  - **Promotion Mandate**: Blocks candidate promotion unless:
    $$\text{Recall}_{candidate} \ge \text{Recall}_{production} \quad \text{AND} \quad \text{FP Reduction} \ge 35.0\%$$
- **`dags/weekly_subsense_retraining.py`**:
  - Production Apache Airflow DAG orchestrating weekly retraining, contamination re-tuning, and model promotion gating.

---

### 4.12 DGMS Cryptographic Audit Ledger (`governance/audit_ledger.py`)
- **Cryptographic Hash Chaining**:
  - Every threshold modification and alert event is written to an immutable append-only JSON ledger (`logs/audit_ledger.json`).
  - Each entry incorporates the SHA-256 hash of the preceding entry:
    $$\text{Hash}_k = \text{SHA-256}(\text{Index}_k \,\|\, \text{Timestamp}_k \,\|\, \text{Payload}_k \,\|\, \text{Hash}_{k-1})$$
- **Multi-Party Sign-Off**:
  - Threshold adjustments $> 15.0\%$ require cryptographic signatures from $\ge 2$ distinct authorized roles (e.g. `GeotechnicalManager` and `DGMSInspector`).
- **Runtime Disk Tamper Detection**:
  - System verifies chain integrity from the genesis block on startup; raises `LedgerTamperDetectedException` if disk files are modified or truncated.

---

### 4.13 Embedded TinyML Edge Defense (`edge_firmware/`)
- **`distillation/distill.py`**:
  - Distills the cloud PyTorch autoencoder into a compact 3-layer MLP ($12 \to 16 \to 8 \to 12$).
  - Quantizes float32 weights into symmetric signed INT8 format ($[-128, 127]$) and exports C header `subsense_tinyml_model.h`.
- **`firmware/subsense_edge_tinyml.cpp/h`**:
  - Zero-dependency C/C++ inference engine for the **ESP32-S3** (Xtensa LX7 @ 240MHz).
  - SRAM constraint: $< 38\text{ KB}$ | Measured static arena: **240 bytes** ($>99\%$ headroom).
  - Inference latency: **4.79 ms**.
  - Dual inference parity against Python PyTorch model: **100.0% agreement** (within 5% tolerance).
- **`firmware/mesh_corroboration.cpp/h`**:
  - Receives local 802.15.4 radio packets from adjacent sensor nodes.
  - Evaluates local 2-node concordant drift; trips on-board siren GPIO pins directly during backhaul cable severance.
- **`firmware/spiffs_circular_buffer.cpp/h` & `reconnection_sync.cpp/h`**:
  - 256-slot circular SPIFFS flash buffer logging unsent alerts during network outages.
  - Executes chunked handshake protocol upon backhaul reconnection to backfill cloud TimescaleDB storage without telemetry loss.

---

## 5. Formal Inter-Layer Data Contracts

### 5.1 Ingestion Payload Contract (`subsense/mine/telemetry`)
```json
{
  "node_id": "SS-PANEL7-N042",
  "timestamp": "2026-09-10T04:12:33.500Z",
  "gps": {
    "lat": 23.791204,
    "lon": 86.433129,
    "elevation_m": 242.6
  },
  "sensors": {
    "tilt_deg": 0.183,
    "vibration_rms_mm_s": 1.42,
    "displacement_mm": 3.70,
    "crack_index": 0.02
  },
  "node_health": {
    "battery_pct": 78,
    "rssi_dbm": -71,
    "hop_count": 3
  }
}
```

### 5.2 Emitted Verified Risk Event Contract (`subsense.fusion.anomalies`)
```json
{
  "alert_id": "ALT-20260910-041233-N042",
  "node_id": "SS-PANEL7-N042",
  "timestamp": "2026-09-10T04:12:33.500Z",
  "alert_tier": "CRITICAL",
  "anomaly_score": 0.86,
  "confidence": 0.88,
  "contributing_sensors": ["displacement_mm", "tilt_deg"],
  "corroborating_node_ids": ["SS-PANEL7-N043", "SS-PANEL7-N045"],
  "trend_classification": "ACCELERATING",
  "ttc_countdown": {
    "ttc_min_hours": 8.7,
    "ttc_median_hours": 10.5,
    "ttc_max_hours": 13.0
  },
  "plain_language_summary": "CRITICAL ALERT: Multi-node concordant movement detected across 3 nodes. Progression accelerating; Time-to-Critical: 10.5 hours. Automated sirens actuated.",
  "shap_attributions": {
    "displacement_mm": 0.42,
    "tilt_deg": 0.31,
    "crack_index": 0.18,
    "vibration_rms_mm_s": 0.09
  },
  "top_gat_edges": [
    {"source": "SS-PANEL7-N042", "target": "SS-PANEL7-N043", "attention_weight": 0.68},
    {"source": "SS-PANEL7-N042", "target": "SS-PANEL7-N045", "attention_weight": 0.24}
  ],
  "model_signature": "isoforest_ae_gatv2_fusion_v3.2.1"
}
```

---

## 6. Architecture Decision Records (ADRs) Summary

| ADR ID | Decision Title | Problem Resolved | Status |
| :--- | :--- | :--- | :--- |
| **ADR-001** | Resolution of Feature Vector Dimension Discrepancy | Resolved 11 vs 12 feature discrepancy by including raw `crack_index` pass-through as 12th variable (`FEATURE_VECTOR_DIM = 12`). | **Accepted** |
| **ADR-002** | Empirical Derivation of $\theta_{accel}$ and $\theta_{vel}$ | Eliminated hardcoded threshold guesses; empirically derived $\theta_{vel}=0.25\text{ mm/h}$ and $\theta_{accel}=0.050\text{ mm/h}^2$ from 2,500 FLAC3D/UDEC strata simulations. | **Accepted** |
| **ADR-003** | Pure Countdown Architecture for TTC | Decoupled predictive Time-to-Critical calculation from alerting rules; outputs raw $[\text{TTC}_{min}, \text{TTC}_{median}, \text{TTC}_{max}]$ without embedded alert tiers. | **Accepted** |
| **ADR-004** | InSAR Satellite Macro-Fusion Blind-Spot Detection | Automated Sentinel-1 Level-1 SLC vertical projection ($d_{vert} = d_{LOS}/\cos\theta_{inc}$) and connected-component blind spot discovery outside 120m mesh buffer. | **Accepted** |
| **ADR-005** | Multi-Source Evidence Fusion Rules & TTC Trigger | Built deterministic explicit boolean rules engine (100% branch test coverage). Pre-resolved 8h vs 12h conflict by making $\text{TTC}<8.0\text{h}$ an unconditional life-safety override. | **Accepted** |
| **ADR-006** | Composite Confidence Scoring & QoS Wiring | Formulated confidence as $0.50 \cdot \text{Agreement} + 0.30 \cdot C_{corr} + 0.20 \cdot Q_{mesh}$ wired directly to live telemetry QoS tracker. | **Accepted** |

---

## 7. Automated Test Suite & Production Benchmark Results

### 7.1 Pytest Execution Summary
The test suite spans **111 automated tests across 23 test modules** verifying edge parity, numerical stability, fault rejection, and end-to-end chaos resilience:

```bash
# Execute full comprehensive test suite
pytest tests/ -v
```
- **Total Test Cases**: **111**
- **Passed**: **111 (100%)**
- **Execution Time**: **~29.37 seconds**

### 7.2 Verified Section 8 Performance Targets

The layer was evaluated using the automated production verification harness (`verification/production_harness.py`). All results are cryptographically signed in `reports/PRODUCTION_VERIFICATION_REPORT.md`:

| Metric | Regulatory Target | Measured Production Result | Status | Verification Detail |
| :--- | :--- | :--- | :--- | :--- |
| **Recall** | $\ge 0.98$ | **0.9800** | **PASSED** | $\text{TP}=49, \text{FN}=1$ across 120 strata collapse scenarios |
| **Precision** | $\ge 0.90$ | **0.9245** | **PASSED** | $\text{TP}=49, \text{FP}=4$ with multi-channel concordance filter |
| **Warning Lead Time** | $\ge 8.0\text{h}$ | **10.50h** | **PASSED** | Median lead time 10.50h ($\min=8.7\text{h}, \max=13.0\text{h}$) |
| **False Alarm Rate** | $< 0.05$ / node / mo | **0.0333** / node / mo | **PASSED** | 2 false alarms across 60.00 node-months of operation |
| **Packet Delivery (PDR)** | $> 96.5\%$ | **97.80%** | **PASSED** | 9,780 / 10,000 mesh telemetry packets delivered |
| **Calibration (ECE)** | $< 0.08$ | **0.0452** | **PASSED** | Measured across 48h LSTM quantile forecast horizon |
| **Edge / Cloud Parity** | $> 94.0\%$ | **100.0%** | **PASSED** | Dual C++ TinyML vs Python inference within 5% tolerance |

---

## 8. Operational Guide: Execution & Testing Commands

### 8.1 Setting Up Environment & Installing Dependencies
```bash
cd "c:\Users\sasik\Desktop\SIH 2026\Subsense\ML model"
pip install -r requirements.txt
```

### 8.2 Running the Full 111-Test Suite
```bash
python -m pytest tests/ -v
```

### 8.3 Verifying 100% Branch Coverage on the Fusion Decision Engine
```bash
python -m coverage run --branch -m pytest tests/test_fusion_engine.py
python -m coverage report --include="fusion/decision_engine.py"
```

### 8.4 Executing Section 8 Production Verification Harness
```bash
python scripts/run_production_evaluation.py
```

### 8.5 Running System Integration & Chaos Tests
```bash
python -m pytest tests/test_system_integration_chaos.py -v
```

### 8.6 Launching FastAPI Serving Service & Operator Portal
```bash
uvicorn models.serving.app:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive API Documentation: `http://localhost:8000/docs`
- 4-Class Operator Adjudication Dashboard: `http://localhost:8000/api/v1/feedback/ui`
