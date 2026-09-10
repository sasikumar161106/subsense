import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';
import { wsManager } from './dashboard';

export class SirenActuator implements ChannelAdapter {
  channel = DeliveryChannel.Siren;

  async send(
    alert: AlertRecord,
    recipient: string = 'on_ground_local_siren',
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    const startTime = performance.now();

    // Autonomous Edge GPIO simulation:
    // This executes locally on the gateway / edge node hardware
    const zoneId = alert.risk_zone_id;
    console.log(
      `[EDGE GPIO SIREN] >>> HARDWARE GPIO PIN HIGH: Actuating on-ground sirens & strobes for zone ${zoneId} <<<`
    );

    // Non-blocking dashboard notice: Broadcast siren ACTIVE event on local WebSocket
    // Must NOT depend on network succeeding
    try {
      wsManager.broadcast('SIREN_ACTIVE', {
        zone_id: zoneId,
        alert_id: alert.alert_id,
        severity: alert.severity,
        action: context?.isRetraction ? 'SIREN_RESET' : 'SIREN_TRIGGERED',
        timestamp: new Date().toISOString()
      });
    } catch (wsErr) {
      // Intentionally ignore: Edge siren NEVER depends on network
      console.warn('[EDGE GPIO SIREN] Local WebSocket notification skipped; hardware siren fired autonomously.');
    }

    const durationMs = Number((performance.now() - startTime).toFixed(2));

    console.log(
      `[EDGE GPIO SIREN] Siren actuation completed in ${durationMs}ms (Must be < 1200ms: ${durationMs < 1200 ? 'PASS' : 'FAIL'})`
    );

    return {
      status: DeliveryStatus.Delivered,
      delivered_at: new Date(),
      external_ref: `gpio-siren-${zoneId.substring(0, 8)}`,
      duration_ms: durationMs,
      meta: {
        gpio_pin: 18,
        mode: 'AUTONOMOUS_EDGE',
        duration_ms: durationMs
      }
    };
  }
}

export const sirenActuator = new SirenActuator();
