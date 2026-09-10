import { describe, it, expect } from "vitest";
import jwt from "jsonwebtoken";
import { verifyUserToken, signUserToken, normalizeTenantId, UserSession } from "../src/auth/service";

const JWT_SECRET = "subsense-jwt-safety-compliance-secret-key-2026";

describe("Phase 3b: Unified Auth Secret & Cross-Service Interoperability", () => {
  it("should verify tokens issued by Alert_System (no issuer/audience constraint)", () => {
    // Alert_System payload structure
    const alertSystemPayload = {
      user_id: "usr-jharia-01",
      username: "officer_jharia",
      role: "mine_safety_officer",
      tenant_id: "tenant-jharia-01",
    };

    const alertToken = jwt.sign(alertSystemPayload, JWT_SECRET, { expiresIn: "24h" });

    const session = verifyUserToken(alertToken);
    expect(session).not.toBeNull();
    expect(session?.userId).toBe("usr-jharia-01");
    expect(session?.role).toBe("safety_officer"); // Mapped to BFF role
    expect(session?.tenantId).toBe("tenant-jharia-01");
  });

  it("should verify tokens issued by BFF Gateway (with issuer/audience)", () => {
    const userSession: UserSession = {
      userId: "USR-ECL-001",
      email: "engineer@subsense.gov.in",
      name: "ECL Engineer",
      role: "technical_lead",
      tenantId: "OPCO-ECL-01",
      jurisdictionId: "JUR-DGMS-EAST",
      mfaVerified: true,
    };

    const bffToken = signUserToken(userSession);
    const verified = verifyUserToken(bffToken);

    expect(verified).not.toBeNull();
    expect(verified?.userId).toBe("USR-ECL-001");
    expect(verified?.role).toBe("technical_lead");
    expect(verified?.tenantId).toBe("OPCO-ECL-01");
  });

  it("should reject tokens signed with incorrect secret", () => {
    const bogusToken = jwt.sign({ user_id: "intruder" }, "wrong-secret-key");
    const verified = verifyUserToken(bogusToken);
    expect(verified).toBeNull();
  });

  it("should properly normalize tenant IDs across platform aliases", () => {
    expect(normalizeTenantId("tenant-jharia-01")).toBe("tenant-jharia-01");
    expect(normalizeTenantId("OPCO-BCCL-02")).toBe("tenant-jharia-01");
    expect(normalizeTenantId("tenant-raniganj-02")).toBe("tenant-raniganj-02");
    expect(normalizeTenantId("OPCO-ECL-01")).toBe("tenant-raniganj-02");
    expect(normalizeTenantId(null)).toBeNull();
  });
});
