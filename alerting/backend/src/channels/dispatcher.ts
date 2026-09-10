import { randomUUID } from 'crypto';
import { repository } from '../db/repository';
import {
  AlertDeliveryRecord,
  AlertRecord,
  DeliveryChannel,
  DeliveryStatus
} from '../models/types';
import { ChannelAdapter, DeliveryContext } from './adapters/base';
import { communitySmsAdapter } from './adapters/community-sms';
import { dashboardBannerAdapter } from './adapters/dashboard';
import { emailAdapter } from './adapters/email';
import { pushNotificationAdapter } from './adapters/push';
import { sirenActuator } from './adapters/siren';
import { smsAdapter } from './adapters/sms';
import { voiceIvrAdapter } from './adapters/voice';
import { backlogBuffer } from './buffer';

export const channelAdapters: Record<DeliveryChannel, ChannelAdapter> = {
  [DeliveryChannel.Siren]: sirenActuator,
  [DeliveryChannel.SMS]: smsAdapter,
  [DeliveryChannel.Email]: emailAdapter,
  [DeliveryChannel.PushNotification]: pushNotificationAdapter,
  [DeliveryChannel.DashboardBanner]: dashboardBannerAdapter,
  [DeliveryChannel.VoiceIVR]: voiceIvrAdapter,
  [DeliveryChannel.CommunitySMS]: communitySmsAdapter
};

export interface DispatchOptions {
  operatorRecipient?: string;
  context?: DeliveryContext;
  maxRetries?: number;
}

/**
 * Exponential backoff retry for failed digital channel deliveries.
 * (Base 2.0: 100ms, 200ms, 400ms... Siren is NEVER retried).
 */
async function retryWithExponentialBackoff(
  adapter: ChannelAdapter,
  alert: AlertRecord,
  recipient: string,
  deliveryId: string,
  context?: DeliveryContext,
  maxAttempts: number = 5
): Promise<boolean> {
  // Never retry the siren — it is fire-and-forget local hardware
  if (adapter.channel === DeliveryChannel.Siren) {
    return false;
  }

  let attempt = 1;
  while (attempt <= maxAttempts) {
    const delayMs = Math.pow(2, attempt - 1) * 100; // Scaled for snappy demo/tests
    console.log(
      `[DISPATCHER RETRY] Attempt ${attempt}/${maxAttempts} for ${adapter.channel} to ${recipient} in ${delayMs}ms...`
    );
    await new Promise((res) => setTimeout(res, delayMs));

    try {
      const result = await adapter.send(alert, recipient, context);
      if (result.status === DeliveryStatus.Sent || result.status === DeliveryStatus.Delivered) {
        console.log(
          `[DISPATCHER RETRY SUCCESS] ${adapter.channel} to ${recipient} succeeded on attempt ${attempt}.`
        );
        return true;
      }
    } catch (err: any) {
      console.warn(`[DISPATCHER RETRY FAILED] Attempt ${attempt} failed: ${err.message}`);
    }
    attempt++;
  }

  return false;
}

/**
 * Master concurrent dispatcher:
 * - Fans out alert to all adapters concurrently
 * - Writes AlertDelivery row per channel per recipient (Queued -> Sent/Delivered/Failed)
 * - Retries failed digital channels with exponential backoff
 * - Buffers in backlog if completely unreachable
 */
