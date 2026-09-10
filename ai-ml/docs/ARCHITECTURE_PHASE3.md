# SubSense Layer 4: Phase 3 Architecture Specification
**Document ID**: `SUBSENSE-ARCH-L4-PHASE3`  
**Standard**: DGMS Circular 02 / CMR 2017 Life-Safety Compliance  
**Status**: Approved Production Standard  

---

## 1. System Architecture Overview

Phase 3 establishes the **Multi-Source Evidence Fusion, Explainability, Active Learning, and Regulatory Governance Layer** of SubSense Layer 4. It unifies the ten independent sensory and deep intelligence streams into an auditable, deterministic life-safety alerting engine.

```mermaid
flowchart TD
    subgraph Phase 1: Edge & Telemetry Foundation
        M1[Raw MQTT Sensor Ingestion] --> M2[Streaming Feature Pipeline 12-D]
        M1 --> M3[QoS & Mesh Telemetry Tracker Q_mesh]
        M2 --> M4[Per-Node Anomaly Ensemble IF + AE]
        M4 --> M5[Spatial-Temporal Cross-Correlation C_corr]
        M1 --> M_EDGE[C++ TinyML Edge Firmware Fail-Safe]
    end

    subgraph Phase 2: Spatio-Temporal Intelligence
        M2 --> M6[Universal Kriging with Physical Drift]
        M2 --> M7[GNN Mesh Fracture Correlation GATv2]
        M2 --> M8[Quantile Seq2Seq LSTM Forecaster]
        M8 --> M9[Kinematic Trend & Pure TTC Countdown]
        M6 --> M10[InSAR Sentinel-1 Spatial Divergence]
    end

    subgraph Phase 3: Fusion, Explainability & Governance
        M4 & M5 & M3 & M7 & M9 & M10 --> F1[Multi-Source Evidence Fusion Engine]
        F1 --> F2[Adaptive Entropy-Weighted Spatial Blending]
        F1 --> F3[Composite Confidence Scoring w1, w2, w3]
        F1 --> F4[TreeSHAP & GAT Attention Explainability]
        F4 --> F5{Explainability Gatekeeper}
        F5 -- Verified Alert --> F6[Siren & Conveyor Cutoff Dispatch]
        F6 --> F7[Cryptographic DGMS Audit Ledger]
    end

    subgraph Feedback Loop
        F6 --> FB1[4-Class Operator Adjudication Portal]
        FB1 --> FB2[Negative Sample Mining Repository]
        FB2 --> FB3[Weekly Airflow Retraining DAG]
        FB3 --> FB4{Model Promotion Gate}
        FB4 -- Promoted --> M4 & M7
    end
```

---

## 2. Multi-Source Evidence Fusion Engine (ADR-005)

The decision engine is implemented as an **explicit, deterministic boolean rules engine** (`fusion.decision_engine.FusionDecisionEngine`). It forbids black-box classifiers from triggering evacuations.

### Formal Boolean Decision Logic

#### 1. CRITICAL Tier
Triggers sirens, conveyor cutoff, zone evacuation, and Level 3 DGMS emergency audits:
$$\text{CRITICAL} \iff (\text{WarningConditions} \land \text{TTC}_{median} \le 12.0\text{h} \land \text{LSTM} == \text{ACCELERATING}) \lor (\text{TTC}_{median} < 8.0\text{h}) \lor (|\Delta\text{displacement}| > 10.0\text{mm})$$

- **Override C1**: $\text{WarningConditions} \land \text{TTC}_{median} \le 12.0\text{h} \land (\text{LSTM} == \text{ACCELERATING} \lor d^2\hat{y}/dt^2 \ge 0.050\text{ mm/h}^2)$.
- **Override C2 (Life-Safety Override)**: $\text{TTC}_{median} < 8.0\text{h}$ unconditionally triggers CRITICAL, regardless of any other sensory signals.
- **Override C3 (Dynamic Shear Fail-Safe)**: Instantaneous displacement jump $> 10.0\text{ mm}$ unconditionally triggers CRITICAL.

#### 2. WARNING Tier
Dispatches SMS/Telegram alerts to the resident geotechnical manager, inspection dispatches, and Level 2 DGMS audit tracking:
$$\text{WARNING} \iff (S_{node} \ge 0.75 \text{ across } \ge 2\text{ channels}) \land (C_{corr} \ge 0.70 \text{ at } \le 120\text{m}) \land (R_{GNN} \ge 0.70) \land (\text{LSTM} == \text{SUSTAINED})$$

