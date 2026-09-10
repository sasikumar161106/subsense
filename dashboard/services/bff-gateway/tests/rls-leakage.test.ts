import { describe, it, expect, beforeAll } from "vitest";
import { getDb, withTenantScope, withSystemScope } from "../src/db/client";
import { seedDatabase } from "../src/db/seed";

describe("Multi-Tenancy & Database RLS Isolation Engine", () => {
  beforeAll(async () => {
    await seedDatabase();
  });

  it("proves ZERO cross-tenant leakage: ECL Operator sees only ECL sites and zero BCCL sites", async () => {
    // When executing under ECL operator tenant session
    const eclSites = await withTenantScope(
      { tenantId: "OPCO-ECL-01", userId: "USR-OP-8492", isRegulator: false },
      async (client) => {
        // Query has NO manual WHERE tenant_id filter! RLS query interceptor enforces it.
        const res = await client.query("SELECT * FROM sites;");
        return res.rows;
      }
    );

    expect(eclSites.length).toBeGreaterThan(0);
    // Every single returned site must belong to OPCO-ECL-01
    expect(eclSites.every((s) => s.tenant_id === "OPCO-ECL-01")).toBe(true);
    // Explicitly verify BCCL site 'MOONIDIH-SEAM-16' is NOT present
    expect(eclSites.find((s) => s.id === "MOONIDIH-SEAM-16")).toBeUndefined();
  });

  it("proves ZERO cross-tenant leakage: BCCL Operator sees only BCCL sites and zero ECL sites", async () => {
    // When executing under BCCL operator tenant session
    const bcclSites = await withTenantScope(
      { tenantId: "OPCO-BCCL-02", userId: "USR-OP-9901", isRegulator: false },
      async (client) => {
        const res = await client.query("SELECT * FROM sites;");
        return res.rows;
      }
    );

    expect(bcclSites.length).toBeGreaterThan(0);
    expect(bcclSites.every((s) => s.tenant_id === "OPCO-BCCL-02")).toBe(true);
    // Explicitly verify ECL site 'PANEL7-JHARIA' is NOT present
    expect(bcclSites.find((s) => s.id === "PANEL7-JHARIA")).toBeUndefined();
  });

  it("proves ZERO cross-tenant leakage for alert lifecycle events", async () => {
    // ECL Operator queries alerts
    const eclAlerts = await withTenantScope(
      { tenantId: "OPCO-ECL-01", userId: "USR-OP-8492", isRegulator: false },
      async (client) => {
        const res = await client.query("SELECT * FROM alert_lifecycle_events;");
        return res.rows;
      }
    );

    expect(eclAlerts.length).toBeGreaterThan(0);
    expect(eclAlerts.every((a) => a.tenant_id === "OPCO-ECL-01")).toBe(true);
    expect(eclAlerts.find((a) => a.alert_id === "ALERT-MOONIDIH-20260909-0105")).toBeUndefined();

    // BCCL Operator queries alerts
    const bcclAlerts = await withTenantScope(
      { tenantId: "OPCO-BCCL-02", userId: "USR-OP-9901", isRegulator: false },
      async (client) => {
        const res = await client.query("SELECT * FROM alert_lifecycle_events;");
        return res.rows;
      }
    );

    expect(bcclAlerts.length).toBeGreaterThan(0);
    expect(bcclAlerts.every((a) => a.tenant_id === "OPCO-BCCL-02")).toBe(true);
    expect(bcclAlerts.find((a) => a.alert_id === "ALERT-PANEL7-20260909-0412")).toBeUndefined();
  });

  it("proves Dynamic Regulator Scoping: DGMS Regulator queries across permitted tenants via explicit permit tables", async () => {
    // Regulator has permits for both OPCO-ECL-01 and OPCO-BCCL-02
    const regulatorSites = await withTenantScope(
      { tenantId: null, userId: "USR-REG-4412", isRegulator: true },
      async (client) => {
        const res = await client.query("SELECT * FROM sites ORDER BY tenant_id;");
        return res.rows;
      }
    );

    // Regulator sees both tenants because valid permits exist
    const tenantIds = new Set(regulatorSites.map((s) => s.tenant_id));
    expect(tenantIds.has("OPCO-ECL-01")).toBe(true);
    expect(tenantIds.has("OPCO-BCCL-02")).toBe(true);

    // Now test revoking/deactivating permit for BCCL
    await withSystemScope(async (client) => {
      await client.query("UPDATE regulator_permits SET active = false WHERE tenant_id = 'OPCO-BCCL-02';");
    });

    const restrictedRegulatorSites = await withTenantScope(
      { tenantId: null, userId: "USR-REG-4412", isRegulator: true },
      async (client) => {
        const res = await client.query("SELECT * FROM sites;");
        return res.rows;
      }
    );

    // Now regulator can ONLY see ECL, not BCCL!
    expect(restrictedRegulatorSites.every((s) => s.tenant_id === "OPCO-ECL-01")).toBe(true);
    expect(restrictedRegulatorSites.find((s) => s.tenant_id === "OPCO-BCCL-02")).toBeUndefined();

    // Re-enable permit for subsequent tests
    await withSystemScope(async (client) => {
      await client.query("UPDATE regulator_permits SET active = true WHERE tenant_id = 'OPCO-BCCL-02';");
    });
  });
});