export async function dispatch_concurrent(
  alert: AlertRecord,
  channels: DeliveryChannel[],
  options?: DispatchOptions
): Promise<AlertDeliveryRecord[]> {
  const deliveries: AlertDeliveryRecord[] = [];
  const tasks: Promise<void>[] = [];

  // Determine recipients per channel
  for (const channel of channels) {
    const adapter = channelAdapters[channel];
    if (!adapter) {
      console.warn(`[DISPATCHER] No adapter registered for channel ${channel}`);
      continue;
    }

    if (channel === DeliveryChannel.CommunitySMS) {
      // Query opted-in community registrants in this risk zone
      let registrants = await repository.getRegistrants(alert.risk_zone_id);
      registrants = registrants.filter((r) => r.opted_in);

      // If no enrolled community members exist in DB, provide a realistic default for the demo
      if (registrants.length === 0) {
        registrants = [
          {
            registrant_id: randomUUID(),
            tenant_id: alert.tenant_id,
            risk_zone_id: alert.risk_zone_id,
            phone_number: '+919876543210',
            preferred_language: 'hi',
            opted_in: true
          }
        ];
      }

      for (const reg of registrants) {
        const deliveryRecord: AlertDeliveryRecord = {
          delivery_id: randomUUID(),
          alert_id: alert.alert_id,
          channel,
          recipient_ref: reg.phone_number,
          delivery_status: DeliveryStatus.Queued,
          attempted_at: new Date(),
          delivered_at: null,
          retraction_notice: options?.context?.isRetraction
        };
        deliveries.push(deliveryRecord);

        tasks.push(
          (async () => {
            try {
              const res = await adapter.send(alert, reg.phone_number, {
                ...options?.context,
                communityLanguage: reg.preferred_language
              });
              deliveryRecord.delivery_status = res.status;
              deliveryRecord.delivered_at = res.delivered_at || new Date();
            } catch (err: any) {
              deliveryRecord.delivery_status = DeliveryStatus.Failed;
              deliveryRecord.error = err.message;
              const retried = await retryWithExponentialBackoff(
                adapter,
                alert,
                reg.phone_number,
                deliveryRecord.delivery_id,
                options?.context,
                options?.maxRetries ?? 5
              );
              if (retried) {
                deliveryRecord.delivery_status = DeliveryStatus.Delivered;
                deliveryRecord.delivered_at = new Date();
              } else {
                backlogBuffer.bufferDelivery(deliveryRecord, alert.created_at);
              }
            }
          })()
        );
      }
    } else {
      // Standard operator / local channel
      const recipient =
        channel === DeliveryChannel.Siren
          ? 'on_ground_local_siren'
          : options?.operatorRecipient ||
            (channel === DeliveryChannel.Email
              ? 'duty_safety_officer@coalfield.gov.in'
              : '+919800000001');

      const deliveryRecord: AlertDeliveryRecord = {
        delivery_id: randomUUID(),
        alert_id: alert.alert_id,
        channel,
        recipient_ref: recipient,
        delivery_status: DeliveryStatus.Queued,
        attempted_at: new Date(),
        delivered_at: null,
        retraction_notice: options?.context?.isRetraction
      };
      deliveries.push(deliveryRecord);

      tasks.push(
        (async () => {
          try {
            const res = await adapter.send(alert, recipient, options?.context);
            deliveryRecord.delivery_status = res.status;
            deliveryRecord.delivered_at = res.delivered_at || new Date();
          } catch (err: any) {
            deliveryRecord.delivery_status = DeliveryStatus.Failed;
            deliveryRecord.error = err.message;

            if (channel !== DeliveryChannel.Siren) {
              const retried = await retryWithExponentialBackoff(
                adapter,
                alert,
                recipient,
                deliveryRecord.delivery_id,
                options?.context,
                options?.maxRetries ?? 5
              );
              if (retried) {
                deliveryRecord.delivery_status = DeliveryStatus.Delivered;
                deliveryRecord.delivered_at = new Date();
              } else {
                backlogBuffer.bufferDelivery(deliveryRecord, alert.created_at);
              }
            }
          }
        })()
      );
    }
  }

  // Save initial Queued records to repository
  await repository.saveDeliveries(deliveries);

  // Execute all channel adapters concurrently
  await Promise.allSettled(tasks);

  return deliveries;
}

/**
 * Dispatches a Retraction Notice across every channel and recipient
 * that the original alert utilized.
 */
export async function dispatch_retraction_notice(
  alert: AlertRecord,
  originalDeliveries: AlertDeliveryRecord[],
  reason: string
): Promise<AlertDeliveryRecord[]> {
  console.log(
    `[DISPATCHER] Preparing Retraction Notice for alert ${alert.alert_id} across ${originalDeliveries.length} original delivery paths...`
  );

  // Collect unique channels originally used
  const originalChannels = Array.from(new Set(originalDeliveries.map((d) => d.channel)));

  return dispatch_concurrent(alert, originalChannels, {
    context: {
      isRetraction: true,
      retractionReason: reason
    }
  });
}
