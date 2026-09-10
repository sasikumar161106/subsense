# SubSense — AI/ML Data Inference Layer (Layer 4)
## Complete Repository Details & Technical Architecture Specification

---

## 1. Executive Summary & System Identity

The **AI/ML Data Inference Layer (Layer 4)** is the analytical intelligence core of the **SubSense Smart Underground Coal Mine Subsidence Monitoring Platform** (developed for Smart India Hackathon 2026). Situated between upstream physical sensor telemetry (LoRaWAN surface mesh network & Time-Series DB) and downstream operational systems (**GIS & 3D Digital Twin Layer 5** and **Alerting System Layer 6**), Layer 4 transforms raw, noisy multi-sensor telemetry into explainable, continuous, geostatistically interpolated, and predictive **Risk Events**.

### Key System Attributes:
- **Repository Location**: `c:\Users\sasik\Desktop\SIH 2026\Subsense\AIML data inference`
- **Technical Specification Baseline**: `SubSense AI/ML Data Inference Layer Technical Design Document v1.0`
- **Regulatory Standard**: DGMS (Directorate General of Mines Safety) Underground Coal Mine Subsidence Monitoring Guidelines
- **Technology Stack**: Python 3.11+, PyTorch 2.2+, Scikit-Learn 1.4+, FastAPI, SciPy Geostatistics, NetworkX, NumPy, Pydantic v2
- **Test Suite Status**: **34/34 passed** (100% pass rate) across 13 automated test suites
- **SLA Performance Target**: $\le 15.0\text{ s}$ per cycle | **Measured Latency**: $\sim 0.045\text{ s}$ ($>330\times$ headroom)

---

## 2. End-to-End Pipeline Architecture & Data Flow

```
                               +-------------------------------------------------------+
                               |              UPSTREAM TELEMETRY SOURCES               |
                               |    Surface Sensor Mesh (Tilt, Vibration, Strain,      |
                               |    Crack) + Node Health (Battery, RSSI, Status)       |
                               +---------------------------+---------------------------+
                                                           | Raw telemetry streams
                                                           v
+-----------------------------------------------------------------------------------------------------------------------+
|                                    LAYER 4: AI/ML DATA INFERENCE PIPELINE                                             |
|                                                                                                                       |
|  +-------------------------------------+      +-------------------------------------+                                 |
|  |     1. SENSOR FAULT FILTERING       | ---> |      2. FEATURE EXTRACTION          |                                 |
|  |   Rejects flatlines, dead batteries |      |   Sliding window (60 samples):      |                                 |
|  |   (<2.4V), degraded RF (<-115dBm)   |      |   tilt rate, RMS vibe, strain drift |                                 |
|  +-------------------------------------+      +------------------+------------------+                                 |
|                                                                  | 8D Feature Vectors                                 |
|                                                                  v                                                    |
|                                               +-------------------------------------+                                 |
|                                               |    3. UNSUPERVISED ANOMALY ENSEMBLE |                                 |
|                                               |   Isolation Forest (45%)            |                                 |
|                                               |   + Deep Autoencoder (55%)          |                                 |
|                                               +------------------+------------------+                                 |
|                                                                  | Per-node anomaly score [0, 1]                      |
|                                                                  v                                                    |
|                                               +-------------------------------------+                                 |
|                                               |    4. MESH GRAPH SPATIAL GNN        |                                 |
|                                               |   Gaussian RBF proximity graph (150m|                                 |
|                                               |   Suppresses single-node spikes     |                                 |
|                                               |   Boosts multi-node clusters        |                                 |
|                                               +------------------+------------------+                                 |
|                                                                  |                                                    |
|                                      +---------------------------+---------------------------+                        |
|                                      |                                                       |                        |
|                                      v                                                       v                        |
|                     +---------------------------------+                     +---------------------------------+       |
|                     |   5. LSTM PROGRESSION FORECAST  |                     |    6. ORDINARY KRIGING SURFACE  |       |
|                     | - Predicts velocity & accel     |                     | - Semivariogram spatial fit     |       |
|                     | - 4-Tier trend classification   |                     | - 2D continuous risk raster     |       |
|                     | - Time-to-Critical (TTC) solver |                     | - Estimation variance mask      |       |
|                     +----------------+----------------+                     +----------------+----------------+       |
|                                      |                                                       |                        |
|                                      +---------------------------+---------------------------+                        |
|                                                                  |                                                    |
|                                                                  v                                                    |
|                                               +-------------------------------------+                                 |
|                                               |  7. CONFIDENCE & EXPLAINABILITY     |                                 |
|                                               | - Multi-factor confidence score     |                                 |
|                                               | - Auditable deterministic narrative |                                 |
|                                               +------------------+------------------+                                 |
+------------------------------------------------------------------|----------------------------------------------------+
                                                                   |
                                    +------------------------------+------------------------------+
                                    |                                                             |
                                    v Structured Risk Events                                      v Continuous 2D Raster
+-------------------------------------------------------+     +-------------------------------------------------------+
|              ALERTING SYSTEM (LAYER 6)                |     |              GIS & DIGITAL TWIN (LAYER 5)             |
| - DGMS multi-tier alert escalation (Advisory/Crit)    |     | - Real-time continuous deformation heatmap            |
| - Automated SMS/WhatsApp/Email dispatch               |     | - Opacity-modulated estimation variance mask          |
| - Evacuation trigger management                       |     | - Dynamic risk-zone polygon boundaries                |
+---------------------------+---------------------------+     +---------------------------+---------------------------+
                            |                                                             |
                            | Operator Feedback (False Alarm / Confirmed)                 | Satellite Pass (Sentinel-1)
                            v                                                             v
+-------------------------------------------------------+     +-------------------------------------------------------+
|           AUTOMATIC FEEDBACK LEARNING LOOP            |     |         InSAR SATELLITE CROSS-VALIDATION              |
| - Short-term: Dynamic per-site threshold nudging      |     | - Wide-area macro-scale geodetic sanity check         |
| - Long-term: Holdout-validated automated retraining   |     | - Flags unmonitored subsidence basins outside mesh    |
| - Model Registry: Version tracking & instant rollback |     | - Flags ground-sensor vs satellite velocity mismatches|
+---------------------------+---------------------------+     +-------------------------------------------------------+
                            | Retrained Teachers
                            v
+-------------------------------------------------------+
|             TINYML EDGE DISTILLATION BRIDGE           |
| - INT8 symmetric quantization (<32 KB memory footprint)|
| - Edge MCU deployment (ARM Cortex-M4 / ESP32)         |
| - Edge-cloud reconciliation & drift monitoring        |
+-------------------------------------------------------+
```

