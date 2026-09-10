import { Router, Request, Response } from 'express';
import { repository } from '../../db/repository';
import { authenticateToken } from '../../security/auth';
import { UserRole } from '../../models/types';

export const auditRouter = Router();

function escapeCsv(val: any): string {
  if (val === null || val === undefined) return '""';
  const str = typeof val === 'object' ? JSON.stringify(val) : String(val);
  return `"${str.replace(/"/g, '""')}"`;
}

/**
 * GET /api/v1/audit/export
 * One-click extraction of the append-only DGMS audit log into an official CSV report.
 * Supports date filtering and enforces tenant scoping for Mine Safety Officers.
 */
auditRouter.get('/export', authenticateToken, async (req: Request, res: Response): Promise<void> => {
  try {
    const user = req.user;
    let tenantId = req.query.tenant_id as string | undefined;

    // Enforce tenant scoping for Mine Safety Officers
    if (user && user.role === UserRole.MineSafetyOfficer && user.tenant_id) {
      tenantId = user.tenant_id;
    }

    const startDate = req.query.start_date ? new Date(req.query.start_date as string) : undefined;
    const endDate = req.query.end_date ? new Date(req.query.end_date as string) : undefined;

    const logs = await repository.getAuditLogs({
      tenant_id: tenantId,
      start_date: startDate,
      end_date: endDate
    });

    const headers = [
      'Log ID',
      'Alert ID',
      'Tenant ID',
      'Risk Zone ID',
      'Transition',
      'Timestamp (UTC)',
      'Severity',
      'Status',
      'Confidence Score',
      'Time To Critical (Hours)',
      'Contributing Nodes Count',
      'Trigger Narrative / Explanation',
      'Human Sign-Off / Operator',
      'Metadata'
    ];

    const rows = logs.map((l) => {
      const snap = l.snapshot || {};
      const meta = l.metadata || {};
      const operatorSignOff = meta.human_sign_off || meta.operator_id || 'System_Automated';

      return [
        escapeCsv(l.log_id),
        escapeCsv(l.alert_id),
        escapeCsv(snap.tenant_id || 'N/A'),
        escapeCsv(snap.risk_zone_id || 'N/A'),
        escapeCsv(l.transition.toUpperCase()),
        escapeCsv(new Date(l.timestamp).toISOString()),
        escapeCsv(snap.severity || 'N/A'),
        escapeCsv(snap.status || 'N/A'),
        escapeCsv(snap.confidence_score !== undefined ? snap.confidence_score : 'N/A'),
        escapeCsv(snap.time_to_critical_hours !== undefined ? snap.time_to_critical_hours : 'N/A'),
        escapeCsv(snap.contributing_nodes ? snap.contributing_nodes.length : 0),
        escapeCsv(snap.explainability?.trigger_narrative || snap.explanation || 'N/A'),
        escapeCsv(operatorSignOff),
        escapeCsv(meta)
      ].join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\r\n');
    const timestampStr = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `dgms_annual_safety_audit_${tenantId || 'all_tenants'}_${timestampStr}.csv`;

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.status(200).send(csvContent);
  } catch (error: any) {
    console.error('[AUDIT EXPORT ERROR] Failed to generate DGMS CSV export:', error);
    res.status(500).json({ error: 'Failed to generate DGMS safety audit CSV export', details: error.message });
  }
});
