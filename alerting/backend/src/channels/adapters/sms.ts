import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { CircuitBreaker } from '../circuit-breaker';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';

export const smsCircuitBreaker = new CircuitBreaker('SMS_GATEWAY', {
  failureThreshold: 1, // Trip immediately on failure for responsive failover demo
  timeoutMs: 8000,
  cooldownPeriodMs: 15000
});

export class PrimarySmsAdapter {
  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    // Check simulated outage flag
    if (process.env.SIMULATE_SMS_OUTAGE === 'true' || process.env.SIMULATE_GATEWAY_OUTAGE === 'true') {
      console.warn(
        `[PRIMARY SMS GATEWAY] SIMULATE_SMS_OUTAGE is ACTIVE. Simulating 503 Gateway Outage to ${recipient}.`
      );
      throw new Error('503 Service Unavailable: Primary SMS Telecom Gateway Down');
    }

    // Normal simulated transmission
    console.log(
      `[PRIMARY SMS GATEWAY] Sent ${context?.isRetraction ? 'RETRACTION' : alert.severity} SMS to ${recipient} (Zone: ${alert.risk_zone_id.substring(0, 8)})`
    );

    return {
      status: DeliveryStatus.Sent,
      delivered_at: new Date(),
      external_ref: `sms-prim-${Date.now()}`,
      meta: { provider: 'PRIMARY_TELECOM_GATEWAY', recipient }
    };
  }
}

export class SecondarySmsAdapter {
  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    if (process.env.SIMULATE_GATEWAY_OUTAGE === 'true') {
      console.warn(`[SECONDARY SMS GATEWAY] Gateway network offline. Uplink unreachable for ${recipient}.`);
      throw new Error('Network Unreachable: Backup satellite uplink offline');
    }
    console.log(
      `[SECONDARY SMS GATEWAY] >>> FALLBACK ACTIVATED <<< Dispatched ${context?.isRetraction ? 'RETRACTION' : alert.severity} SMS to ${recipient} via Secondary Satellite/GSM route.`
    );

    return {
      status: DeliveryStatus.Sent,
      delivered_at: new Date(),
      external_ref: `sms-sec-${Date.now()}`,
      meta: { provider: 'SECONDARY_FALLBACK_GATEWAY', recipient, failover: true }
    };
  }
}

export class ResilientSmsAdapter implements ChannelAdapter {
  channel = DeliveryChannel.SMS;
  private primary = new PrimarySmsAdapter();
  private secondary = new SecondarySmsAdapter();

  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    const { result, usedSecondary } = await smsCircuitBreaker.execute(
      () => this.primary.send(alert, recipient, context),
      () => this.secondary.send(alert, recipient, context)
    );

    if (usedSecondary) {
      console.log(
        `[RESILIENT SMS DISPATCHER] Delivered to ${recipient} through SECONDARY route within failover window.`
      );
    }

    return result;
  }
}

export const smsAdapter = new ResilientSmsAdapter();