---

## 3. Complete Directory & File Inventory

The complete folder layout of `c:\Users\sasik\Desktop\SIH 2026\Subsense\AIML data inference` contains **30 production files and tests** organized into clean architectural sub-packages:

```
AIML data inference/
│
├── config/                                    # Configuration profiles
│   ├── default_config.yaml                    # Global pipeline, model, and threshold configurations
│   └── site_configs/
│       └── SITE-JHARIA-04.yaml                # Site-specific UTM coordinates, bounds, and node layouts
│
├── data/                                      # Data generation and synthetic baselines
│   └── synthetic_generator.py                 # Multi-sensor time-series & InSAR grid generator
│
├── src/                                       # Core implementation source code
│   ├── __init__.py                            # Package initialization
│   │
│   ├── api/                                   # FastAPI serving layer (REST interfaces)
│   │   ├── __init__.py
│   │   ├── main.py                            # FastAPI app, lifespan, CORS, and router registration
│   │   ├── router_inference.py                # POST /api/v1/inference/run, GET /health
│   │   ├── router_kriging.py                  # POST /api/v1/kriging/surface
│   │   ├── router_insar.py                    # POST /api/v1/insar/cross-validate
│   │   └── router_feedback.py                 # POST /api/v1/feedback/submit, /retrain, /rollback
│   │
│   ├── explainability/                        # Explainable AI (XAI) & confidence scoring
│   │   ├── __init__.py
│   │   ├── confidence_scorer.py               # Composite confidence scoring (Agreement + GNN + Nodes)
│   │   └── narrative_generator.py             # Deterministic, non-hallucinated natural language generator
│   │
│   ├── feedback_loop/                         # Closed-loop adaptation & model lifecycle
│   │   ├── __init__.py
│   │   ├── online_calibrator.py               # Short-term fast dynamic threshold adaptation
│   │   ├── feedback_consumer.py               # Operator feedback buffer and dispatcher
│   │   ├── retraining_orchestrator.py         # Automated retraining, validation, and promotion
│   │   └── model_registry.py                  # Model version tracking, audit log, and rollback
│   │
│   ├── geostats/                              # Geostatistical spatial interpolation
│   │   ├── __init__.py
│   │   ├── variogram.py                       # Theoretical Semivariogram (Spherical/Exponential/Gaussian)
│   │   └── ordinary_kriging.py                # Ordinary Kriging 2D solver with estimation variance
│   │
│   ├── ingestion/                             # Ingestion, buffering, and data quality
│   │   ├── __init__.py
│   │   ├── fault_filter.py                    # Hardware fault, flatline, dead battery, RF loss filtering
│   │   ├── feature_extractor.py               # Physical time-series feature engineering
│   │   └── window_buffer.py                   # Ring buffer managing sliding windows (60 samples)
│   │
│   ├── insar/                                 # Satellite geodetic data fusion
│   │   ├── __init__.py
│   │   └── insar_cross_validator.py           # Sentinel-1 cross-validation & discrepancy detector
│   │
│   ├── models/                                # Analytical & Deep Learning models
│   │   ├── __init__.py
│   │   ├── isolation_forest_detector.py       # Unsupervised Isolation Forest outlier detector
│   │   ├── autoencoder_detector.py            # Deep PyTorch bottleneck autoencoder (MSE anomaly)
│   │   ├── anomaly_ensemble.py                # Calibrated ensemble combiner (IF + AE)
│   │   ├── mesh_gnn_correlator.py             # PyTorch Mesh Graph Neural Network (neighborhood aggregation)
│   │   └── lstm_forecaster.py                 # PyTorch recurrent sequence forecaster & Time-to-Critical solver
│   │
│   ├── pipeline/                              # Pipeline orchestration
│   │   ├── __init__.py
│   │   └── inference_pipeline.py              # Unified end-to-end inference orchestrator
│   │
│   ├── schemas/                               # Pydantic v2 data contracts
│   │   ├── __init__.py
│   │   ├── sensor_contracts.py                # SensorReading, NodeHealthMetadata, EngineeredFeatureVector
│   │   ├── risk_event_contracts.py            # RiskEvent, ForecastTrendEnum, ModelVersionMetadata
│   │   ├── gis_interop_contracts.py           # IngestionRasterPayload, RiskZoneFeatureCollection
│   │   ├── insar_contracts.py                 # InSARDiscrepancyMarker, InSAROverlayPayload
│   │   └── feedback_contracts.py              # OperatorFeedbackEvent, ModelRegistryEntry
│   │
│   └── tinyml_bridge/                         # Edge TinyML synchronization
│       ├── __init__.py
│       ├── distillation_exporter.py           # Teacher-to-student INT8 quantization exporter (<32 KB)
│       └── edge_reconciler.py                 # Cloud-edge inference reconciliation & drift monitor
│
├── tests/                                     # Automated test suite (34 tests)
│   ├── __init__.py
│   ├── test_anomaly_ensemble.py               # IF, AE, and Ensemble unit tests
│   ├── test_api_endpoints.py                  # FastAPI endpoint integration tests
│   ├── test_explainability.py                 # Confidence scorer and narrative generator tests
│   ├── test_feedback_loop.py                  # Online calibration, retraining, and registry rollback tests
│   ├── test_gis_integration.py                # GIS Layer 5 serialization and raster contract tests
│   ├── test_gnn_correlation.py                # Graph construction and neighborhood message passing tests
│   ├── test_ingestion_and_faults.py           # Windowing, feature extractor, and hardware fault rejection
│   ├── test_insar_cross_validation.py         # Sentinel-1 discrepancy detection tests
│   ├── test_kriging_interpolation.py          # Variogram modeling and Kriging grid interpolation tests
│   ├── test_lstm_forecasting.py               # Trend classification and Time-to-Critical estimation tests
│   ├── test_robustness_and_edge_cases.py      # Zero-node, empty mesh, collinear, heave, and edge tests
│   ├── test_sla_latency_benchmark.py          # Latency SLA verification (target <= 15s)
│   └── test_tinyml_bridge.py                  # Distillation export and drift reconciliation tests
│
├── pyproject.toml                             # Project build configuration & pytest metadata
├── requirements.txt                           # Python package dependencies
├── README.md                                  # Architectural overview & quickstart guide
├── docx_full_content.txt                      # Full text transcript of Technical Design Document v1.0
└── SubSense_AIML_Data_Inference_Layer_...docx # Source Technical Design Document (.docx)
```

