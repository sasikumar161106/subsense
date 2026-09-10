# SubSense — AI/ML Data Inference Layer (Layer 4)

**Technical Specification Baseline**: `SubSense AI/ML Data Inference Layer Technical Design Document v1.0`  
**System Target**: Python 3.11+ / PyTorch 2.2+ / Scikit-Learn 1.4+ / FastAPI / SciPy Geostatistics / NetworkX  
**Compliance Standard**: DGMS Underground Coal Mine Subsidence Monitoring Guidelines  

---

## 1. System Overview

The **AI/ML Data Inference Layer (Layer 4)** is the analytical intelligence core of the **SubSense Smart Mine Subsidence Platform**. Positioned directly between raw telemetry ingestion (Time-Series DB / LoRaWAN Mesh Gateway) and the downstream operational subsystems (**GIS & Digital Twin Layer 5** and **Alerting System Layer 6**), Layer 4 transforms raw multi-sensor telemetry into explainable, continuous, and predictive **Risk Events**.

Layer 4 fuses physical kinematics, unsupervised machine learning, graph-based spatial correlation over the wireless mesh, deep sequence forecasting, and geostatistical Kriging interpolation into a unified, high-reliability pipeline that satisfies the strict $\le 15\text{--}20\text{ s}$ inference SLA.

---

## 2. Architecture & Pipeline Data Flow

```
 +---------------------------------------------------------------------------------------+
 |                            UPSTREAM: GATEWAY & SENSOR MESH                            |
 |  Tilt, Vibration, Displacement, Crack Sensors + Node Health (Battery, RSSI, Status)   |
 +-------------------------------------------+-------------------------------------------+
                                             |
                                             v
 +---------------------------------------------------------------------------------------+
 |                     LAYER 4: DATA INGESTION & FEATURE ENGINEERING                     |
 |  1. Sliding Windowing & Aggregation (Mean, Tilt Rate, Vibration RMS, Drift, Crack)  |
 |  2. Hardware Fault & Sensor Glitch Filtering (Flatline, Low Battery Rejection)        |
 +-------------------------------------------+-------------------------------------------+
                                             | Validated Feature Windows
                                             v
 +---------------------------------------------------------------------------------------+
 |                     UNSUPERVISED ANOMALY ENSEMBLE (SECTION 4)                         |
 |  - Isolation Forest (Scikit-Learn) + Deep Autoencoder (PyTorch)                       |
 |  - Outputs calibrated per-node anomaly_score in [0.0, 1.0]                            |
 +-------------------------------------------+-------------------------------------------+
                                             | Node Anomaly Scores + Graph Edges
                                             v
 +---------------------------------------------------------------------------------------+
 |                    GRAPH-BASED SPATIAL CORRELATION (SECTION 5)                        |
 |  - PyTorch Mesh GNN: Node features + Spatial Proximity Adjacency Graph               |
 |  - Aggregates neighborhood signals; filters isolated glitches                         |
 |  - Identifies Candidate Risk Zones, contributing_nodes, correlation_score in [0, 1]   |
 +---------------------+---------------------+---------------------+---------------------+
                       |                     |                     |
                       v                     v                     v
 +---------------------------+ +---------------------------+ +---------------------------+
 |   LSTM FORECASTING (6.1)  | |   KRIGING GEOSTATS (6.2)  | |   InSAR SATELLITE (7.0)   |
 | - Temporal progression    | | - Ordinary Kriging        | | - Sentinel-1 macro cross- |
 | - Trend classification:   | | - Semivariogram fit       | |   validation              |
 |   stable, slow,           | | - Continuous risk surface | | - Macro discrepancy basin |
 |   accelerating, sudden    | | - Estimation variance     | |   callout markers         |
 | - time_to_critical_hours  | |   confidence mask         | |                           |
 +---------------------------+ +---------------------------+ +---------------------------+
                       |                     |                     |
                       +---------------------+---------------------+
                                             v
 +---------------------------------------------------------------------------------------+
 |                   CONFIDENCE SCORING & EXPLAINABILITY ENGINE (SECTION 7)              |
 |  - Multi-factor confidence calculation (Ensemble Agreement + GNN Correlation + Count) |
 |  - Templated natural language explanation text (Auditable, non-hallucinated)          |
 +-------------------------------------------+-------------------------------------------+
                                             v
 +---------------------------------------------------------------------------------------+
 |                           STRUCTURED RISK EVENT EMITTER (10)                          |
 |  - Versioned JSON matching Section 10 & Alerting Layer 6 Contract                     |
 |  - Kriging 2D Raster Payload matching GIS Layer 5 IngestionRasterPayload              |
 +-------------------------------------+-------------------------------------------------+
                                       |
                   +-------------------+-------------------+
                   v                                       v
 +-----------------------------------+   +-----------------------------------+
 |   GIS / DIGITAL TWIN (LAYER 5)    |   |     ALERTING SYSTEM (LAYER 6)     |
 | - Live Heatmap & Variance Mask    |   | - DGMS Severity Classification    |
 | - Dynamic Risk Zone Contours      |   | - SMS/WhatsApp/Push Dispatch      |
 | - InSAR Overlay & Discrepancies   |   | - Escalation & Evacuation Triggers|
 +-----------------------------------+   +-----------------+-----------------+
                                                           |
                                                           v Operator Feedback
 +---------------------------------------------------------------------------------------+
 |                     AUTOMATIC FALSE-ALARM LEARNING LOOP (SECTION 8)                   |
 |  - Consumes false-alarm / confirmed-positive feedback events                          |
 |  - Short-term: Dynamic per-site threshold & sensor weight tuning                      |
 |  - Long-term: Scheduled retraining of Autoencoder, Isolation Forest, GNN, & LSTM      |
 |  - Model Registry: Version tracking, audit logging, and rollback                      |
 +-------------------------------------------+-------------------------------------------+
                                             v
 +---------------------------------------------------------------------------------------+
 |                    TINYML EDGE DISTILLATION BRIDGE (SECTION 9)                        |
 |  - Cloud teacher-to-student model compression & quantization                          |
 |  - Edge vs. Cloud inference reconciliation & drift detection                          |
 +---------------------------------------------------------------------------------------+
```

