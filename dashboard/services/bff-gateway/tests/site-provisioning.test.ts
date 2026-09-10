import { describe, it, expect, beforeAll } from "vitest";
import { withTenantScope, withSystemScope } from "../src/db/client";
import { seedDatabase } from "../src/db/seed";
import { TenantS3Storage } from "../src/storage/tenant-s3";

describe("Zero-Downtime Metadata Site Provisioning", () => {
  beforeAll(async () => {
    await seedDatabase();
  });

  it("provisions a new mining panel dynamically via metadata only without server restart", async () => {
    const newSiteId = "PANEL9-RANIGANJ";
    const tenantId = "OPCO-ECL-01";

    const s3Prefix = TenantS3Storage.getStoragePath(
      {
        bucketName: "subsense-strata-data-production",
        tenantId,
        siteId: newSiteId,
        resourceCategory: "reports",
      },
      ""
    );

    expect(s3Prefix).toBe("tenants/OPCO-ECL-01/PANEL9-RANIGANJ/reports/");

    // Provision site metadata
    await withTenantScope(
      { tenantId, userId: "USR-ADM-001", isRegulator: false },
      async (client) => {
        await client.query(
          `INSERT INTO sites (
            id, tenant_id, name, status, node_ids, gateway_credentials,
            seam_depth_meters, extraction_method, boundaries_geojson, s3_report_prefix
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);`,
          [
            newSiteId,
            tenantId,
            "Raniganj Panel 9 Highwall Expansion",
            "active",
            JSON.stringify(["SS-RANI-N091", "SS-RANI-N092"]),
            JSON.stringify({ gateway_eui: "GW-ECL-RN-009", protocol: "sub_ghz_mesh" }),
            280.0,
            "longwall",
            JSON.stringify({
              type: "Polygon",
              coordinates: [[[87.15, 23.63], [87.16, 23.63], [87.16, 23.64], [87.15, 23.64], [87.15, 23.63]]],
            }),
            s3Prefix,
          ]
        );

        // Nodes provisioned
        await client.query(
          `INSERT INTO nodes (id, tenant_id, site_id, zone_id, status)
           VALUES 
           ('SS-RANI-N091', 'OPCO-ECL-01', 'PANEL9-RANIGANJ', 'PANEL9-ZONE-1', 'online'),
           ('SS-RANI-N092', 'OPCO-ECL-01', 'PANEL9-RANIGANJ', 'PANEL9-ZONE-1', 'online');`
        );
      }
    );

    // Assert that ECL Operator can immediately see the new panel in their tenant scope
    const eclSites = await withTenantScope(
      { tenantId: "OPCO-ECL-01", userId: "USR-OP-8492", isRegulator: false },
      async (client) => {
        const res = await client.query("SELECT * FROM sites WHERE id = $1;", [newSiteId]);
        return res.rows;
      }
    );

    expect(eclSites.length).toBe(1);
    expect(eclSites[0].name).toBe("Raniganj Panel 9 Highwall Expansion");
    expect(eclSites[0].s3_report_prefix).toBe("tenants/OPCO-ECL-01/PANEL9-RANIGANJ/reports/");

    // Assert that BCCL Operator STILL CANNOT see this newly provisioned site (RLS isolation enforced)
    const bcclSites = await withTenantScope(
      { tenantId: "OPCO-BCCL-02", userId: "USR-OP-9901", isRegulator: false },
      async (client) => {
        const res = await client.query("SELECT * FROM sites WHERE id = $1;", [newSiteId]);
        return res.rows;
      }
    );

    expect(bcclSites.length).toBe(0);
  });
});