---

## 4. In-Depth Sub-Module Analysis

### 4.1 Ingestion & Sensor-Fault Filtering (`src/ingestion/`)
- **`fault_filter.py` (`SensorFaultFilter`)**:
  - Implements **Section 3.3 (Data Quality & Sensor-Fault Filtering)**.
  - Prevents physical and electronic failure modes from generating false alarms:
    1. **Battery Brownout Rejection**: Nodes with voltage $< 2.4\text{ V}$ are quarantined (prevents ADC power-rail collapse spikes).
    2. **Degraded RF Link Filter**: Packets with $\text{RSSI} < -115\text{ dBm}$ are dropped to avoid corrupted payloads.
    3. **Hardware Flatline Detection**: Detects frozen sensor ADCs where variance across tilt and vibration falls below $10^{-6}$.
    4. **Physical Limits Validation**: Rejects impossible values (tilt $> 85^\circ$, displacement $<-50\text{ mm}$ or $>5000\text{ mm}$).
    5. **Quarantine Routing**: Flagged nodes are bypassed from inference and routed to the mesh self-health/predictive maintenance queue.
- **`feature_extractor.py` (`FeatureExtractor`)**:
  - Implements **Section 3.2 (Windowing & Feature Extraction)**.
  - Extracts 8 physical and statistical features from sliding windows:
    - `tilt_mean`: Window average inclination ($\theta$).
    - `tilt_rate`: Rate of angular change ($\Delta\theta/\Delta t$).
    - `tilt_var_short`: High-frequency variance over the last 10 samples.
    - `tilt_var_long`: Full-window variance (baseline stability).
    - `vibration_rms`: Micro-seismic energy amplitude ($\sqrt{\frac{1}{N}\sum g_i^2}$).
    - `vibration_peak_ratio`: Peak-to-RMS ratio for impact/rockburst identification.
    - `displacement_delta`: Surface displacement relative to baseline ($\Delta S$).
    - `displacement_cum_drift`: Cumulative path length of deformation drift.
    - `crack_active_ratio`: Duty cycle of binary crack gauge tripping.