---

## 3. Core Sub-Modules & Algorithms

### 3.1 Ingestion & Sensor-Fault Filtering (`src/ingestion`)
- **Sliding Window Buffer**: Ring buffer retaining fixed-duration windows (60 samples per node).
- **Feature Extraction**: Computes tilt rate ($\Delta\theta/\Delta t$), short/long tilt variance, vibration RMS amplitude, peak-to-RMS ratio, cumulative displacement drift, and crack sensor duty cycle.
- **Hardware Fault Rejection**: Automatically excludes flat-lined ADCs (zero variance), dead batteries ($< 2.4\text{ V}$), and degraded RF links ($< -115\text{ dBm}$) from entering inference, routing them to predictive maintenance.

### 3.2 Unsupervised Anomaly Detection Ensemble (`src/models`)
- **Isolation Forest**: Partitions feature space via random splits; rapidly flags point outliers.
- **Deep Autoencoder**: Multi-layer bottleneck neural network (PyTorch) trained to reconstruct normal ground behavior. Non-linear deformation drift triggers high reconstruction MSE.
- **Ensemble Scorer**: Combines both normalized models into a bounded `anomaly_score` $[0.0, 1.0]$ and computes model agreement.

### 3.3 Graph-Based Spatial Correlation via Mesh GNN (`src/models/mesh_gnn_correlator.py`)
- **Graph Topology**: Nodes = sensor nodes; Edges = proximity threshold ($R \le 150\text{ m}$) weighted by Gaussian radial basis kernel $w_{ij} = \exp(-d_{ij}^2 / 2\sigma^2)$.
- **Neighborhood Message Passing**: Corroborates adjacent node activations. An isolated sensor spike on 1 node is attenuated by 55%, while multi-node clusters receive a spatial coherence boost, isolating the `contributing_nodes` cluster and computing `correlation_score` $[0.0, 1.0]$.

### 3.4 LSTM Progression Forecasting & Time-to-Critical (`src/models/lstm_forecaster.py`)
- **Sequence Trajectory**: Models strain kinematics and recurrent sequence dynamics.
- **Trend Classification**: Classifies `forecast_trend` into `"stable"`, `"slow_progression"`, `"accelerating"`, or `"sudden_onset"`.
- **Time-to-Critical (TTC)**: Solves second-order kinematic equations to project hours remaining until critical displacement ($S_{\text{crit}}$). Stable zones return `null` per Section 6.3.

### 3.5 Ordinary Kriging Geostatistical Surface (`src/geostats`)
- **Semivariogram Fitting**: Fits spherical or exponential semivariograms $\gamma(h) = c_0 + c [1 - \exp(-3h/a)]$.
- **Continuous 2D Surface**: Solves the Kriging system $\mathbf{\Gamma} \mathbf{\lambda} = \mathbf{\gamma}_0$ with Lagrange multiplier $\mu$.
- **Estimation Variance**: Calculates $\sigma_K^2(x_0)$ at every grid point, directly powering Layer 5's opacity-modulated confidence mask.

### 3.6 Explainability & Confidence Engine (`src/explainability`)
- **Confidence Formulation**: Multi-factor synthesis of ensemble agreement, GNN correlation strength, and node count.
- **Auditable Templated Narrative**: Generates deterministic, non-hallucinated explanations:
  > *"Correlated tilt and vibration and crack rise across 3 adjacent nodes (N-014, N-015, N-021); GNN correlation score 0.76. Progression accelerating. Estimated time-to-critical: 36.5 hours."*

