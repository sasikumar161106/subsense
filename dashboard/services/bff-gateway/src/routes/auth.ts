import { FastifyPluginAsync } from "fastify";
import { withSystemScope } from "../db/client";
import { signUserToken, UserSession } from "../auth/service";
import { verifyMfaToken, generateMfaSecret } from "../auth/mfa";
import { ROLE_DEFINITIONS, UserRole } from "@subsense/shared";

export const authRoutes: FastifyPluginAsync = async (fastify) => {
  fastify.get("/api/v1/auth/roles", async () => {
    return { roles: ROLE_DEFINITIONS };
  });

  fastify.post<{
    Body: {
      userId?: string;
      email?: string;
      role?: UserRole;
      mfaCode?: string;
    };
  }>("/api/v1/auth/login", async (request, reply) => {
    const { userId, role, mfaCode } = request.body;

    return await withSystemScope(async (client) => {
      let userQuery = "SELECT * FROM users WHERE 1=1";
      const params: any[] = [];

      if (userId) {
        userQuery += " AND id = $1";
        params.push(userId);
      } else if (role) {
        userQuery += " AND role = $1 LIMIT 1";
        params.push(role);
      } else {
        // default to Mine Operator for quick start
        userQuery += " AND role = 'mine_operator' LIMIT 1";
      }

      const res = await client.query(userQuery, params);
      if (res.rows.length === 0) {
        return reply.status(401).send({ error: "User not found" });
      }

      const user = res.rows[0];

      // Verify MFA if mfaCode is passed or required
      if (user.mfa_enabled) {
        if (!mfaCode || !verifyMfaToken(mfaCode, user.mfa_secret)) {
          return reply.status(400).send({ error: "MFA code is required and must be valid" });
        }
      } else if (mfaCode && !verifyMfaToken(mfaCode, user.mfa_secret)) {
        return reply.status(400).send({ error: "Invalid MFA verification token" });
      }

      const session: UserSession = {
        userId: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        tenantId: user.tenant_id,
        jurisdictionId: user.jurisdiction_id,
        mfaVerified: true,
      };

      const token = signUserToken(session);

      return {
        token,
        session,
        roleMetadata: ROLE_DEFINITIONS[user.role as UserRole],
      };
    });
  });

  fastify.post<{
    Body: {
      userId: string;
      mfaToken: string;
    };
  }>("/api/v1/auth/mfa/verify", async (request, reply) => {
    const { userId, mfaToken } = request.body;

    return await withSystemScope(async (client) => {
      const res = await client.query("SELECT * FROM users WHERE id = $1;", [userId]);
      if (res.rows.length === 0) {
        return reply.status(404).send({ error: "User not found" });
      }

      const user = res.rows[0];
      const valid = verifyMfaToken(mfaToken, user.mfa_secret);

      if (!valid) {
        return reply.status(400).send({ valid: false, error: "Invalid TOTP token" });
      }

      return { valid: true, message: "MFA verified successfully" };
    });
  });

  fastify.get("/api/v1/auth/me", async (request, reply) => {
    const session = (request as any).userSession as UserSession;
    if (!session) {
      return reply.status(401).send({ error: "Unauthenticated" });
    }
    return {
      session,
      roleMetadata: ROLE_DEFINITIONS[session.role],
    };
  });
};