- **`window_buffer.py` (`SlidingWindowBuffer`)**:
  - Ring buffer retaining up to 60 temporal samples per sensor node with configurable minimum sample readiness thresholds (15 samples).

---

### 4.2 Unsupervised Anomaly Detection Ensemble (`src/models/`)
- **`isolation_forest_detector.py` (`IsolationForestAnomalyDetector`)**:
  - Fast, non-parametric tree ensemble (Scikit-Learn).
  - Isolates observations through recursive random partitioning.
  - Uses smooth sigmoidal mapping around the 5th percentile training decision function to output bounded continuous scores in $[0.0, 1.0]$.
- **`autoencoder_detector.py` (`PyTorchAutoencoderDetector`)**:
  - Deep PyTorch bottleneck neural network:
    $$\text{Encoder: } 8 \to 16 \to 8 \to 3 \quad\Big|\quad \text{Decoder: } 3 \to 8 \to 16 \to 8$$
  - Trained solely on normal ground baseline windows using Adam and MSE loss.
  - Computes per-sample reconstruction MSE; maps reconstruction loss exceeding the 95th percentile baseline through an exponential decay mapping to $[0.0, 1.0]$.
- **`anomaly_ensemble.py` (`AnomalyDetectionEnsemble`)**:
  - Implements **Section 4 (Unsupervised Anomaly Detection)**.
  - Fuses both detectors using calibrated weighting:
    $$\text{anomaly\_score} = 0.45 \times \text{score}_{\text{IF}} + 0.55 \times \text{score}_{\text{AE}}$$
  - Computes **model agreement** ($1.0 - |\text{score}_{\text{IF}} - \text{score}_{\text{AE}}|$), directly feeding the downstream confidence scoring engine.

---

### 4.3 Graph-Based Spatial Correlation via Mesh GNN (`src/models/mesh_gnn_correlator.py`)
- Implements **Section 5 (Graph-Based Spatial Correlation)**.
- **Graph Topology Construction**:
  - Nodes = physical sensors deployed above the coal extraction panel.
  - Edges = Euclidean distance within spatial interaction radius ($R \le 150\text{ m}$).
  - Edge weights computed via Gaussian Radial Basis Function (RBF):
    $$w_{ij} = \exp\left(-\frac{d_{ij}^2}{2\sigma^2}\right), \quad \sigma = \frac{R}{2}$$
  - Symmetrically normalized adjacency matrix $\mathbf{\tilde{A}} = \mathbf{\tilde{D}}^{-1/2} (\mathbf{A} + \mathbf{I}) \mathbf{\tilde{D}}^{-1/2}$.
