# SubSense TinyML — Model Performance & Efficiency Evaluation System

A standalone, reproducible PC-based evaluation and benchmarking pipeline for the pre-trained **SubSense TinyML Models** (Node-Tier and Gateway-Tier) designed for real-time subsidence monitoring in underground coal mines.

---

## Architecture Overview

1. **Node-Tier Detector (`models/node_model_int8.tflite` / `firmware/subsense_node_model.h`)**:
   - Ultra-compact, asymmetric high-recall detector optimized for ESP32/ESP32-C3 sensor nodes.
   - Constraint: $\le 200\text{ KB Flash}$, $\le 500\text{ ms latency}$, $\ge 95\%\text{ recall}$ (100% on catastrophic sudden-collapse precursors).
   - Footprint: 212 Bytes static Flash, 16 Bytes static RAM.

2. **Gateway-Tier Consensus Ensemble (`models/gateway_model_int8.tflite` / `firmware/subsense_gateway_model.h`)**:
   - 6-Layer Deep Autoencoder coupled with a 5-tree decision ensemble.
   - Suppresses heavy shearer drilling vibrations while maintaining $\ge 97\%\text{ recall}$.
   - Constraint: $\le 1024\text{ KB Flash}$, $\le 200\text{ ms latency}$, $\ge 95\%\text{ recall}$.
   - Footprint: 23.7 KB static Flash, 256 Bytes static RAM.

---

## Directory Structure

```text
evaluation/
├── README.md                  # This documentation
├── config.yaml                # Acceptance targets, benchmark runs, and test parameters
├── requirements.txt           # Python dependencies
├── run_evaluation.py          # Master orchestrator script
├── benchmark.py               # Latency profiler (1000 runs) & ESP32 cycle estimator
├── metrics.py                 # Core/Advanced metrics, confusion matrix & comparative plots
├── model_inspection.py        # TFLite deep inspector & C header static memory parser
├── threshold_analysis.py      # Threshold sweep (0.01-0.99) & ROC/PR curve generators
├── robustness.py              # Sensor packet loss, Gaussian noise & fault injection
├── results/                   # Machine-readable JSONs, CSVs, and technical markdown report
│   ├── TINYML_EVALUATION_REPORT.md
│   ├── node_metrics.json
│   ├── gateway_metrics.json
│   ├── comparison.csv
│   ├── benchmark_results.csv
│   ├── threshold_analysis.csv
│   ├── node_confusion_matrix.png
│   ├── gateway_confusion_matrix.png
│   └── plots/                 # High-resolution publication-quality evaluation figures
```

---

## Quickstart & Reproduction

### 1. Install Dependencies
```bash
pip install -r evaluation/requirements.txt
```

### 2. Execute Full Evaluation Suite
Run the master evaluation script from the project root:
```bash
python evaluation/run_evaluation.py
```

### 3. Generated Artifacts
After execution, the following outputs are produced:
- **`evaluation/results/TINYML_EVALUATION_REPORT.md`**: Complete 12-section technical evaluation report.
- **`evaluation/results/comparison.csv`**: Head-to-head comparison table against SubSense budget constraints.
- **`evaluation/results/benchmark_results.csv`**: Detailed latency percentiles (Mean, P50, P90, P95, P99, Min, Max).
- **`evaluation/results/plots/`**:
  - `node_confusion_matrix.png`
  - `gateway_confusion_matrix.png`
  - `roc_curve.png`
  - `precision_recall_curve.png`
  - `f1_vs_threshold.png`
  - `recall_vs_threshold.png`
  - `score_distribution.png`
  - `model_size_comparison.png`
  - `latency_comparison.png`
  - `fp32_vs_int8_comparison.png`
  - `robustness_noise_performance.png`
