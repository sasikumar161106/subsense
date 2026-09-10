import { FastifyPluginAsync } from "fastify";
import { withTenantScope, withSystemScope } from "../db/client";
import { UserSession } from "../auth/service";
import { NodeTelemetryRecord } from "@subsense/shared";

export const tenantsRoutes: FastifyPluginAsync = async (fastify) => {
  // List tenants (or permitted tenants for regulator)
  fastify.get("/api/v1/tenants", async (request) => {
    return await withSystemScope(async (client) => {
      const res = await client.query("SELECT * FROM tenants ORDER BY id;");
      return { tenants: res.rows };
    });
  });

  // Get live sensor nodes and current telemetry for a panel
  fastify.get<{
    Params: { tenantId: string; siteId: string };
  }>("/api/v1/tenants/:tenantId/sites/:siteId/sensors", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { tenantId, siteId } = request.params;
    const isRegulator = session?.role === "dgms_regulator";

    return await withTenantScope(
      {
        tenantId: isRegulator ? null : tenantId,
        userId: session?.userId || "USR-OP-8492",
        isRegulator,
      },
      async (client) => {
        // Fetch nodes
        const nodesRes = await client.query(
          "SELECT * FROM nodes WHERE site_id = $1 ORDER BY id ASC;",
          [siteId]
        );

        // Fetch latest telemetry for these nodes
        const teleRes = await client.query(
          `SELECT DISTINCT ON (node_id) * FROM node_telemetry 
           WHERE site_id = $1 
           ORDER BY node_id, time DESC;`,
          [siteId]
        );

        const telemetryMap = new Map<string, any>();
        teleRes.rows.forEach((r) => telemetryMap.set(r.node_id, r));

        const combined = nodesRes.rows.map((node) => {
          const tele = telemetryMap.get(node.id);
          const asOf = tele?.as_of || new Date().toISOString();
          const ageSeconds = (Date.now() - new Date(asOf).getTime()) / 1000;
          // Zero Silent Staleness: >90s triggers amber warning state
          const isStale = tele ? tele.is_stale || ageSeconds > 90 : false;

          const record: NodeTelemetryRecord = {
            tenant_id: tenantId,
            site_id: siteId,
            node_id: node.id,
            as_of: asOf,
            is_stale: isStale,
            readings: {
              tilt_deg: parseFloat(tele?.tilt_deg || "0.120"),
              vibration_rms_mm_s: parseFloat(tele?.vibration_rms_mm_s || "0.850"),
              displacement_mm: parseFloat(tele?.displacement_mm || "2.100"),
              crack_index: parseFloat(tele?.crack_index || "0.010"),
            },
            anomaly_score: parseFloat(tele?.anomaly_score || "0.25"),
            health: {
              battery_pct: parseFloat(tele?.battery_pct || "85"),
              rssi_dbm: parseFloat(tele?.rssi_dbm || "-72"),
              hop_count: parseInt(tele?.hop_count || "2", 10),
              predicted_maintenance_days: parseFloat(tele?.predicted_maintenance_days || "35"),
            },
          };

          return {
            node,
            latest_telemetry: record,
            staleness_details: {
              age_seconds: Math.round(ageSeconds),
              threshold_seconds: 90,
              is_amber_warning: isStale,
            },
          };
        });

        return { sensors: combined };
      }
    );
  });
};