- **GNN Neural Architecture (`MeshSpatialGNN`)**:
  - 2-layer spectral Graph Convolutional Network (GCN):
    $$\mathbf{H}^{(1)} = \text{ReLU}\left(\mathbf{\tilde{A}} \mathbf{X} \mathbf{W}_1\right), \quad \mathbf{H}^{(2)} = \text{ReLU}\left(\mathbf{\tilde{A}} \mathbf{H}^{(1)} \mathbf{W}_2\right)$$
  - Input features: 9D vector per node (8 engineered features + calibrated anomaly score).
  - Hidden dimensions: $9 \to 16 \to 8 \to 1$ with Sigmoid projection.
- **Neighborhood Corroboration & False-Alarm Suppression**:
  - Identifies candidate risk zones via NetworkX connected component subgraphs.
  - **Isolated Node Discounting**: A single isolated elevated node is penalized by $55\%$ ($0.45\times$), drastically reducing single-node false alarms.
  - **Multi-Node Coherence Boost**: Multi-node clusters receive a spatial coherence bonus up to $1.3\times$, elevating genuine ground subsidence basins.

---

### 4.4 Progression Forecasting & Time-to-Critical (TTC) (`src/models/lstm_forecaster.py`)
- Implements **Section 6.1 (LSTM Progression Forecasting)** & **Section 6.3 (Time-to-Critical Estimation)**.
- **Network Architecture (`LSTMDeformationNet`)**:
  - PyTorch recurrent model: 2-layer LSTM ($4 \to 32$) with fully-connected projection ($32 \to 16 \to 2$).
  - Inputs: Temporal sequence $[T, 4]$ ($\text{tilt}, \text{vibration\_rms}, \text{displacement}, \text{anomaly\_score}$).
  - Outputs: Predicted deformation velocity ($v_{\text{pred}}$) and acceleration ($a_{\text{pred}}$).
- **Hybrid Physical-Neural Kinematics**:
  - Fuses finite-difference numerical derivatives ($70\%$) with neural predictions ($30\%$).
  - Guardrail: If measured displacement is flat ($<0.02\text{ mm/hr}$), neural bias is suppressed to prevent phantom acceleration.
- **4-Tier Trend Classification**:
  - `stable`: Velocity $\le 0.05\text{ mm/hr}$ and zero acceleration.
  - `slow_progression`: Velocity $> 0.05\text{ mm/hr}$, creeping strain.
  - `accelerating`: Positive acceleration ($> 0.05\text{ mm/hr}^2$) and velocity $> 0.15\text{ mm/hr}$.
  - `sudden_onset`: Rapid velocity spike ($> 5.0\text{ mm/hr}$) or tilt swing $> 2^\circ$.
- **Time-to-Critical Solver**:
  - Solves the second-order geomechanical kinematic equation for remaining displacement $\Delta S = S_{\text{crit}} - S_{\text{current}}$:
    $$\Delta S = v_0 t + \frac{1}{2} a t^2 \implies t_{\text{hours}} = \frac{-v_0 + \sqrt{v_0^2 + 2 a \Delta S}}{a}$$
  - **Specification Compliance (Section 6.3)**: When trend is `stable`, `time_to_critical_hours` returns `null` rather than generating spurious predictions.

---

### 4.5 Ordinary Kriging Geostatistical Interpolation (`src/geostats/`)
- Implements **Section 6.2 (Kriging Spatial Interpolation)**.
- **Theoretical Semivariogram (`variogram.py`)**:
  - Models spatial autocorrelation:
    $$\text{Exponential: } \gamma(h) = c_0 + c \left[1 - \exp\left(-\frac{3h}{a}\right)\right]$$
    $$\text{Spherical: } \gamma(h) = c_0 + c \left[1.5 \left(\frac{h}{a}\right) - 0.5 \left(\frac{h}{a}\right)^3\right]$$
  - Bins empirical semivariances $\hat{\gamma}(h) = \frac{1}{2N(h)} \sum (Z_i - Z_j)^2$ and fits optimal parameters ($c_0 = \text{nugget}$, $c = \text{sill}$, $a = \text{range}$) using Levenberg-Marquardt curve fitting.
