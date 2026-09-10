import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';

export class PushNotificationAdapter implements ChannelAdapter {
  channel = DeliveryChannel.PushNotification;

  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    if (process.env.SIMULATE_GATEWAY_OUTAGE === 'true') {
      throw new Error('Network Unreachable: FCM Cloud Gateway Unreachable');
    }
    const isRetraction = context?.isRetraction;

    // FCM payload simulation
    const fcmMessage = {
      to: recipient, // device token or operator topic
      priority: 'high',
      notification: {
        title: isRetraction ? 'Subsidence Alert Retracted' : `SubSense ${alert.severity} Alert`,
        body: isRetraction
          ? `Alert for Zone ${alert.risk_zone_id.substring(0, 8)} has been cancelled.`
          : alert.explanation,
        sound: alert.severity === 'Critical' ? 'emergency_siren.wav' : 'default',
        channelId: 'emergency_subsidence_channel'
      },
      data: {
        alert_id: alert.alert_id,
        severity: alert.severity,
        risk_zone_id: alert.risk_zone_id,
        time_to_critical: String(alert.time_to_critical_hours ?? 'N/A'),
        is_retraction: String(Boolean(isRetraction))
      }
    };

    const messageId = `projects/subsense-fcm/messages/msg-${Date.now()}`;

    console.log(
      `[FCM PUSH ADAPTER] High-priority push dispatched to device ${recipient.substring(0, 16)}... (FCM Message ID: ${messageId})`
    );

    return {
      status: DeliveryStatus.Sent,
      delivered_at: new Date(),
      external_ref: messageId,
      meta: { fcm_ticket: messageId, payload: fcmMessage }
    };
  }
}

export const pushNotificationAdapter = new PushNotificationAdapter();
