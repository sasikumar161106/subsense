import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  mapFeedbackReasonToVerdict,
  alertRecordToLifecycleEvent,
  AlertSystemClient,
} from "../src/alert-engine/alert-system-client";
import { buildApp } from "../src/app";

describe("Alert_System BFF Proxy & Contract Translation (Phase 2c)", () => {
  it("translates Dashboard false alarm reasons to Alert_System FeedbackVerdict", () => {
    expect(mapFeedbackReasonToVerdict("false_alarm")).toBe("FalsePositive");
    expect(mapFeedbackReasonToVerdict("surface_blasting")).toBe("FalsePositive");
    expect(mapFeedbackReasonToVerdict("heavy_vehicle_impact")).toBe("FalsePositive");
    expect(mapFeedbackReasonToVerdict("unrelated_seismic_activity")).toBe("FalsePositive");
    expect(mapFeedbackReasonToVerdict("sensor_hardware_glitch")).toBe("HardwareDefect");
    expect(mapFeedbackReasonToVerdict("instrument_failure")).toBe("HardwareDefect");
    expect(mapFeedbackReasonToVerdict("telecom_packet_jitter")).toBe("HardwareDefect");
    expect(mapFeedbackReasonToVerdict("other_operational_noise")).toBe("FalsePositive");
    expect(mapFeedbackReasonToVerdict("confirmed")).toBe("Confirmed");
    expect(mapFeedbackReasonToVerdict("true_alarm")).toBe("Confirmed");
    expect(mapFeedbackReasonToVerdict("random_unspecified")).toBe("Unclear");
  });

  it("converts Alert_System AlertRecord to Dashboard AlertLifecycleEvent schema", () => {
    const record = {
      alert_id: "ALERT-PANEL7-001",
      tenant_id: "tenant-jharia-01",
      risk_zone_id: "11111111-1111-1111-1111-111111111111",
      severity: "Critical",
      status: "Active",
      confidence_score: 0.92,
      time_to_critical_hours: 10.0,
      explanation: "CRITICAL: Accelerated roof sag at N042.",
      contributing_nodes: ["SS-PANEL7-N042"],
      contributing_sensors: ["tilt_deg", "vibration_rms_mm_s"],
      created_at: "2026-09-10T12:00:00.000Z",
    };

    const lifecycle = alertRecordToLifecycleEvent(record);

    expect(lifecycle.alert_id).toBe("ALERT-PANEL7-001");
    expect(lifecycle.severity).toBe("critical");
    expect(lifecycle.state).toBe("new");
    expect(lifecycle.confidence_score).toBe(0.92);
    expect(lifecycle.time_to_critical_hours).toEqual([7.5, 12.5]);
    expect(lifecycle.contributing_sensors).toEqual(["tilt_deg", "vibration_rms_mm_s"]);
    expect(lifecycle.explanation_summary).toBe("CRITICAL: Accelerated roof sag at N042.");

    // Retracted status mapping
    const retractedRecord = { ...record, status: "Retracted" };
    const retractedLifecycle = alertRecordToLifecycleEvent(retractedRecord);
    expect(retractedLifecycle.state).toBe("false_alarm");
  });

  describe("BFF REST Endpoints Proxying", () => {
    let app: any;

    beforeEach(async () => {
      app = await buildApp();
    });

    afterEach(async () => {
      await app.close();
      vi.restoreAllMocks();
    });

    it("proxies GET /api/v1/alerts to Alert_System and converts format", async () => {
      const mockAlerts = [
        {
          alert_id: "ALERT-REMOTE-001",
          tenant_id: "tenant-jharia-01",
          risk_zone_id: "11111111-1111-1111-1111-111111111111",
          severity: "Warning",
          status: "Active",
          confidence_score: 0.85,
          explanation: "Warning from Alert_System",
          contributing_sensors: ["tilt_deg"],
        },
      ];

      vi.spyOn(global, "fetch").mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlerts,
      } as any);

      const res = await app.inject({
        method: "GET",
        url: "/api/v1/alerts",
        headers: {
          "x-user-role": "mine_safety_officer",
          "x-tenant-id": "tenant-jharia-01",
        },
      });

      expect(res.statusCode).toBe(200);
      const data = JSON.parse(res.body);
      expect(data.alerts.length).toBe(1);
      expect(data.alerts[0].alert_id).toBe("ALERT-REMOTE-001");
      expect(data.alerts[0].severity).toBe("warning");
    });

    it("proxies POST /api/v1/alerts/:id/retract to Alert_System", async () => {
      vi.spyOn(AlertSystemClient, "retractAlert").mockResolvedValueOnce({
        alert: {
          alert_id: "ALERT-RETRACT-01",
          tenant_id: "tenant-jharia-01",
          site_id: "PANEL7-JHARIA",
          zone_id: "11111111-1111-1111-1111-111111111111",
          severity: "warning",
          state: "false_alarm",
          raised_at: new Date().toISOString(),
          acknowledged_by: null,
          acknowledged_at: null,
          time_to_critical_hours: [6, 14],
          confidence_score: 0.85,
          contributing_sensors: ["tilt_deg"],
          explanation_summary: "Retracted alert",
        },
        retraction_deliveries: [],
      });

      const res = await app.inject({
        method: "POST",
        url: "/api/v1/alerts/ALERT-RETRACT-01/retract",
        headers: {
          "x-user-role": "mine_safety_officer",
          "x-tenant-id": "tenant-jharia-01",
        },
        payload: { reason: "False positive verified" },
      });

      expect(res.statusCode).toBe(200);
      const data = JSON.parse(res.body);
      expect(data.success).toBe(true);
      expect(data.alert.state).toBe("false_alarm");
    });
  });
});