### 3.7 Closed-Loop Feedback & Retraining (`src/feedback_loop`)
- **Short-Term Fast Tuning**: Nudges per-site thresholds on operator false-positive feedback without full retraining.
- **Scheduled / On-Demand Retraining**: Retrains models on accumulated operator feedback and validates against holdout data before automated promotion.
- **Model Registry**: Full version auditability with rollback support (`cloud-ensemble-v2.1.0`, etc.).

### 3.8 TinyML Edge Bridge (`src/tinyml_bridge`)
- **Model Distillation & Quantization**: Converts PyTorch models into INT8-quantized weight manifests for edge microcontrollers ($< 32\text{ KB}$ footprint).
- **Cloud-Edge Reconciliation**: Reconciles backfilled edge alerts against cloud inferences to flag sensor drift.

---

## 4. Formal Inter-Layer Data Contracts

### 4.1 Output to Alerting System (Layer 6) — Section 10 Risk Event Contract
```json
{
  "site_id": "SITE-JHARIA-04",
  "zone_id": "PANEL-7-NE",
  "node_ids": ["N-014", "N-015", "N-021"],
  "anomaly_score": 0.81,
  "correlation_score": 0.76,
  "forecast_trend": "accelerating",
  "time_to_critical_hours": 36.5,
  "confidence_score": 0.87,
  "contributing_sensors": ["tilt", "vibration", "crack"],
  "explanation_text": "Correlated tilt and crack-sensor rise across 3 nodes.",
  "model_versions": {
    "anomaly": "cloud-ensemble-v2.1.0",
    "correlation": "gnn-corr-v1.4.0",
    "forecast": "lstm-forecast-v1.2.0"
  },
  "event_timestamp": "2026-09-09T05:10:02Z"
}
```

### 4.2 Output to GIS Layer 5 (`heatmap_contracts.py` & `risk_zone_contracts.py`)
- **`IngestionRasterPayload`**:
  - `site_id`: `"SITE-JHARIA-04"`
  - `bounds_utm`: `[min_x, min_y, max_x, max_y]`
  - `utm_epsg`: `32645`
  - `risk_values`: 2D continuous array $[0.0, 1.0]$
  - `variance_values`: 2D Kriging estimation variance array $\sigma_K^2$
  - `gateway_sync_age_seconds`: Elapsed time in seconds
- **`InSAROverlayPayload`**:
  - `markers`: List of `InSARDiscrepancyMarker` instances (unmonitored subsidence basins, velocity mismatches).

---

## 5. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/inference/run` | Executes full inference cycle over telemetry batch; returns Risk Events & Kriging raster |
| `GET`  | `/api/v1/inference/health` | Service health status, SLA target, and active model versions |
| `POST` | `/api/v1/kriging/surface` | Generates 2D Ordinary Kriging risk and variance raster for GIS Layer 5 |
| `POST` | `/api/v1/insar/cross-validate` | Cross-validates Sentinel-1 satellite grids against ground mesh |
| `POST` | `/api/v1/feedback/submit` | Ingests operator feedback (false positive / confirmed) and updates site calibration |
| `POST` | `/api/v1/feedback/retrain/trigger` | Triggers on-demand model retraining cycle |
| `GET`  | `/api/v1/feedback/models/registry` | Lists all registered model versions and validation metrics |
| `POST` | `/api/v1/feedback/models/rollback` | Rollbacks active model to an earlier validated version |

---

## 6. Verification & Automated Benchmark Results

The layer includes 34 automated tests across 13 test modules covering unit components, inter-layer contracts, edge cases, numerical stability, and end-to-end SLA benchmarks.

```bash
# Execute entire test suite
python -m pytest tests/ -v
```

### Verified Benchmark Performance Targets (Section 11, Table 3)
- **Automated Tests**: **34/34 passed** (100% pass rate, 0 warnings)
- **End-to-End Pipeline Latency**: **~0.045 s** (SLA Target $\le 15.0\text{ s}$: **PASSED** with $330\times$ headroom)
- **Explainability Coverage**: **100%** non-null confidence scores and auditable explanations (**PASSED**)
- **Data Contract Compatibility**: Zero-loss serialization into GIS Layer 5 `IngestionRasterPayload` and Alerting Layer 6 `RiskEvent` (**PASSED**)
- **Model Registry & Rollback**: 100% versioned traceability and automated rollback verified (**PASSED**)
- **Robustness & Edge-Case Guardrails**: Collinear/duplicate coordinates, isolated node discounting, negative velocity heave, empty meshes, and all-quarantined meshes verified (**PASSED**)
