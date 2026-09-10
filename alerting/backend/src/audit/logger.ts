import { randomUUID } from 'crypto';
import { repository } from '../db/repository';
import { AlertRecord, AuditLogRecord, AuditTransition } from '../models/types';

/**
 * DGMS-Compliant Append-Only Audit Logger.
 *
 * Captures every state transition (created, merged, escalated, de-escalated, retracted, resolved)
 * with a millisecond-precision timestamp and complete Alert snapshot.
 *
 * Strictly append-only: No UPDATE or DELETE operations are permitted on audit_log.
 */
export const audit_logger = {
  persist_alert_transaction: async (
    alert: AlertRecord,
    transition: AuditTransition = 'created',
    metadata?: Record<string, any>
  ): Promise<AuditLogRecord> => {
    // Make a pure immutable snapshot of the alert
    const snapshot = JSON.parse(JSON.stringify(alert));

    const auditRecord: AuditLogRecord = {
      log_id: randomUUID(),
      alert_id: alert.alert_id,
      transition,
      timestamp: new Date(),
      snapshot,
      metadata: metadata || null
    };

    await repository.insertAuditLog(auditRecord);

    console.log(
      `[DGMS AUDIT LOG] Transition '${transition}' recorded for alert ${alert.alert_id} at ${auditRecord.timestamp.toISOString()}`
    );

    return auditRecord;
  },

  get_alert_history: async (alert_id: string): Promise<AuditLogRecord[]> => {
    return repository.getAuditLogs(alert_id);
  },

  get_all_audit_logs: async (): Promise<AuditLogRecord[]> => {
    return repository.getAuditLogs();
  }
};
