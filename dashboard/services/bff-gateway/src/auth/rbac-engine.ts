import { UserRole, Capability, hasCapability } from "@subsense/shared";
import { UserSession } from "./service";
import { withSystemScope } from "../db/client";

export class RbacEngine {
  static checkCapability(session: UserSession, capability: Capability): boolean {
    return hasCapability(session.role, capability);
  }

  static async verifyRegulatorPermit(
    regulatorUserId: string,
    targetTenantId: string
  ): Promise<boolean> {
    return await withSystemScope(async (client) => {
      const result = await client.query(
        `SELECT 1 FROM regulator_permits 
         WHERE regulator_user_id = $1 
           AND tenant_id = $2 
           AND active = true 
           AND NOW() BETWEEN valid_from AND valid_to;`,
        [regulatorUserId, targetTenantId]
      );
      return result.rows.length > 0;
    });
  }

  static async getPermittedTenantsForRegulator(
    regulatorUserId: string
  ): Promise<string[]> {
    return await withSystemScope(async (client) => {
      const result = await client.query(
        `SELECT tenant_id FROM regulator_permits 
         WHERE regulator_user_id = $1 
           AND active = true 
           AND NOW() BETWEEN valid_from AND valid_to;`,
        [regulatorUserId]
      );
      return result.rows.map((r) => r.tenant_id);
    });
  }
}
