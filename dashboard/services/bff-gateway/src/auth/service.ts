import jwt from "jsonwebtoken";
import { UserRole } from "@subsense/shared";

const JWT_SECRET = process.env.JWT_SECRET || "subsense-safety-critical-jwt-secret-key-2026";

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
    const decoded = jwt.verify(token, JWT_SECRET, {
      issuer: "subsense-auth-service",
      audience: "subsense-layer6-clients",
    }) as UserSession;
    return decoded;
  } catch (err) {
    return null;
  }
}
