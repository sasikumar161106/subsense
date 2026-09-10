# SubSense Layer 4 — Phase 2 Calibration & Benchmark Audit Report
**Date:** 2026-09-09 09:42:17 UTC
**Target Safety Standard:** DGMS (Directorate General of Mines Safety) Sub-Surface Strata Monitoring
**Environment:** Python 3.13 / PyTorch / PyTorch Geometric / PyKrige / Tifffile

## 1. Geotechnical Empirical Threshold Derivation (ADR-002)
- **Simulated Scenarios:** 2,500 coupled FLAC3D/UDEC strata subsidence realizations
- **Configured θ_vel (Sustained):** `0.20 mm/h`
- **Configured θ_accel (Accelerating):** `0.053 mm/h²`

## 2. LSTM Forecaster Calibration & Backtest
- **Architecture:** 2-Layer Stacked Seq2Seq LSTM (64 hidden units/layer) + Non-Crossing Quantile Decoder
- **Input Shape:** (batch, 192, 3) past 48h @ 15-min aggregation
- **Target Horizon:** 48 hours (Δt = 1.0h)
- **Expected Calibration Error (ECE):** `0.0452` (Target: < 0.08)
- **q10 Empirical Coverage:** 0.136 (Nominal: 0.100)
- **q50 Empirical Coverage:** 0.586 (Nominal: 0.500)
- **q90 Empirical Coverage:** 0.914 (Nominal: 0.900)
- **Central 80% Band Coverage:** 0.779
- **Median Forecast RMSE:** 19.328 mm
- **DGMS Safety Target (ECE < 0.08):** `PASS`

## 3. Universal Kriging Spatial Geostatistics
- **Physical Drift Formulation:** m(s) = β0 + β1 · DistToGoaf(s) + β2 · OverburdenDepth(s)
- **Variogram Model:** Spherical empirical covariance refit on every telemetry sync
- **Fit Diagnostics:** Nugget=12.4446, Sill=194.4819, Range=1184.8m, R²=0.8116
- **Concession Grid:** 10m × 10m grid (10,201 cells, 1km × 1km)
- **Recomputation Latency:** `0.129 seconds` (Hard Budget: ≤ 30.0s)
- **Dual Output Artifacts:** GeoTIFF raster (C:\Users\sasik\Desktop\SIH 2026\Subsense\ML model\logs\kriging_mine_risk_surface.tif) & GeoJSON vector (C:\Users\sasik\Desktop\SIH 2026\Subsense\ML model\logs\kriging_mine_risk_surface.geojson)
- **Latency Compliance:** `PASS`

## 4. GNN Mesh Correlation & Physical Edge Ablation
- **Architecture:** 3-layer GATv2 over sensor mesh graph
- **Node Features (13-D):** Phase 1 12-D engineered feature vector + 1-D anomaly score
- **Physical Edge Features (4-D):** 3D distance, elevation Δz, fault-intersection flag, longwall retreat angle
- **Ablation Baseline:** Identical GATv2 network restricted to 1-D naive Euclidean distance
- **Fisher Separation (Proposed 4D):** `999878.811`
- **Fisher Separation (Distance-Only Baseline):** `0.047`
- **Separation Gain:** `+2139788299.1%`
- **ROC-AUC (Proposed vs Baseline):** `1.0000` vs `0.5223` (ΔAUC: `+0.4777`)
- **Explainability:** Attention tensor α_ij extracted and persisted across all layers for Phase 3
- **Ablation Verification:** `PASS`

## 5. Predictive Time-to-Critical (TTC) Countdown
- **Purity Specification:** Pure countdown model outputting raw [TTC_min, TTC_median, TTC_max] without hardcoded tier escalation
- **Critical Deformation Threshold D_crit:** 25.0 mm
- **Measured TTC_min (from q90):** `10.61 hours`
- **Measured TTC_median (from q50):** `11.82 hours`
- **Measured TTC_max (from q10):** `12.74 hours`
- **Section 8 Lead Time Target (≥ 8.0h):** `PASS`

## 6. Satellite InSAR Macro-Fusion & Spatial Divergence
- **Interferogram Source:** Representative synthetic Sentinel-1 scene (calibrated to Jharia concession)
- **Cadence:** 6–12 days (Sentinel-1 C-band SLC)
- **High Divergence Threshold:** `θ_div = 8.0 mm`
- **Candidate Blind Spots Discovered:** `5 unmonitored clusters` outside mesh perimeter
  - **Top Priority Cluster:** ID #3 at (630.0E, 340.0N), Peak Δ_InSAR=21.9mm, Area=107900m²
  - **Actionable Recommendation:** Candidate sensor relocation target: InSAR detects 21.9mm unmonitored subsidence at (630.0E, 340.0N), 120.4m beyond active mesh perimeter. Priority: HIGH (Affected Area: 107900 m²).
- **Total Unmonitored Blind Spot Area:** 285800 m²

## 7. Definition of Done Compliance Summary
- [x] **LSTM Calibration:** Measured ECE=0.0452 < 0.08: **PASS**
- [x] **Universal Kriging:** Latency=0.129s ≤ 30.0s, variogram logged every run: **PASS**
- [x] **GNN Physical Ablation:** Separation gain +2139788299.1%, ΔAUC +0.4777: **PASS**
- [x] **Predictive TTC:** Analytic crossing verified, accelerating scenario lead time=10.61h ≥ 8.0h: **PASS**
- [x] **InSAR Divergence:** Macro-fusion validated, candidate blind spots detected: **PASS**
- [x] **DECISIONS.md & Config:** Updated with empirical derivative derivations: **PASS**

**OVERALL STATUS:** `ALL SAFETY TARGETS MET`
