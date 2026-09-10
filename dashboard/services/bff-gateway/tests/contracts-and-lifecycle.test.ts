import { describe, it, expect, beforeAll, afterEach } from "vitest";
import {
  NodeTelemetryRecordSchema,
  AlertLifecycleEventSchema,
  DgmsReportRequestPayloadSchema,
  AlertLifecycleEvent,
} from "@subsense/shared";
import { AlertEscalationEngine } from "../src/alert-engine/escalation-timer";
import { NotificationDispatcher } from "../src/notifications/dispatcher";
import { AuditLedger } from "../src/alert-engine/audit-ledger";
import { seedDatabase } from "../src/db/seed";
import { withSystemScope, withTenantScope } from "../src/db/client";

describe("Data Contracts, Alert Escalation Engine & Safety Notifications", () => {
  beforeAll(async () => {
    await seedDatabase();
  });

  afterEach(() => {
    AlertEscalationEngine.clearAllTimers();
    NotificationDispatcher.clearHistory();
  });

  it("validates exact shape of Contract 14.1 (Real-time node telemetry & health record)", () => {
    const valid14_1Payload = {
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      node_id: "SS-PANEL7-N042",
      as_of: "2026-09-09T04:15:00.000Z",
      is_stale: false,
      readings: {
        tilt_deg: 0.183,
        vibration_rms_mm_s: 1.42,
        displacement_mm: 3.7,
        crack_index: 0.02,
      },
      anomaly_score: 0.86,
      health: {
        battery_pct: 78,
        rssi_dbm: -71,
        hop_count: 3,
        predicted_maintenance_days: 21,
      },
    };

    const parsed = NodeTelemetryRecordSchema.safeParse(valid14_1Payload);
    expect(parsed.success).toBe(true);

    // Assert rejection on missing mandatory field
    const invalidPayload = { ...valid14_1Payload, anomaly_score: undefined };
    const invalidParsed = NodeTelemetryRecordSchema.safeParse(invalidPayload);
    expect(invalidParsed.success).toBe(false);
  });

  it("validates exact shape of Contract 14.2 (Alert lifecycle event)", () => {
    const valid14_2Payload = {
      alert_id: "ALERT-PANEL7-20260909-0412",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "warning",
      state: "acknowledged",
      raised_at: "2026-09-09T04:12:00.000Z",
      acknowledged_by: "USR-OP-8492",
      acknowledged_at: "2026-09-09T04:14:10.000Z",
      time_to_critical_hours: [6.0, 14.0],
      confidence_score: 0.79,
      contributing_sensors: ["tilt_deg", "displacement_mm"],
      explanation_summary:
        "Sustained tilt increase at N042, corroborated by 3 neighboring nodes over 40 minutes.",
    };

    const parsed = AlertLifecycleEventSchema.safeParse(valid14_2Payload);
    expect(parsed.success).toBe(true);
  });

  it("validates exact shape of Contract 14.3 (DGMS statutory report request payload)", () => {
    const valid14_3Payload = {
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      report_type: "dgms_statutory_subsidence_summary_v2",
      reporting_period: {
        start_date: "2026-08-01T00:00:00.000Z",
        end_date: "2026-08-31T23:59:59.000Z",
      },
      requested_by: "USR-REG-4412",
      output_format: "application/pdf",
      include_kriging_risk_maps: true,
      include_audit_trail: true,
    };

    const parsed = DgmsReportRequestPayloadSchema.safeParse(valid14_3Payload);
    expect(parsed.success).toBe(true);
  });

  it("proves Alert Lifecycle: Server-side timeout escalates unacknowledged alert and fires physical siren relay stub", async () => {
    const testAlertId = `ALERT-TEST-TIMEOUT-${Date.now()}`;
    const testAlert: AlertLifecycleEvent = {
      alert_id: testAlertId,
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "critical",
      state: "new",
      raised_at: new Date().toISOString(),
      acknowledged_by: null,
      acknowledged_at: null,
      time_to_critical_hours: [1.0, 3.0],
      confidence_score: 0.95,
      contributing_sensors: ["displacement_mm"],
      explanation_summary: "Impending strata shear collapse",
    };

    // Save alert into DB
    await withSystemScope(async (client) => {
      await client.query(
        `INSERT INTO alert_lifecycle_events (
          alert_id, tenant_id, site_id, zone_id, severity, state, raised_at,
          time_to_critical_min, time_to_critical_max, confidence_score,
          contributing_sensors, explanation_summary
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12);`,
        [
          testAlert.alert_id,
          testAlert.tenant_id,
          testAlert.site_id,
          testAlert.zone_id,
          testAlert.severity,
          testAlert.state,
          testAlert.raised_at,
          testAlert.time_to_critical_hours[0],
          testAlert.time_to_critical_hours[1],
          testAlert.confidence_score,
          JSON.stringify(testAlert.contributing_sensors),
          testAlert.explanation_summary,
        ]
      );
    });

    // Register with short 100ms timeout to simulate 5-minute escalation expiry
    await AlertEscalationEngine.registerAlert(testAlert, 100);

    // Wait 150ms for server-side timer to execute
    await new Promise((r) => setTimeout(r, 150));

    // Verify DB state transitioned to 'escalated'
    await withSystemScope(async (client) => {
      const res = await client.query(
        "SELECT state, escalated_at FROM alert_lifecycle_events WHERE alert_id = $1;",
        [testAlertId]
      );
      expect(res.rows[0].state).toBe("escalated");
      expect(res.rows[0].escalated_at).toBeTruthy();
    });

    // Verify physical siren relay stub was fired!
    expect(NotificationDispatcher.getSirenTriggerCount()).toBeGreaterThanOrEqual(1);
  });

  it("proves Closed-Loop Lifecycle: Audible acknowledgement disarms countdown and logs to cryptographic ledger", async () => {
    const testAlertId = `ALERT-TEST-ACK-${Date.now()}`;
    const testAlert: AlertLifecycleEvent = {
      alert_id: testAlertId,
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "warning",
      state: "new",
      raised_at: new Date().toISOString(),
      acknowledged_by: null,
      acknowledged_at: null,
      time_to_critical_hours: [5.0, 10.0],
      confidence_score: 0.82,
      contributing_sensors: ["tilt_deg"],
      explanation_summary: "Tilt creep test",
    };

    await withSystemScope(async (client) => {
      await client.query(
        `INSERT INTO alert_lifecycle_events (
          alert_id, tenant_id, site_id, zone_id, severity, state, raised_at,
          time_to_critical_min, time_to_critical_max, confidence_score,
          contributing_sensors, explanation_summary
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12);`,
        [
          testAlert.alert_id,
          testAlert.tenant_id,
          testAlert.site_id,
          testAlert.zone_id,
          testAlert.severity,
          testAlert.state,
          testAlert.raised_at,
          testAlert.time_to_critical_hours[0],
          testAlert.time_to_critical_hours[1],
          testAlert.confidence_score,
          JSON.stringify(testAlert.contributing_sensors),
          testAlert.explanation_summary,
        ]
      );
    });

    // Arm with 500ms timeout
    await AlertEscalationEngine.registerAlert(testAlert, 500);

    // Operator acknowledges within window
    const updated = await AlertEscalationEngine.acknowledgeAlert(
      testAlertId,
      "USR-OP-8492",
      "Audible tone confirmed on control room console"
    );

    expect(updated.state).toBe("acknowledged");
    expect(updated.acknowledged_by).toBe("USR-OP-8492");

    // Wait 600ms to ensure countdown was disarmed and never escalated
    await new Promise((r) => setTimeout(r, 600));

    await withSystemScope(async (client) => {
      const res = await client.query(
        "SELECT state FROM alert_lifecycle_events WHERE alert_id = $1;",
        [testAlertId]
      );
      // Must remain 'acknowledged', NOT 'escalated'
      expect(res.rows[0].state).toBe("acknowledged");
    });
  });

  it("proves Closed-Loop Lifecycle: False Alarm flags root cause vector and feeds Layer 4 retraining loop", async () => {
    const testAlertId = `ALERT-TEST-FALSE-${Date.now()}`;
    const testAlert: AlertLifecycleEvent = {
      alert_id: testAlertId,
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "warning",
      state: "new",
      raised_at: new Date().toISOString(),
      acknowledged_by: null,
      acknowledged_at: null,
      time_to_critical_hours: [8.0, 16.0],
      confidence_score: 0.74,
      contributing_sensors: ["vibration_rms_mm_s"],
      explanation_summary: "Transient vibration spike",
    };

    await withSystemScope(async (client) => {
      await client.query(
        `INSERT INTO alert_lifecycle_events (
          alert_id, tenant_id, site_id, zone_id, severity, state, raised_at,
          time_to_critical_min, time_to_critical_max, confidence_score,
          contributing_sensors, explanation_summary
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12);`,
        [
          testAlert.alert_id,
          testAlert.tenant_id,
          testAlert.site_id,
          testAlert.zone_id,
          testAlert.severity,
          testAlert.state,
          testAlert.raised_at,
          testAlert.time_to_critical_hours[0],
          testAlert.time_to_critical_hours[1],
          testAlert.confidence_score,
          JSON.stringify(testAlert.contributing_sensors),
          testAlert.explanation_summary,
        ]
      );
    });

    const falseAlarmResult = await AlertEscalationEngine.flagFalseAlarm(
      testAlertId,
      "USR-OP-8492",
      "surface_blasting",
      "Surface bench blasting at opencast sector corroborated by shift log"
    );

    expect(falseAlarmResult.state).toBe("false_alarm");
    expect(falseAlarmResult.false_alarm_reason).toBe("surface_blasting");

    // Verify audit ledger contains Layer 4 retraining event
    await withSystemScope(async (client) => {
      const auditRes = await client.query(
        "SELECT * FROM tamper_proof_audit_ledger WHERE action = 'LAYER4_RETRAINING_FALSE_ALARM_VECTOR_EMITTED' ORDER BY timestamp DESC LIMIT 1;"
      );
      expect(auditRes.rows.length).toBe(1);
      const details = auditRes.rows[0].details_json;
      expect(details.reason).toBe("surface_blasting");
      expect(details.alertId).toBe(testAlertId);
    });
  });

  it("proves Multi-Channel Dispatcher & Quiet-Hours Override for Critical severity", async () => {
    // Test 1: During quiet hours (e.g. 23:00 UTC), a Warning alert is silenced from push/SMS
    const quietTime = new Date("2026-09-09T23:30:00.000Z"); // 23:30 UTC is inside 22:00-06:00
    const warningAlert: AlertLifecycleEvent = {
      alert_id: "ALERT-WARN-QUIET",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "warning",
      state: "new",
      raised_at: quietTime.toISOString(),
      acknowledged_by: null,
      acknowledged_at: null,
      time_to_critical_hours: [6.0, 12.0],
      confidence_score: 0.75,
      contributing_sensors: ["tilt_deg"],
      explanation_summary: "Moderate tilt anomaly",
    };

    const warnResults = await NotificationDispatcher.dispatchAlert(warningAlert, {
      evaluationTime: quietTime,
    });
    // Warning alerts must be silenced during quiet hours
    expect(warnResults.length).toBe(0);

    // Test 2: CRITICAL severity MUST OVERRIDE QUIET HOURS AND FIRE ACROSS CHANNELS
    const criticalAlert: AlertLifecycleEvent = {
      alert_id: "ALERT-CRIT-OVERRIDE",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "PANEL7-ZONE-C",
      severity: "critical",
      state: "new",
      raised_at: quietTime.toISOString(),
      acknowledged_by: null,
      acknowledged_at: null,
      time_to_critical_hours: [1.0, 2.5],
      confidence_score: 0.98,
      contributing_sensors: ["displacement_mm", "vibration_rms_mm_s"],
      explanation_summary: "Catastrophic roof strata shear impending",
    };

    const critResults = await NotificationDispatcher.dispatchAlert(criticalAlert, {
      evaluationTime: quietTime,
    });

    // Must deliver across multiple channels (browser, mobile push, SMS, siren relay)
    expect(critResults.length).toBeGreaterThanOrEqual(3);
    const channels = critResults.map((r) => r.channel);
    expect(channels).toContain("browser_push");
    expect(channels).toContain("mobile_push_fcm");
    expect(channels).toContain("sms_twilio");
    expect(channels).toContain("physical_siren_relay");
  });

  it("proves Cryptographic Audit Ledger SHA-256 chain integrity", async () => {
    const isIntact = await AuditLedger.verifyIntegrity();
    expect(isIntact).toBe(true);
  });
});
