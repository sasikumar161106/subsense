import { randomUUID } from 'crypto';
import { AlertDeliveryRecord, AlertRecord, DeliveryChannel, DeliveryStatus } from '../models/types';

export const deliveryDispatchHistory: AlertDeliveryRecord[] = [];

/**
 * Notification dispatcher stub for Phase 1.
 * Prepares concurrent delivery records across all active channels for the given alert.
 */
export const notification_dispatcher = {
  dispatch_concurrent: async (
    alert: AlertRecord,
    channels: DeliveryChannel[],
    recipient_ref: string = 'control_room_duty_officer'
  ): Promise<AlertDeliveryRecord[]> => {
    const deliveries: AlertDeliveryRecord[] = channels.map((channel) => {
      const record: AlertDeliveryRecord = {
        delivery_id: randomUUID(),
        alert_id: alert.alert_id,
        channel,
        recipient_ref,
        delivery_status: DeliveryStatus.Queued,
        attempted_at: new Date(),
        delivered_at: null
      };
      deliveryDispatchHistory.push(record);
      return record;
    });

    console.log(
      `[NOTIFICATION DISPATCHER] Dispatched ${channels.length} delivery channels for alert ${alert.alert_id}: [${channels.join(', ')}]`
    );

    return deliveries;
  }
};
