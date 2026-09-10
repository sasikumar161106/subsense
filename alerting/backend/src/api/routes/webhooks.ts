import { Router, Request, Response } from 'express';
import { repository } from '../../db/repository';
import { DeliveryStatus } from '../../models/types';

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
