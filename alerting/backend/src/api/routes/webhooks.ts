import { Router, Request, Response } from 'express';
import { repository } from '../../db/repository';
import { on_new_risk_event } from '../../rule-engine';
import { DeliveryStatus, RiskEvent, AlertSource } from '../../models/types';

export const webhooksRouter = Router();

/**
 * POST /webhooks/sms-gateway/status
 * Inbound status update callback from telecom SMS aggregator
 */
webhooksRouter.post('/sms-gateway/status', async (req: Request, res: Response): Promise<void> => {
  try {
    const { delivery_id, status, delivered_at } = req.body;

    if (!delivery_id || !status) {
      res.status(400).json({ error: 'delivery_id and status are required' });
      return;
    }

    const delivery = await repository.findDeliveryById(delivery_id);
    if (!delivery) {
      res.status(404).json({ error: `AlertDelivery with id ${delivery_id} not found` });
      return;
    }

    const targetStatus =
      status === 'Delivered'
        ? DeliveryStatus.Delivered
        : status === 'Failed'
        ? DeliveryStatus.Failed
        : DeliveryStatus.Sent;

    const updated = await repository.updateDelivery(delivery_id, {
      delivery_status: targetStatus,
      delivered_at: delivered_at ? new Date(delivered_at) : new Date()
    });

    console.log(
      `[INBOUND WEBHOOK] SMS status updated for delivery ${delivery_id}: ${targetStatus}`
    );

    res.json({ message: 'SMS delivery status updated', delivery: updated });
  } catch (error: any) {
    console.error('[WEBHOOK ERROR] Failed to process SMS status callback:', error);
    res.status(500).json({ error: 'Failed to process webhook', details: error.message });
  }
});

/**
 * POST /webhooks/voice-gateway/status
 * Inbound status update callback from Voice IVR provider
 */
webhooksRouter.post('/voice-gateway/status', async (req: Request, res: Response): Promise<void> => {
  try {
    const { delivery_id, status, duration_seconds, dtmf_response, delivered_at } = req.body;

    if (!delivery_id || !status) {
      res.status(400).json({ error: 'delivery_id and status are required' });
      return;
    }

    const delivery = await repository.findDeliveryById(delivery_id);
    if (!delivery) {
      res.status(404).json({ error: `AlertDelivery with id ${delivery_id} not found` });
      return;
    }

    const targetStatus =
      status === 'Delivered' || status === 'completed'
        ? DeliveryStatus.Delivered
        : status === 'failed'
        ? DeliveryStatus.Failed
        : DeliveryStatus.Sent;

    const updated = await repository.updateDelivery(delivery_id, {
      delivery_status: targetStatus,
      delivered_at: delivered_at ? new Date(delivered_at) : new Date()
    });

    console.log(
      `[INBOUND WEBHOOK] Voice IVR status updated for delivery ${delivery_id}: ${targetStatus} (Duration: ${duration_seconds ?? 'N/A'}s, DTMF: '${dtmf_response ?? 'N/A'}')`
    );

    res.json({
      message: 'Voice IVR delivery status updated',
      delivery: updated,
      metadata: { duration_seconds, dtmf_response }
    });
  } catch (error: any) {
    console.error('[WEBHOOK ERROR] Failed to process Voice IVR status callback:', error);
    res.status(500).json({ error: 'Failed to process webhook', details: error.message });
  }
});

/**
 * POST /webhooks/risk-events
 * POST /api/v1/webhooks/risk-events
 * Public / API-Key protected webhook endpoint for ingesting AI/ML risk events
 */
webhooksRouter.post('/risk-events', async (req: Request, res: Response): Promise<void> => {
  try {
    const raw = req.body;
    if (!raw) {
      res.status(400).json({ error: 'Request body cannot be empty' });
      return;
    }

    const event: RiskEvent = {
      tenant_id: raw.tenant_id || 'tenant-jharia-01',
      risk_zone_id: raw.risk_zone_id || raw.zone_id || '11111111-1111-1111-1111-111111111111',
      anomaly_score: Number(raw.anomaly_score ?? 0.85),
      correlation_strength: Number(raw.correlation_strength ?? 0.80),
      confidence: Number(raw.confidence ?? 0.85),
      source: raw.source ? (raw.source === 'Edge' ? AlertSource.Edge : AlertSource.Cloud) : AlertSource.Cloud,
      explanation: raw.explanation || raw.plain_language_summary || 'AI/ML Risk Event Triggered',
      contributing_nodes: raw.contributing_nodes || (raw.node_id ? [raw.node_id] : ['SS-PANEL7-N042']),
      contributing_sensors: raw.contributing_sensors || ['tilt_deg'],
      time_to_critical_hours: raw.time_to_critical_hours ?? raw.time_to_critical ?? null,
      progression_rate: raw.progression_rate ?? raw.velocity_delta ?? 0.2,
      velocity_delta: raw.velocity_delta ?? 0.2,
      timestamp: raw.timestamp || new Date().toISOString()
    };

    const alert = await on_new_risk_event(event);
    console.log(`[INBOUND WEBHOOK] Ingested risk event for zone ${event.risk_zone_id} -> Alert ${alert.alert_id} (${alert.severity})`);
    res.status(201).json(alert);
  } catch (error: any) {
    console.error('[WEBHOOK ERROR] Failed to process risk event webhook:', error);
    res.status(500).json({ error: 'Failed to process risk event', details: error.message });
  }
});