#### 3. ADVISORY Tier
Emits dashboard notices, node health pings, and Level 1 audit logs:
$$\text{ADVISORY} \iff (S_{node} > 0.65) \land (\text{is\_single\_sensor\_uncorroborated}) \land (\text{LSTM} == \text{STABLE}) \land (\text{Confidence} < 0.60)$$

---

## 3. Spatial Risk-Surface Blending

Isotropic Universal Kriging provides continuous surface estimation but smooths out directional fracture steps. The 3-layer GATv2 model captures anisotropic shear channeling along fault interfaces.

SubSense blends them dynamically via the **Adaptive Entropy-Weighted Blender** (`fusion.spatial_blend.AdaptiveSpatialBlender`):
$$Z_{blended}(x, y) = (1 - w_{GNN}(x, y)) \cdot Z_{krig}(x, y) + w_{GNN}(x, y) \cdot Z_{GNN}(x, y)$$

Where $w_{GNN}(x, y) \in [w_{min}, w_{max}]$ scales with the local spatial covariance gradient $|\nabla Z(x, y)|$, Kriging variance $\sigma_{krig}^2$, and local discontinuity index:
$$w_{GNN}(x, y) = w_{min} + (w_{max} - w_{min}) \cdot \text{clip}\left(\tanh\left(\gamma \cdot \frac{|\nabla Z|}{\theta_{grad}}\right) + 0.25 \cdot \frac{\sigma_{krig}^2}{\bar{\sigma}^2} + 0.15 \cdot \frac{\text{std}_{local}(\nabla Z)}{\text{mean}_{local}(\nabla Z)}, 0.0, 1.0\right)$$

- In uniform, continuous flexure zones: $w_{GNN} \approx 0.10 - 0.25$, Kriging dominates.
- In shear steps and fracture lines: $w_{GNN} \approx 0.75 - 0.90$, shifting weight toward the GNN.

---

## 4. Composite Confidence Scoring (ADR-006)

$$\text{Confidence} = w_1 \cdot \text{Agreement}(\text{IsoForest}, \text{LSTM}, \text{GNN}) + w_2 \cdot C_{corr} + w_3 \cdot Q_{mesh}$$

- **Defaults**: $w_1 = 0.50, w_2 = 0.30, w_3 = 0.20$ ($w_1 + w_2 + w_3 = 1.0$).
- **Inter-Model Agreement**: Combines normalized continuous dispersion of model risk estimates with binary multi-model elevation concordance.
- **Mesh QoS ($Q_{mesh}$)**: Evaluated directly from `ingestion.qos_tracker.QoSTracker`:
  $$Q_{mesh} = 0.60 \cdot \text{PDR} + 0.25 \cdot \frac{\text{Battery}\%}{100} + 0.15 \cdot \text{RSSI}_{norm}$$

---

## 5. Explainability Layer & Schema Validation Gate

1. **TreeSHAP**: Evaluates exact Shapley values on the 12-dimensional tabular feature vector for `MineIsolationForest`, mapping features to physical sensor modalities (`tilt_deg`, `displacement_mm`, `vibration_rms_mm_s`, `crack_index`).
2. **Top-$k$ GAT Attention Extraction**: Identifies corroborating neighbor nodes along physical fracture pathways with attention weights $\alpha_{ij}$.
3. **Structured Geotechnical Natural-Language Generator**:
   ```
   [TIER] WARNING (Zone 3B, Panel 7): Triggered by sustained tilt surge (+0.24° over 30 min) and differential displacement (+4.8 mm/hr) at Node SS-PANEL7-N042. Corroborated by high spatial attention (α=0.88) with adjacent nodes N041 and N044 along the active extraction face. InSAR macro-crosscheck confirms 12mm historical depression basin.
   ```
4. **Non-Negotiable Schema Validation Gate**:
   `explainability.alert_schema.validate_and_gate_alert()` enforces that **zero alerts** are published without:
   - Non-empty `contributing_sensors`
   - Non-empty `corroborating_node_ids`
   - Valid, structured `plain_language_summary`
   Any omission raises `IncompleteExplainabilityAlertError` immediately.

---

## 6. DGMS Compliance Ledger & Cryptographic Governance

- **Append-Only Hash-Chained Ledger**: Every threshold change is recorded in `logs/audit_ledger.json` with SHA-256 hash chaining ($H_k = \text{SHA256}(H_{k-1} \parallel \text{Payload}_k)$).
- **Multi-Party Sign-Off**: Threshold changes exceeding $15\%$ strictly require $\ge 2$ distinct authorized signatories in code (`MissingSignOffException`).
- **Tamper Detection**: `verify_chain_integrity()` recalculates every link from the genesis block and raises `LedgerTamperDetectedException` on any byte mutation.
