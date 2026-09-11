import { FastifyPluginAsync } from "fastify";
import { SiteProvisioningMetadataSchema } from "@subsense/shared";
import { withTenantScope, withSystemScope } from "../db/client";
import { TenantS3Storage } from "../storage/tenant-s3";
import { AuditLedger } from "../alert-engine/audit-ledger";
import { UserSession } from "../auth/service";

export const provisioningRoutes: FastifyPluginAsync = async (fastify) => {
  /**
   * ZERO-DOWNTIME SITE PROVISIONING
   * Site Administrator provisions a new mine site / mining panel via metadata payload.
   * No server restart or redeploy required. Immediately accessible to authorized operators.
   */
  fastify.post<{
    Params: { tenantId: string };
    Body: any;
  }>("/api/v1/tenants/:tenantId/sites", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { tenantId } = request.params;

    // RBAC check: Only site_admin can provision new sites
    if (!session || session.role !== "site_admin") {
      return reply.status(403).send({ error: "Forbidden: Only Site Administrator can provision new mine panels" });
    }

    const parseResult = SiteProvisioningMetadataSchema.safeParse(request.body);
    if (!parseResult.success) {
      return reply.status(400).send({
        error: "Validation failed for site provisioning metadata",
        details: parseResult.error.format(),
      });
    }

    const meta = parseResult.data;
    const s3Prefix = TenantS3Storage.getStoragePath(
      {
        bucketName: "subsense-strata-data-production",
        tenantId,
        siteId: meta.site_id,
        resourceCategory: "reports",
      },
      ""
    );

    const createdSite = await withTenantScope(
      { tenantId, userId: session?.userId || "USR-ADM-001", isRegulator: false },
      async (client) => {
        // Insert site metadata
        await client.query(
          `INSERT INTO sites (
            id, tenant_id, name, status, node_ids, gateway_credentials,
            seam_depth_meters, extraction_method, boundaries_geojson, s3_report_prefix
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
          ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            node_ids = EXCLUDED.node_ids,
            gateway_credentials = EXCLUDED.gateway_credentials,
            seam_depth_meters = EXCLUDED.seam_depth_meters,
            extraction_method = EXCLUDED.extraction_method,
            boundaries_geojson = EXCLUDED.boundaries_geojson;`,
          [
            meta.site_id,
            tenantId,
            meta.name,
            "active",
            JSON.stringify(meta.node_ids),
            JSON.stringify(meta.gateway_credentials),
            meta.seam_depth_meters,
            meta.extraction_method,
            JSON.stringify(meta.boundaries_geojson),
            s3Prefix,
          ]
        );

        // Provision individual node entries in tenant scope
        for (const nodeId of meta.node_ids) {
          await client.query(
            `INSERT INTO nodes (id, tenant_id, site_id, zone_id, status)
             VALUES ($1, $2, $3, $4, $5)
             ON CONFLICT (id) DO NOTHING;`,
            [nodeId, tenantId, meta.site_id, `${meta.site_id}-ZONE-1`, "online"]
          );
        }

        // Return provisioned record
        const res = await client.query("SELECT * FROM sites WHERE id = $1;", [meta.site_id]);
        return res.rows[0];
      }
    );

    // Cryptographic audit signing
    const auditHash = await AuditLedger.record({
      tenantId,
      userId: session?.userId || "USR-ADM-001",
      action: "ZERO_DOWNTIME_SITE_PROVISIONED",
      details: {
        siteId: meta.site_id,
        name: meta.name,
        nodeCount: meta.node_ids.length,
        gatewayEui: meta.gateway_credentials.gateway_eui,
        s3Prefix,
      },
    });

    return reply.status(201).send({
      message: "Site provisioned with zero downtime",
      site: createdSite,
      s3_storage: {
        bucket: "subsense-strata-data-production",
        report_prefix: s3Prefix,
        tenant_isolation: "ENFORCED",
      },
      audit_signature: auditHash,
    });
  });

  fastify.get<{
    Params: { tenantId: string };
  }>("/api/v1/tenants/:tenantId/sites", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    const { tenantId } = request.params;

    const isRegulator = session?.role === "dgms_regulator";

    return await withTenantScope(
      {
        tenantId: isRegulator ? null : tenantId,
        userId: session?.userId || "USR-OP-8492",
        isRegulator,
      },
      async (client) => {
        const res = await client.query("SELECT * FROM sites ORDER BY created_at DESC;");
        return { sites: res.rows };
      }
    );
  });
};
