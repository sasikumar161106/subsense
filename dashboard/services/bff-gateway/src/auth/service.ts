import jwt from "jsonwebtoken";
import { UserRole } from "@subsense/shared";

const JWT_SECRET = process.env.JWT_SECRET || "subsense-jwt-safety-compliance-secret-key-2026";

export interface UserSession {
  userId: string;
  email: string;
  name: string;
  role: UserRole;
  tenantId: string | null;
  jurisdictionId: string | null;
  mfaVerified: boolean;
}

export function signUserToken(user: UserSession): string {
  return jwt.sign(user, JWT_SECRET, {
    expiresIn: "12h",
    issuer: "subsense-auth-service",
    audience: "subsense-layer6-clients",
  });
}

export function verifyUserToken(token: string): UserSession | null {
  try {
    let decoded: any = null;
    try {
      decoded = jwt.verify(token, JWT_SECRET, {
        issuer: "subsense-auth-service",
        audience: "subsense-layer6-clients",
      });
    } catch {
      // Fallback verification for tokens signed by Alert_System
      decoded = jwt.verify(token, JWT_SECRET);
    }
    if (!decoded) return null;

    // Harmonize role mapping between alerting and bff
    let role = (decoded.role || "safety_officer") as UserRole;
    if (decoded.role === "mine_safety_officer") role = "safety_officer" as UserRole;
    if (decoded.role === "regulator_dgms") role = "regulator" as UserRole;
    if (decoded.role === "strata_control_engineer") role = "technical_lead" as UserRole;

    return {
      userId: decoded.userId || decoded.user_id || "USR-OPERATOR",
      email: decoded.email || `${decoded.username || "operator"}@subsense.gov.in`,
      name: decoded.name || decoded.username || "Mine Safety Officer",
      role,
      tenantId: decoded.tenantId || decoded.tenant_id || null,
      jurisdictionId: decoded.jurisdictionId || "JUR-DGMS-EAST",
      mfaVerified: decoded.mfaVerified ?? true,
    };
  } catch (err) {
    return null;
  }
}

/**
 * Normalizes tenant IDs across platform components (Alerting, BFF, GIS, AI/ML)
 */
export function normalizeTenantId(rawTenant: string | null | undefined): string | null {
  if (!rawTenant) return null;
  const t = rawTenant.trim();
  if (t === "tenant-jharia-01" || t === "OPCO-BCCL-02") return "tenant-jharia-01";
  if (t === "tenant-raniganj-02" || t === "OPCO-ECL-01") return "tenant-raniganj-02";
  return t;
}

