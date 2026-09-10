# SubSense Layer 4: Production Verification Harness Report
**Report ID**: `VERIF-20260909-170721`  
**Generated**: `2026-09-09T17:07:21.791307+00:00`  
**Overall Status**: **`FULLY_PASSED`**  
**SHA-256 Signature**: `d0edbd2700aec9d398406c87b0230e8d183e59f756abbe601fc122989ee9606d`  

## Section 8 Target Verification Results

| Metric | Target | Measured | Status | Sample Size | Rationale / Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Recall | >=0.98 | 0.9800 | **PASSED** | 120 | Observed TP=49, FN=1 across 120 benchmark scenarios. |
| Precision | >=0.90 | 0.9245 | **PASSED** | 120 | Observed TP=49, FP=4 across 120 benchmark scenarios. |
| Warning lead time | >=8.0h | 10.5000 | **PASSED** | 15 | Median lead time 10.50h (min 8.7h, max 13.0h). |
| False alarm rate | <0.05 / node / month | 0.0333 | **PASSED** | 1800 | Observed 2 false alarms across 60.00 node-months of operation. |
| Packet delivery | >96.5% | 0.9780 | **PASSED** | 10000 | Delivered 9780/10000 mesh telemetry packets (97.80%). |
| Forecast calibration (ECE) | <0.08 | 0.0452 | **PASSED** | 48 | Conformal quantile calibration ECE measured at 0.0452 across 48h horizon. |
| Edge/cloud parity | >94.0% | 1.0000 | **PASSED** | 250 | Dual inference agreement within 5% tolerance: 100.00%. |

## Summary Counts
- **Passed**: 7
- **Failed**: 0
- **Insufficient Data**: 0

> **Regulatory Compliance Notice**: This report was generated automatically by the SubSense Section 8 Verification Harness. All unmeasured or data-limited metrics are explicitly documented without silent rounding or artificial inflation.