- **Ordinary Kriging Interpolator (`ordinary_kriging.py`)**:
  - Solves the Best Linear Unbiased Estimator (BLUE) Kriging system with Lagrange multiplier $\mu$:
    $$\begin{bmatrix} \mathbf{\Gamma} & \mathbf{1} \\ \mathbf{1}^T & 0 \end{bmatrix} \begin{bmatrix} \mathbf{\lambda} \\ \mu \end{bmatrix} = \begin{bmatrix} \mathbf{\gamma}_0 \\ 1 \end{bmatrix}$$
  - Generates continuous 2D estimated risk values $\hat{Z}(x_0) = \sum \lambda_i Z_i \in [0.0, 1.0]$.
  - Calculates **Kriging Estimation Variance** at every grid coordinate:
    $$\sigma_K^2(x_0) = \sum \lambda_i \gamma(x_i - x_0) + \mu$$
  - Directly feeds **GIS Layer 5** to modulate heatmap opacity based on statistical uncertainty.

---

### 4.6 Explainability & Confidence Scoring (`src/explainability/`)
- Implements **Section 7 (Confidence Scoring & Explainability)**.
- **`confidence_scorer.py` (`ConfidenceScorer`)**:
  - Synthesizes multi-factor evidence into a continuous score $[0.05, 0.99]$:
    $$\text{Confidence} = 0.35 \times \text{Agreement}_{\text{Ensemble}} + 0.40 \times \text{Score}_{\text{GNN}} + 0.25 \times \min\left(1.0, \frac{\log_2(1 + N)}{2}\right)$$
  - High corroboration across both models and multiple adjacent nodes yields $>0.85$ confidence.
- **`narrative_generator.py` (`ExplainabilityNarrativeGenerator`)**:
  - Generates 100% deterministic, auditable explanations strictly derived from model features.
  - Eliminates LLM hallucinations and adheres to DGMS regulatory requirements.
  - *Example Output*:
    > *"Correlated tilt and vibration and crack rise across 3 adjacent nodes (N-014, N-015, N-021); GNN correlation score 0.76. Progression accelerating. Estimated time-to-critical: 36.5 hours."*

---

### 4.7 Closed-Loop Feedback & Retraining (`src/feedback_loop/`)
- Implements **Section 8 (Model Training, Retraining & the Feedback Loop)**.
- **Short-Term Fast Adaptation (`online_calibrator.py`)**:
  - Responds immediately to operator false-alarm feedback without triggering full retraining.
  - Nudges per-site thresholds ($+0.03$ on false alarm, $-0.01$ on confirmed subsidence) capped at $\pm 0.15$.
- **Automated Retraining Orchestration (`retraining_orchestrator.py`)**:
  - Triggers on accumulated feedback volume (default: 30–50 events) or weekly cron schedule.
  - Retrains the ensemble, computes holdout validation metrics (Precision, Recall, F1), and automatically promotes candidate models if performance standards are met.
- **Model Registry & Rollback (`model_registry.py`)**:
  - Stores all active and historical model versions (`cloud-ensemble-v2.1.0`, `gnn-corr-v1.4.0`, etc.).
  - Preserves full auditability and enables one-click rollback if new versions exhibit drift.

---

### 4.8 TinyML Edge Distillation Bridge (`src/tinyml_bridge/`)
- Implements **Section 9 (Integration with the TinyML Edge Layer)**.
- **`distillation_exporter.py` (`TinyMLDistillationExporter`)**:
  - Performs INT8 symmetric weight quantization on cloud teacher autoencoder models:
    $$\text{Scale} = \frac{\max(|W|)}{127}, \quad W_{\text{INT8}} = \text{round}\left(\frac{W}{\text{Scale}}\right)$$
  - Verifies total model footprint is $< 32\text{ KB}$ for resource-constrained ARM Cortex-M4 and ESP32 microcontrollers.
- **`edge_reconciler.py` (`EdgeCloudReconciler`)**:
  - Reconciles buffered edge alerts backfilled upon mesh reconnection against cloud inference.
  - Automatically raises a model drift alert if 5 consecutive edge-cloud disagreements occur.

---

### 4.9 Satellite InSAR Macro-Cross Validation (`src/insar/`)
- Implements **Section 2, 7 & 11 (Satellite InSAR Data Fusion)**.
- **`insar_cross_validator.py` (`InSARCrossValidator`)**:
  - Ingests Sentinel-1 Line-of-Sight (LOS) deformation velocity rasters ($\text{mm/year}$).
  - Detects two critical geodetic discrepancy types:
    1. `satellite_motion_unmonitored_by_ground_mesh`: Sentinel-1 observes subsidence ($< -18\text{ mm/yr}$) beyond the ground mesh boundary. Flags the need for ground mesh expansion.
    2. `sensor_satellite_velocity_mismatch`: Ground sensors indicate critical strain ($>0.75$) but satellite LOS velocity is neutral. Triggers verification of underground void depth or atmospheric noise.

