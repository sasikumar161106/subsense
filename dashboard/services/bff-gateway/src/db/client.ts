import { PGlite } from "@electric-sql/pglite";
import * as fs from "fs";
import * as path from "path";

export interface TenantSessionContext {
  tenantId: string | null;
  userId: string;
  isRegulator?: boolean;
}

export interface QueryResult<T = any> {
  rows: T[];
  affectedRows?: number;
}

export interface ScopedDbClient {
  query<T = any>(sql: string, params?: any[]): Promise<QueryResult<T>>;
}

let dbInstance: PGlite | null = null;

export async function getDb(): Promise<PGlite> {
  if (!dbInstance) {
    dbInstance = new PGlite();
    await initSchema(dbInstance);
  }
  return dbInstance;
}

export async function initSchema(db: PGlite): Promise<void> {
  const schemaPath = path.join(__dirname, "schema.sql");
  const schemaSql = fs.readFileSync(schemaPath, "utf-8");
  await db.exec(schemaSql);
}

/**
 * MANDATORY QUERY INTERCEPTOR
 * Executes database operations within a strict transaction context where session variables
 * app.current_tenant_id, app.current_user_id, and app.is_regulator are injected automatically.
 * Row-Level Security policies read these variables so developers never have to write manual tenant filters.
 */
export async function withTenantScope<T>(
  context: TenantSessionContext,
  operation: (client: ScopedDbClient) => Promise<T>
): Promise<T> {
  const db = await getDb();

  const tenantId = context.tenantId || "";
  const userId = context.userId || "ANONYMOUS";
  const isRegulator = context.isRegulator ? "true" : "false";

  // Use a transaction block to enforce local session variables
  await db.query("BEGIN;");
  try {
    // Switch to unprivileged application role to enforce Row Level Security
    await db.query("SET ROLE subsense_app_user;");
    await db.query(
      "SELECT set_config('app.current_tenant_id', $1, true), set_config('app.current_user_id', $2, true), set_config('app.is_regulator', $3, true);",
      [tenantId, userId, isRegulator]
    );

    const scopedClient: ScopedDbClient = {
      query: async <R = any>(sql: string, params: any[] = []) => {
        const result = await db.query<R>(sql, params);
        return {
          rows: result.rows,
          affectedRows: result.affectedRows,
        };
      },
    };

    const result = await operation(scopedClient);
    await db.query("RESET ROLE;");
    await db.query("COMMIT;");
    return result;
  } catch (error) {
    try {
      await db.query("RESET ROLE;");
    } catch {}
    await db.query("ROLLBACK;");
    throw error;
  }
}

/**
 * System-level scoped operation used only for bootstrapping/seeding
 */
export async function withSystemScope<T>(
  operation: (client: ScopedDbClient) => Promise<T>
): Promise<T> {
  const db = await getDb();
  await db.query("BEGIN;");
  try {
    // Enable system bypass
    await db.query(
      "SELECT set_config('app.is_system', 'true', true), set_config('app.current_tenant_id', '', true), set_config('app.current_user_id', 'SYSTEM', true), set_config('app.is_regulator', 'false', true);"
    );

    const scopedClient: ScopedDbClient = {
      query: async <R = any>(sql: string, params: any[] = []) => {
        const result = await db.query<R>(sql, params);
        return {
          rows: result.rows,
          affectedRows: result.affectedRows,
        };
      },
    };

    const result = await operation(scopedClient);
    await db.query("COMMIT;");
    return result;
  } catch (error) {
    await db.query("ROLLBACK;");
    throw error;
  }
}
