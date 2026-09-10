# SubSense Layer 4: DGMS Regulatory Compliance Packet

**Regulatory Filing**: Directorate General of Mines Safety (DGMS)  
**Standard**: Coal Mines Regulations (CMR) 2017 — Strata Control & Monitoring Plan (SCAMP)  
**Technical Dossier**: `DGMS-SCAMP-SUB-2026-L4`  
**Classification**: Safety-Critical Digital Intelligence Infrastructure  

---

## 1. Statutory Authority & Regulatory Framework

Under Regulation 104 and 105 of the Coal Mines Regulations (CMR) 2017, mine operators are legally mandated to formulate, implement, and maintain a scientific Strata Control and Monitoring Plan (SCAMP). 

SubSense Layer 4 serves as the automated real-time intelligence engine governing roof displacement, pillar dilation, and surface subsidence forecasting. Because its outputs directly command automated sirens, conveyor cutoffs, and miner evacuations, it is classified as a **Level 3 Safety-Critical Life-Safety System**.

---

## 2. DGMS Compliance Matrix

| Statutory Mandate | CMR 2017 Clause | SubSense Implementation | Verification Method |
| :--- | :--- | :--- | :--- |
| **Deterministic Alert Escalation** | Reg 104(3)(b) | Explicit boolean rules engine (`fusion.decision_engine.FusionDecisionEngine`). Zero black-box neural models may unilaterally escalate incidents. | 100% branch test coverage (`tests/test_fusion_engine.py`) |
| **Explainability by Construction** | Reg 105(1) | Schema-enforced gatekeeper (`explainability.alert_schema`). Rejects any alert missing contributing sensors, corroborating neighbor IDs, or plain-language summary. | Automated schema rejection test (`tests/test_explainability_gate.py`) |
| **Threshold Revision Governance** | Reg 104(4) | SHA-256 hash-chained append-only cryptographic ledger (`governance.audit_ledger`). Changes $>15\%$ require multi-party sign-off in code. | Disk tamper mutation test (`tests/test_audit_ledger_tamper.py`) |
| **Continuous Uninterrupted Defense** | Reg 104(1) | Dual-tier edge defense (`edge_firmware/subsense_edge_tinyml.cpp`). Edge nodes autonomously fire sirens during backhaul cable severance. | Chaos backhaul severance test (`tests/test_system_integration_chaos.py`) |
| **Model Retraining Safety Gates** | Reg 105(2) | Code-enforced promotion gate (`active_learning.validation_gate`). Blocks candidates unless $\text{Recall} \ge \text{Production}$ and $\ge 35\%$ FP reduction. | Regressing candidate rejection test (`tests/test_active_learning_gate.py`) |
| **Multi-Scale Macro Verification** | Reg 104(2) | Sentinel-1 InSAR satellite Line-of-Sight interferometric crosscheck fused with terrestrial Kriging risk surfaces. | InSAR spatial divergence test (`tests/test_insar_divergence.py`) |

---

## 3. The Three Life-Safety Alert Tiers

### ADVISORY (Level 1 Audit)
- **Trigger**: $S_{node} > 0.65$ (single node); uncorroborated single sensor; LSTM trend flat/decelerating; Confidence $< 0.60$.
- **Action**: Dashboard notice, node health telemetry ping, logged to Level 1 maintenance audit.
- **Safety Objective**: Early preventative maintenance before physical sensor fatigue causes false alarms.

### WARNING (Level 2 DGMS-Tracked)
- **Trigger**: $S_{node} \ge 0.75$ across $\ge 2$ physical channels; $C_{corr} \ge 0.70$ (within $\le 120\text{m}$); $R_{GNN} \ge 0.70$; $\text{LSTM} == \text{SUSTAINED}$.
- **Action**: Automated SMS/Telegram dispatch to resident geotechnical manager, physical underground inspection dispatch, recorded in statutory DGMS shift log.
- **Safety Objective**: Timely human intervention and face inspection before acceleration onset.

### CRITICAL (Level 3 Emergency Siren & Evacuation)
- **Trigger**:
  - $(\text{Warning Conditions} \land \text{TTC}_{median} \le 12.0\text{h} \land \text{LSTM} == \text{ACCELERATING})$
  - **OR** $\text{TTC}_{median} < 8.0\text{h}$ (unconditional life-safety override, ADR-005)
  - **OR** Instantaneous displacement spike $> 10.0\text{mm}$ (dynamic shear fail-safe)
- **Action**: Automated audible and visual sirens activated in affected zones, instantaneous conveyor belt cutoff to prevent worker entrapment, mandatory zone evacuation.
- **Safety Objective**: Total prevention of personnel loss during dynamic roof falls or massive goaf collapses.

---

## 4. Cryptographic Audit Trail Architecture

All threshold revisions and emergency alert dispatches are logged to an append-only ledger protected by SHA-256 cryptographic chaining:

```
[Genesis Block: REV-00000]
       │
       ▼ (Hash: h0)
[Revision Block: REV-00001] ─── PrevHash: h0, EntryHash: h1
       │
       ▼ (Hash: h1)
[Revision Block: REV-00002] ─── PrevHash: h1, EntryHash: h2
```

Any modification, truncation, or historical alteration of ledger files stored on disk invalidates the hash chain and triggers an immediate cryptographic tamper alarm upon system startup.

---

## 5. Auditor Verification Commands

DGMS Safety Inspectors can independently verify system compliance using the following terminal commands:

1. **Verify 100% Decision Engine Branch Coverage**:
   ```bash
   python -m coverage run --branch -m pytest tests/test_fusion_engine.py
   python -m coverage report --include="fusion/decision_engine.py"
   ```
2. **Verify Cryptographic Ledger Chain**:
   ```bash
   python -c "from governance.audit_ledger import CryptographicAuditLedger; l = CryptographicAuditLedger(); print('Ledger Chain Valid:', l.verify_chain_integrity())"
   ```
3. **Execute Section 8 Production Verification Harness**:
   ```bash
   python scripts/run_production_evaluation.py
   ```
4. **Execute Full Chaos & Integration Test Suite**:
   ```bash
   pytest tests/test_system_integration_chaos.py -v
   ```
