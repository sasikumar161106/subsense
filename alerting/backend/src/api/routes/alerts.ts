import { Router, Request, Response } from 'express';
import * as crypto from 'crypto';
import { repository } from '../../db/repository';
import { on_new_risk_event } from '../../rule-engine';
import { deescalate_alert } from '../../rule-engine/deescalation';
import { dispatch_retraction_notice } from '../../channels/dispatcher';
import { audit_logger } from '../../audit/logger';
import { FeedbackVerdict, RiskEvent, UserRole } from '../../models/types';
import { authenticateToken } from '../../security/auth';

export const alertsRouter = Router();
alertsRouter.use(authenticateToken);

/**
 * POST /api/v1/alerts
 * Ingest a RiskEvent from AI/ML Layer and process through Rule Engine
 */
alertsRouter.post('/', async (req: Request, res: Response): Promise<void> => {
  try {
    const event: RiskEvent = req.body;

    // Validate required fields
    if (
      !event.risk_zone_id ||
      !event.tenant_id ||
      event.anomaly_score === undefined ||
      event.correlation_strength === undefined ||
      event.confidence === undefined ||
      !event.source
    ) {
      res.status(400).json({
        error:
          'Missing required RiskEvent fields: risk_zone_id, tenant_id, anomaly_score, correlation_strength, confidence, source'
      });
      return;
    }

    const alert = await on_new_risk_event(event);
    res.status(201).json(alert);
  } catch (error: any) {
    console.error('[API ERROR] Failed to process RiskEvent:', error);
    res.status(500).json({ error: 'Failed to process risk event', details: error.message });
  }
});

/**
 * GET /api/v1/alerts
 * Filter by zone_id (or risk_zone_id), severity, status, date range
 */
alertsRouter.get('/', async (req: Request, res: Response): Promise<void> => {
  try {
    const { zone_id, risk_zone_id, severity, status, start_date, end_date } = req.query;

    const filter: any = {};
    if (zone_id || risk_zone_id) {
      filter.risk_zone_id = (risk_zone_id || zone_id) as string;
    }
    if (severity) filter.severity = severity as string;
    if (status) filter.status = status as string;
    if (start_date) filter.start_date = new Date(start_date as string);
    if (end_date) filter.end_date = new Date(end_date as string);

    // Enforce tenant scoping: MineSafetyOfficer only sees their own tenant
    if (req.user && req.user.role === UserRole.MineSafetyOfficer && req.user.tenant_id) {
      filter.tenant_id = req.user.tenant_id;
    } else if (req.query.tenant_id) {
      filter.tenant_id = req.query.tenant_id as string;
    }

    const alerts = await repository.findAlerts(filter);
    res.json(alerts);
  } catch (error: any) {
    console.error('[API ERROR] Failed to fetch alerts:', error);
    res.status(500).json({ error: 'Failed to fetch alerts', details: error.message });
  }
});

/**
 * GET /api/v1/alerts/:id
 * Retrieve full alert details
 */
alertsRouter.get('/:id', async (req: Request, res: Response): Promise<void> => {
  try {
    const alertId = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
    const alert = await repository.findAlertById(alertId);
    if (!alert) {
      res.status(404).json({ error: `Alert not found with id: ${alertId}` });
      return;
    }

    // Verify tenant scoping for Mine Safety Officers
    if (req.user && req.user.role === UserRole.MineSafetyOfficer && req.user.tenant_id) {
      if (alert.tenant_id !== req.user.tenant_id) {
        res.status(403).json({
          error: `Tenant Access Denied: Alert belongs to tenant '${alert.tenant_id}', but operator is locked to '${req.user.tenant_id}'.`
        });
        return;
      }
    }

    const auditHistory = await audit_logger.get_alert_history(alertId);
    const deliveries = await repository.getDeliveriesByAlertId(alertId);

    res.json({
      ...alert,
      deliveries,
      audit_history: auditHistory
    });
  } catch (error: any) {
    console.error('[API ERROR] Failed to fetch alert detail:', error);
    res.status(500).json({ error: 'Failed to fetch alert details', details: error.message });
  }
});

/**
 * GET /api/v1/alerts/:id/deliveries
 * Delivery audit trail per channel
 */
alertsRouter.get('/:id/deliveries', async (req: Request, res: Response): Promise<void> => {
  try {
    const alertId = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
    const deliveries = await repository.getDeliveriesByAlertId(alertId);
    res.json(deliveries);
  } catch (error: any) {
    console.error('[API ERROR] Failed to fetch deliveries:', error);
    res.status(500).json({ error: 'Failed to fetch alert deliveries', details: error.message });
  }
});

/**
 * POST /api/v1/alerts/:id/feedback
 * Operator submits feedback verdict: Confirmed, FalsePositive, Unclear, HardwareDefect.
 * Cryptographically linked to the alert via SHA-256 hash.
 */
