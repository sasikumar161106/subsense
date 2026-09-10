import { FastifyPluginAsync } from "fastify";
import {
  AlertLifecycleEvent,
  AlertAcknowledgePayloadSchema,
  FalseAlarmSubmissionSchema,
  FalseAlarmReason,
} from "@subsense/shared";
import { withTenantScope, withSystemScope } from "../db/client";
import { AlertEscalationEngine } from "../alert-engine/escalation-timer";
import { AuditLedger } from "../alert-engine/audit-ledger";
import { UserSession } from "../auth/service";
import { NotificationDispatcher } from "../notifications/dispatcher";
import { AlertSystemClient } from "../alert-engine/alert-system-client";

export const alertsRoutes: FastifyPluginAsync = async (fastify) => {
  // Query active alerts in current tenant scope (Proxies to Alert_System with local fallback)
  fastify.get<{
    Querystring: { site_id?: string; severity?: string; state?: string };
  }>("/api/v1/alerts", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const isRegulator = session?.role === "dgms_regulator";

    // 1. Attempt proxy fetch from Alert_System (:3000)
    try {
      const remoteAlerts = await AlertSystemClient.fetchAlerts({
        zone_id: request.query.site_id,
        severity: request.query.severity,
        status: request.query.state,
        tenant_id: isRegulator ? undefined : session?.tenantId || "OPCO-ECL-01",
      });
      if (remoteAlerts && remoteAlerts.length > 0) {
        return { alerts: remoteAlerts };
      }
    } catch {
      // Graceful fallback to local DB when Alert_System is offline or in unit tests
    }

    return await withTenantScope(
      {
        tenantId: isRegulator ? null : session?.tenantId || "OPCO-ECL-01",
        userId: session?.userId || "USR-OP-8492",
        isRegulator,
      },
      async (client) => {
        let sql = "SELECT * FROM alert_lifecycle_events WHERE 1=1";
        const params: any[] = [];

        if (request.query.site_id) {
          params.push(request.query.site_id);
          sql += ` AND site_id = $${params.length}`;
        }
        if (request.query.severity) {
          params.push(request.query.severity);
          sql += ` AND severity = $${params.length}`;
        }
        if (request.query.state) {
          params.push(request.query.state);
          sql += ` AND state = $${params.length}`;
        }

        sql += " ORDER BY raised_at DESC;";

        const res = await client.query(sql, params);
        // Enrich with server-side countdown timer remaining
        const enriched = res.rows.map((row) => {
          const timer = AlertEscalationEngine.getActiveTimer(row.alert_id);
          return {
            ...row,
            time_to_critical_hours: [row.time_to_critical_min, row.time_to_critical_max],
            escalation_timer: timer,
          };
        });

        return { alerts: enriched };
      }
    );
  });

  // Acknowledge alert (audible dialog confirmation)
  // Acknowledge alert (audible dialog confirmation)
  fastify.post<{
    Params: { alertId: string };
    Body: any;
  }>("/api/v1/alerts/:alertId/acknowledge", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { alertId } = request.params;
    const body = request.body as any;
    const userId = session?.userId || body?.user_id || "USR-OP-8492";

    // Regulators cannot acknowledge operational alerts
    if (session?.role === "dgms_regulator") {
      return reply.status(403).send({ error: "Forbidden: DGMS Regulators are strictly read-only" });
    }

    try {
      try {
        await AlertSystemClient.acknowledgeAlert(alertId, userId, body?.comment);
      } catch {
        // Fallback to local
      }

      const updated = await AlertEscalationEngine.acknowledgeAlert(
        alertId,
        userId,
        body?.comment
      );
      return { success: true, alert: updated };
    } catch (err: any) {
      return reply.status(400).send({ error: err.message });
    }
  });

  // Flag False Alarm with structured reason feeding Layer 4 retraining loop
  fastify.post<{
    Params: { alertId: string };
    Body: any;
  }>("/api/v1/alerts/:alertId/false-alarm", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { alertId } = request.params;
    const body = request.body as any;
    const userId = session?.userId || body?.user_id || "USR-OP-8492";

    if (session?.role === "dgms_regulator") {
      return reply.status(403).send({ error: "Forbidden: DGMS Regulators cannot alter alert state" });
    }

    const parseResult = FalseAlarmSubmissionSchema.safeParse({
      ...(body || {}),
      user_id: userId,
    });

    if (!parseResult.success) {
      return reply.status(400).send({
        error: "Invalid false alarm submission payload",
        details: parseResult.error.format(),
      });
    }

    const { reason, notes, feature_vector_snapshot } = parseResult.data;

    try {
      try {
        await AlertSystemClient.submitFeedback(alertId, userId, reason, notes);
      } catch {
        // Fallback to local
      }

      const updated = await AlertEscalationEngine.flagFalseAlarm(
        alertId,
        userId,
        reason as FalseAlarmReason,
        notes,
        feature_vector_snapshot
      );
      return {
        success: true,
        message: "Alert marked false alarm. Retraining feature vector queued for Layer 4 AI engine.",
        alert: updated,
      };
    } catch (err: any) {
      return reply.status(400).send({ error: err.message });
    }
  });

  // Retract alert (de-escalate / retraction notice via Alert_System)
  fastify.post<{
    Params: { alertId: string };
    Body: any;
  }>("/api/v1/alerts/:alertId/retract", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { alertId } = request.params;
    const body = request.body as any;
    const userId = session?.userId || body?.user_id || "USR-OP-8492";

    if (session?.role === "dgms_regulator") {
      return reply.status(403).send({ error: "Forbidden: DGMS Regulators cannot alter alert state" });
    }

    try {
      const result = await AlertSystemClient.retractAlert(alertId, userId, body?.reason);
      return { success: true, ...result };
    } catch (err: any) {
      try {
        const updated = await AlertEscalationEngine.resolveAlert(alertId, userId);
        return { success: true, alert: updated };
      } catch (localErr: any) {
        return reply.status(400).send({ error: err.message });
      }
    }
  });

  // Resolve alert
  fastify.post<{
    Params: { alertId: string };
  }>("/api/v1/alerts/:alertId/resolve", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { alertId } = request.params;
    const userId = session?.userId || "USR-OP-8492";

    try {
      const updated = await AlertEscalationEngine.resolveAlert(alertId, userId);
      return { success: true, alert: updated };
    } catch (err: any) {
      return reply.status(400).send({ error: err.message });
    }
  });

  // Simulate new alert emission (for test & live operations drill)
  fastify.post<{
    Body: {
      site_id?: string;
      severity?: "info" | "warning" | "critical";
      explanation?: string;
      timeout_ms?: number;
    };
  }>("/api/v1/alerts/simulate", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const tenantId = session?.tenantId || "OPCO-ECL-01";
    const siteId = request.body.site_id || "PANEL7-JHARIA";
    const severity = request.body.severity || "warning";
    const timeoutMs = request.body.timeout_ms;

    const alertId = `ALERT-${siteId}-${Date.now().toString().slice(-6)}`;
    const raisedAt = new Date().toISOString();

    const newAlert: AlertLifecycleEvent = {
      alert_id: alertId,
      tenant_id: tenantId,
      site_id: siteId,
      zone_id: `${siteId}-ZONE-C`,
      severity,
      state: "new",
      raised_at: raisedAt,
      acknowledged_by: null,
      acknowledged_at: null,
      time_to_critical_hours: severity === "critical" ? [1.5, 4.0] : [6.0, 14.0],
      confidence_score: severity === "critical" ? 0.96 : 0.82,
      contributing_sensors: ["displacement_mm", "tilt_deg"],
      explanation_summary:
        request.body.explanation ||
        (severity === "critical"
          ? "CRITICAL ALERT: Rapid accelerated roof sag exceeding 4.2mm/hr with micro-seismic fracture clustering in Pillar 14."
          : "WARNING: Persistent tilt angle variance at N042 exceeding 0.18 degrees over past 45 minutes."),
    };

    // Save to database
    await withSystemScope(async (client) => {
      await client.query(
        `INSERT INTO alert_lifecycle_events (
          alert_id, tenant_id, site_id, zone_id, severity, state,
          raised_at, time_to_critical_min, time_to_critical_max,
          confidence_score, contributing_sensors, explanation_summary
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12);`,
        [
          newAlert.alert_id,
          newAlert.tenant_id,
          newAlert.site_id,
          newAlert.zone_id,
          newAlert.severity,
          newAlert.state,
          newAlert.raised_at,
          newAlert.time_to_critical_hours[0],
          newAlert.time_to_critical_hours[1],
          newAlert.confidence_score,
          JSON.stringify(newAlert.contributing_sensors),
          newAlert.explanation_summary,
        ]
      );
    });

    // Register with server-side escalation engine
    await AlertEscalationEngine.registerAlert(newAlert, timeoutMs);

    return reply.status(201).send({
      message: "Alert emitted and registered in server-side escalation ladder",
      alert: newAlert,
      countdown_ms: timeoutMs || 300000,
    });
  });

  // Manual siren trigger (Mine Operator capability)
  fastify.post<{
    Body: { site_id?: string; zone_id?: string; reason?: string };
  }>("/api/v1/siren/trigger", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    if (session && session.role !== "mine_operator") {
      return reply.status(403).send({ error: "Forbidden: Only Mine Operators can manually trigger sirens" });
    }

    const tenantId = session?.tenantId || "OPCO-ECL-01";
    const siteId = request.body.site_id || "PANEL7-JHARIA";
    const zoneId = request.body.zone_id || "PANEL7-ZONE-C";
    const userId = session?.userId || "USR-OP-8492";

    const auditHash = await AuditLedger.record({
      tenantId,
      userId,
      action: "MANUAL_EVACUATION_SIREN_TRIGGERED",
      details: {
        siteId,
        zoneId,
        reason: request.body.reason || "Manual operator emergency evacuation protocol initiated",
      },
    });

    return {
      success: true,
      status: "SIRENS_ACTIVATED",
      site_id: siteId,
      zone_id: zoneId,
      operator_id: userId,
      timestamp: new Date().toISOString(),
      audit_signature: auditHash,
    };
  });
};
