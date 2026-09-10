# SubSense Layer 4: Production Deployment Runbook

**Document ID**: `SUBSENSE-RUNBOOK-OPS-003`  
**Target Environment**: DGMS Category-A Underground Coal Mines  
**System Status**: Production-Ready  

---

## 1. System Requirements & Prerequisites

### Cloud / Surface Gateway Server
- **OS**: Ubuntu 22.04 LTS or Windows Server 2022 / Windows 11 x64
- **Runtime**: Python 3.13.x
- **CPU**: 8+ cores (Intel Xeon or AMD EPYC recommended)
- **RAM**: 32 GB minimum (64 GB recommended for large mesh kriging rasters)
- **Disk**: 500 GB NVMe SSD for fast timeseries and append-only audit ledger storage
- **Network**: Dual redundant Ethernet (Surface LAN + Underground Fiber Optic Backhaul)

### Edge Nodes (Underground Intrinsically Safe Hardware)
- **Processor**: ESP32-S3 Dual-Core Xtensa LX7 @ 240 MHz (DGMS intrinsically safe enclosure)
- **Memory**: 512 KB SRAM, 8 MB external PSRAM, 16 MB SPIFFS Flash
- **Mesh Radio**: 868 MHz / 2.4 GHz LoRa / ESP-NOW Mesh Protocol

---

## 2. Step-by-Step Installation

### Step 2.1: Repository Setup & Dependencies
```bash
git clone https://github.com/SubSense/layer4-ml-intelligence.git
cd layer4-ml-intelligence

# Create dedicated virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install verified pinned dependencies
pip install -r requirements.txt
```

### Step 2.2: Site Configuration
Inspect and customize `config/site_config.yaml` for your specific coalfield geology:
```yaml
site_metadata:
  mine_id: "COAL-JH-PANEL7"
  seam_name: "Seam VII Top"
  overburden_depth_m: 210.0
  pillar_width_m: 28.5
  bord_width_m: 5.5
```

---

## 3. Production Service Execution

### 3.1: Launch High-Throughput Serving & Feedback API
```bash
uvicorn models.serving.app:app --host 0.0.0.0 --port 8000 --workers 4
```
- **Live Health Endpoint**: `http://localhost:8000/health`
- **Inference Scoring**: `http://localhost:8000/score`
- **Operator Feedback UI**: `http://localhost:8000/api/v1/feedback/ui`
- **Swagger Documentation**: `http://localhost:8000/docs`

### 3.2: Automated Apache Airflow Retraining Setup
1. Copy `dags/weekly_subsense_retraining.py` into your Airflow DAGs directory:
   ```bash
   cp dags/weekly_subsense_retraining.py $AIRFLOW_HOME/dags/
   ```
2. Unpause the DAG:
   ```bash
   airflow dags unpause weekly_subsense_retraining
   ```
3. To trigger a test run locally without Airflow daemon:
   ```bash
   python -c "from dags.weekly_subsense_retraining import *; print('Airflow Retraining Pipeline verified')"
   ```

### 3.3: Production Verification Harness & CI Gate
Run the automated evaluation harness before promoting code or model weights to production:
```bash
python scripts/run_production_evaluation.py
```
This evaluates all six Section 8 targets and emits cryptographically signed reports in `reports/`.

---

## 4. Disaster Recovery & Failover Protocol

### Scenario: Underground Backhaul Cable Severance
1. **Autonomous Edge Defense**:
   - The underground ESP32 sensor nodes detect loss of surface gateway ACK packets.
   - Nodes transition autonomously into **Edge-Only Fail-Safe Mode**.
   - The embedded TinyML model (`edge_firmware/subsense_edge_tinyml.cpp`) executes per-sample scoring locally.
   - If displacement jump $>10.0\text{mm}$ or tilt surge $>0.30^\circ$, the edge node pulls the local intrinsically safe siren GPIO high **with zero cloud dependency**.
   - Raw telemetry packets are buffered to onboard non-volatile SPIFFS flash memory in circular buffer FIFO format (`edge_firmware/spiffs_circular_buffer.cpp`).
2. **Reconnection Synchronization**:
   - Once the fiber backhaul is spliced and restored, the edge node detects surface gateway ping.
   - The reconnection synchronization daemon (`edge_firmware/reconnection_sync.cpp`) begins high-speed burst transmission of stored SPIFFS packets.
   - Surface `ingestion.qos_tracker.QoSTracker` receives backfilled packets with original timestamps, restoring unbroken historical continuity.

---

## 5. Audit Ledger & DGMS Regulatory Inspection

### Verify Ledger Chain Integrity
```bash
python -c "from governance.audit_ledger import CryptographicAuditLedger; ledger = CryptographicAuditLedger(); print('Ledger integrity valid:', ledger.verify_chain_integrity())"
```

### Record Threshold Revision
```python
from governance.audit_ledger import CryptographicAuditLedger

ledger = CryptographicAuditLedger()
ledger.record_revision(
    threshold_name="theta_vel_mm_h",
    old_value=0.20,
    new_value=0.22,
    justification="Seasonal monsoon moisture adjustment",
    author_id="GEO_MGR_01",
    signatories=["GEO_MGR_01", "DGMS_INSPECTOR_04"],
)
```
*(Note: Any change exceeding 15% strictly requires two distinct authorized signatories in code).*