alertsRouter.post('/:id/feedback', async (req: Request, res: Response): Promise<void> => {
  try {
    const alertId = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
    const { operator_id, verdict, notes } = req.body;

    if (!operator_id || !verdict) {
      res.status(400).json({ error: 'operator_id and verdict are required' });
      return;
    }

    // Regulators have read-only audit access
    if (req.user?.role === UserRole.RegulatorDGMS) {
      res.status(403).json({
        error: 'Forbidden: Regulator/DGMS role has read-only access and cannot submit operator feedback.'
      });
      return;
    }

    const alert = await repository.findAlertById(alertId);
    if (!alert) {
      res.status(404).json({ error: `Alert not found with id: ${alertId}` });
      return;
    }

    // Tenant check
    if (req.user && req.user.role === UserRole.MineSafetyOfficer && req.user.tenant_id) {
      if (alert.tenant_id !== req.user.tenant_id) {
        res.status(403).json({
          error: `Tenant Access Denied: Cannot submit feedback for alert belonging to another tenant '${alert.tenant_id}'.`
        });
        return;
      }
    }

    // Cryptographic link: hash of alert_id + raw payload
    const rawPayload = JSON.stringify({ operator_id, verdict, notes: notes || '' });
    const feedbackHash = crypto
      .createHash('sha256')
      .update(`${alertId}:${rawPayload}`)
      .digest('hex');

    const feedback = await repository.createFeedback({
      feedback_id: '',
      alert_id: alertId,
      operator_id,
      verdict,
      notes: notes || null,
      feedback_hash: feedbackHash,
      submitted_at: new Date()
    });

    console.log(
      `[OPERATOR FEEDBACK] Alert ${alertId} logged verdict ${verdict}. Crypto hash: ${feedbackHash.substring(0, 16)}...`
    );

    res.status(201).json({ feedback, alert });
  } catch (error: any) {
    console.error('[API ERROR] Failed to submit feedback:', error);
    res.status(500).json({ error: 'Failed to submit feedback', details: error.message });
  }
});

/**
 * POST /api/v1/alerts/:id/retract
 * Issue an explicit de-escalation/retraction notice.
 * Strictly enforced: Only allowed after a FalsePositive or HardwareDefect verdict has been recorded.
 * Dispatches a Retraction Notice through every channel the original alert used.
 */
alertsRouter.post('/:id/retract', async (req: Request, res: Response): Promise<void> => {
  try {
    const alertId = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
    const { reason, operator_id } = req.body;

    // Regulators have read-only audit access
    if (req.user?.role === UserRole.RegulatorDGMS) {
      res.status(403).json({
        error: 'Forbidden: Regulator/DGMS role has read-only access and cannot retract alerts.'
      });
      return;
    }

    const alert = await repository.findAlertById(alertId);
    if (!alert) {
      res.status(404).json({ error: `Alert not found with id: ${alertId}` });
      return;
    }

    // Tenant check
    if (req.user && req.user.role === UserRole.MineSafetyOfficer && req.user.tenant_id) {
      if (alert.tenant_id !== req.user.tenant_id) {
        res.status(403).json({
          error: `Tenant Access Denied: Cannot retract alert belonging to another tenant '${alert.tenant_id}'.`
        });
        return;
      }
    }

    // Check pre-condition: Must have prior FalsePositive or HardwareDefect feedback
    const feedbacks = alert.feedbacks || [];
    const hasPriorInvalidation = feedbacks.some(
      (f) =>
        f.verdict === FeedbackVerdict.FalsePositive ||
        f.verdict === FeedbackVerdict.HardwareDefect
    );

    if (!hasPriorInvalidation) {
      res.status(400).json({
        error:
          'Retraction rejected: An alert can only be retracted after a FalsePositive or HardwareDefect feedback verdict has been recorded.'
      });
      return;
    }

    const deescalation = deescalate_alert(alert, reason || 'False alarm verified by operator feedback');
    const updated = await repository.updateAlert(alert.alert_id, deescalation.updatedAlert);

    // Fetch original deliveries to mirror all channels
    const originalDeliveries = await repository.getDeliveriesByAlertId(alertId);

    // Dispatch retraction notice to all original channels
    const retractionDeliveries = await dispatch_retraction_notice(
      updated,
      originalDeliveries,
      deescalation.reason
    );

    await audit_logger.persist_alert_transaction(updated, 'retracted', {
      operator_id: operator_id || 'authorized_operator',
      reason: deescalation.reason,
      retraction_deliveries_count: retractionDeliveries.length
    });

    res.json({
      alert: updated,
      retraction_deliveries: retractionDeliveries
    });
  } catch (error: any) {
    console.error('[API ERROR] Failed to retract alert:', error);
    res.status(500).json({ error: 'Failed to retract alert', details: error.message });
  }
});
