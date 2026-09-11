import { FastifyPluginAsync } from "fastify";
import {
  NodeTelemetryRecordSchema,
  AlertLifecycleEventSchema,
  DgmsReportRequestPayloadSchema,
} from "@subsense/shared";

import { GatewayWebSocketServer } from "../ws/gateway-ws";

export const contractsRoutes: FastifyPluginAsync = async (fastify) => {
  // 14.1 Telemetry Contract Validator & Mock
  fastify.post("/api/v1/contracts/validate/14.1-telemetry", async (request, reply) => {
    const result = NodeTelemetryRecordSchema.safeParse(request.body);
    if (!result.success) {
      return reply.status(400).send({
        valid: false,
        contract: "14.1 Real-time node telemetry & health record",
        errors: result.error.format(),
      });
    }
    return {
      valid: true,
      contract: "14.1 Real-time node telemetry & health record",
      validated_payload: result.data,
    };
  });

  fastify.get("/api/v1/contracts/sample/14.1-telemetry", async () => {
    return {
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      node_id: "SS-PANEL7-N042",
      as_of: "2026-09-09T04:15:00.000Z",
      is_stale: false,
      readings: {
        tilt_deg: 0.183,
        vibration_rms_mm_s: 1.42,
        displacement_mm: 3.70,
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
  });

  // 14.2 Alert Lifecycle Contract Validator & Mock
  fastify.post("/api/v1/contracts/validate/14.2-alert", async (request, reply) => {
    const result = AlertLifecycleEventSchema.safeParse(request.body);
    if (!result.success) {
      return reply.status(400).send({
        valid: false,
        contract: "14.2 Alert lifecycle event",
        errors: result.error.format(),
      });
    }
    return {
      valid: true,
      contract: "14.2 Alert lifecycle event",
      validated_payload: result.data,
    };
  });

  fastify.get("/api/v1/contracts/sample/14.2-alert", async () => {
    return {
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
  });

  // 14.3 DGMS Statutory Report Contract Validator & Mock
  fastify.post("/api/v1/contracts/validate/14.3-dgms-report", async (request, reply) => {
    const result = DgmsReportRequestPayloadSchema.safeParse(request.body);
    if (!result.success) {
      return reply.status(400).send({
        valid: false,
        contract: "14.3 DGMS statutory report request payload",
        errors: result.error.format(),
      });
    }
    return {
      valid: true,
      contract: "14.3 DGMS statutory report request payload",
      validated_payload: result.data,
    };
  });

  fastify.get("/api/v1/contracts/sample/14.3-dgms-report", async () => {
    return {
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
  });

  // Real Physical Telemetry Ingestion Broadcast
  fastify.post("/api/v1/telemetry/broadcast", async (request, reply) => {
    const record = request.body as any;
    GatewayWebSocketServer.broadcastTelemetry(record);
    return { status: "BROADCASTED", node_id: record?.node_id };
  });
};
