import * as crypto from "crypto";
import { withSystemScope } from "../db/client";

export interface AuditEntryInput {
  tenantId: string;
  userId: string;
  action: string;
  details: Record<string, any>;
}

export class AuditLedger {
  /**
   * Appends an entry to the tamper-proof cryptographic audit ledger.
   * Computes SHA-256 hash chaining against the latest record in the database.
   */
  static async record(entry: AuditEntryInput): Promise<string> {
    return await withSystemScope(async (client) => {
      // Get the latest block's hash
      const latestRes = await client.query(
        "SELECT record_hash FROM tamper_proof_audit_ledger ORDER BY timestamp DESC LIMIT 1;"
      );
      const prevHash = latestRes.rows[0]?.record_hash || "0000000000000000000000000000000000000000000000000000000000000000";

      const id = `AUDIT-${Date.now()}-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;
      const timestamp = new Date().toISOString();

      const hashPayload = `${prevHash}|${id}|${timestamp}|${entry.tenantId}|${entry.userId}|${entry.action}|${JSON.stringify(entry.details)}`;
      const recordHash = crypto.createHash("sha256").update(hashPayload).digest("hex");

      await client.query(
        `INSERT INTO tamper_proof_audit_ledger (id, timestamp, tenant_id, user_id, action, details_json, record_hash, prev_hash)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8);`,
        [id, timestamp, entry.tenantId, entry.userId, entry.action, JSON.stringify(entry.details), recordHash, prevHash]
      );

      return recordHash;
    });
  }

  static async verifyIntegrity(): Promise<boolean> {
    return await withSystemScope(async (client) => {
      const res = await client.query(
        "SELECT * FROM tamper_proof_audit_ledger ORDER BY timestamp ASC;"
      );
      const rows = res.rows;
      if (rows.length <= 1) return true;

      for (let i = 1; i < rows.length; i++) {
        const prev = rows[i - 1];
        const curr = rows[i];
        if (curr.prev_hash !== prev.record_hash) {
          return false;
        }
      }
      return true;
    });
  }
}