---

## 5. Formal Inter-Layer Data Contracts

### 5.1 Output to Alerting System (Layer 6) — Section 10 Risk Event Contract
Standardized JSON payload published to the message queue (`risk-events` topic) consumed by the Alerting System:

```json
{
  "site_id": "SITE-JHARIA-04",
  "zone_id": "PANEL-7-ZONE-01",
  "node_ids": ["N-014", "N-015", "N-021"],
  "anomaly_score": 0.81,
  "correlation_score": 0.76,
  "forecast_trend": "accelerating",
  "time_to_critical_hours": 36.5,
  "confidence_score": 0.87,
  "contributing_sensors": ["tilt", "vibration", "crack"],
  "explanation_text": "Correlated tilt and vibration and crack rise across 3 adjacent nodes (N-014, N-015, N-021); GNN correlation score 0.76. Progression accelerating. Estimated time-to-critical: 36.5 hours.",
  "model_versions": {
    "anomaly": "cloud-ensemble-v2.1.0",
    "correlation": "gnn-corr-v1.4.0",
    "forecast": "lstm-forecast-v1.2.0"
  },
  "event_timestamp": "2026-09-10T11:15:00Z"
}
```

### 5.2 Output to GIS & Digital Twin (Layer 5) — IngestionRasterPayload
Continuous 2D geostatistical surface payload ingested by `heatmap_contracts.py` in Layer 5:

```json
{
  "site_id": "SITE-JHARIA-04",
  "timestamp": "2026-09-10T11:15:00Z",
  "grid_width": 51,
  "grid_height": 51,
  "bounds_utm": [442000.0, 2631200.0, 443000.0, 2632200.0],
  "utm_epsg": 32645,
  "risk_values": [[0.12, 0.15, "..."], ["..."]],
  "variance_values": [[0.04, 0.05, "..."], ["..."]],
  "gateway_sync_age_seconds": 1.2
}
```

### 5.3 Closed-Loop Operator Feedback Contract — OperatorFeedbackEvent
Consumes operator validation events from the Alerting System (`alert-feedback` topic):

```json
{
  "feedback_id": "FB-20260910-001",
  "alert_id": "ALERT-JHARIA-7712",
  "site_id": "SITE-JHARIA-04",
  "zone_id": "PANEL-7-ZONE-01",
  "operator_id": "OP-GEOTECH-09",
  "feedback_type": "false_positive",
  "geotechnical_notes": "Surface vibration caused by controlled open-cast blasting in adjacent pit.",
  "timestamp": "2026-09-10T11:20:00Z"
}
```

---

## 6. REST API Endpoints & Interfaces

The service exposes a high-performance FastAPI interface documented below:

| Method | Endpoint | Description | Request Body / Parameters | Response Type |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/inference/run` | Executes complete inference cycle over telemetry batch | `InferenceBatchRequest` | `InferenceCycleResponse` |
| `GET`  | `/api/v1/inference/health` | Service health, SLA latency target, and active models | None | `HealthResponse` |
| `POST` | `/api/v1/kriging/surface` | Generates continuous 2D Kriging risk & variance raster | `KrigingRequest` | `IngestionRasterPayload` |
| `POST` | `/api/v1/insar/cross-validate` | Cross-validates Sentinel-1 grids against ground mesh | `InSARValidationRequest` | `InSAROverlayPayload` |
| `POST` | `/api/v1/feedback/submit` | Ingests operator feedback; triggers short-term calibration | `OperatorFeedbackEvent` | Feedback processing summary |
| `POST` | `/api/v1/feedback/retrain/trigger` | Triggers on-demand retraining cycle on accumulated data | None | Retraining metrics & status |
| `GET`  | `/api/v1/feedback/models/registry` | Lists all model versions, active states, and audit metrics | None | `List[ModelRegistryEntry]` |
| `POST` | `/api/v1/feedback/models/rollback` | Rolls back an active model family to an earlier version | `RollbackRequest` | Rollback status & versions |
| `GET`  | `/` | Service root and registered endpoint directory | None | Service directory |

---

## 7. Automated Test Suite & Benchmark Results

The codebase includes an extensive suite of **34 automated pytest tests** covering unit behavior, inter-layer contracts, numerical stability, edge cases, and end-to-end SLA benchmarks.

```bash
# Command to execute full test suite
pytest tests/ -v
```

### Verified Benchmark Performance Targets (Section 11, Table 3):

| Evaluation Dimension | Requirement / Benchmark | Observed Test Result | Pass / Fail |
| :--- | :--- | :--- | :--- |
| **Test Suite Pass Rate** | 100% test pass rate across all modules | **34 passed in 17.62 s** | **PASSED** |
| **Inference Latency SLA** | End-to-end cycle $\le 15.0\text{ s}$ | **$\sim 0.045\text{ s}$ ($>330\times$ headroom)** | **PASSED** |
| **Explainability Coverage** | 100% non-null confidence & explanation | **100% compliant, zero empty fields** | **PASSED** |
| **Sensor Fault Rejection** | Rejects flatline, $<2.4\text{V}$, RF loss | **100% quarantined with audit reasons** | **PASSED** |
| **Spatial Correlation (GNN)**| Multi-node cluster detection vs. single spike | **Single spikes discounted 55%; clusters boosted** | **PASSED** |
| **Time-to-Critical (TTC)** | Kinematic countdown; null when stable | **Accurate quadratic solver; null on stable** | **PASSED** |
| **Kriging Stability** | Collinear & duplicate coordinates handled | **Ridge pinv regularized; zero NaN/Infs** | **PASSED** |
| **GIS Interoperability** | Valid `IngestionRasterPayload` serialization | **Zero-loss schema validation** | **PASSED** |
| **InSAR Fusion** | Identifies unmonitored basins & mismatches | **Generates GeoJSON & audit markers** | **PASSED** |
| **Closed-Loop Retraining** | Dynamic threshold nudge & version registry | **Verified threshold drift & rollback** | **PASSED** |
| **TinyML Quantization** | Model footprint $< 32\text{ KB}$ for microcontrollers | **Verified $< 5\text{ KB}$ INT8 bundle** | **PASSED** |

---

## 8. Operational Guide: Execution & Integration

### 8.1 Setup & Installation
```bash
# 1. Navigate to the AIML data inference folder
cd "c:\Users\sasik\Desktop\SIH 2026\Subsense\AIML data inference"

# 2. Install dependencies
pip install -r requirements.txt
```

### 8.2 Starting the FastAPI Serving Service
```bash
# Start the Uvicorn development server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation will be available at: `http://localhost:8000/docs`.

### 8.3 Running the Automated Test Suite
```bash
# Run pytest with detailed test execution logging
python -m pytest tests/ -v
```

---

## 9. Architectural Traceability Matrix

| Problem Statement Requirement | Implementing Module / File | Verification Test Module |
| :--- | :--- | :--- |
| **Unsupervised Anomaly Detection** | `src/models/anomaly_ensemble.py`, `src/models/isolation_forest_detector.py`, `src/models/autoencoder_detector.py` | `tests/test_anomaly_ensemble.py` |
| **Sensor Hardware Fault Rejection**| `src/ingestion/fault_filter.py` | `tests/test_ingestion_and_faults.py` |
| **Physical Feature Engineering** | `src/ingestion/feature_extractor.py` | `tests/test_ingestion_and_faults.py` |
| **Graph-Based Spatial Correlation** | `src/models/mesh_gnn_correlator.py` | `tests/test_gnn_correlation.py` |
| **Deformation Progression & TTC** | `src/models/lstm_forecaster.py` | `tests/test_lstm_forecasting.py` |
| **Continuous Kriging Risk Surface** | `src/geostats/ordinary_kriging.py`, `src/geostats/variogram.py` | `tests/test_kriging_interpolation.py` |
| **Explainability & Confidence** | `src/explainability/confidence_scorer.py`, `src/explainability/narrative_generator.py` | `tests/test_explainability.py` |
| **Satellite InSAR Macro Validation**| `src/insar/insar_cross_validator.py` | `tests/test_insar_cross_validation.py` |
| **Closed-Loop Feedback Retraining**| `src/feedback_loop/` | `tests/test_feedback_loop.py` |
| **TinyML Edge Model Distillation** | `src/tinyml_bridge/` | `tests/test_tinyml_bridge.py` |
| **GIS Layer 5 Interoperability** | `src/schemas/gis_interop_contracts.py` | `tests/test_gis_integration.py` |
| **Alerting Layer 6 Interop** | `src/schemas/risk_event_contracts.py` | `tests/test_api_endpoints.py` |
| **Sub-15s Latency SLA** | `src/pipeline/inference_pipeline.py` | `tests/test_sla_latency_benchmark.py` |
