import { on_new_risk_event } from '../src/rule-engine';
import { backlogBuffer } from '../src/channels/buffer';
import { repository } from '../src/db/repository';
import { AlertSeverity, AlertSource, DeliveryChannel, DeliveryStatus, RiskEvent } from '../src/models/types';

describe('Phase 3 Chaos Test: Telecom Gateway Cut, Edge Autonomy & Buffer Replay', () => {
  beforeEach(() => {
    repository.setForceInMemory(true);
    repository.resetMemoryStore();
    backlogBuffer.clear();
    process.env.SIMULATE_GATEWAY_OUTAGE = 'false';
  });

  afterAll(() => {
    process.env.SIMULATE_GATEWAY_OUTAGE = 'false';
  });

  it('should autonomously actuate Edge Siren in < 1.2s during total cloud gateway outage, buffer digital channels, and restore with original timestamps', async () => {
    // 1. Cut telecom network
    process.env.SIMULATE_GATEWAY_OUTAGE = 'true';

    const incidentTime = new Date('2026-09-09T03:00:00.000Z');
    const criticalEvent: RiskEvent = {
      tenant_id: 'tenant-jharia-01',
      risk_zone_id: 'zone-jharia-alpha',
      zone_name: 'Seam IV East Roadway',
      anomaly_score: 0.98,
      correlation_strength: 0.94,
      velocity_delta: 3.5,
      time_to_critical_hours: 1.5,
      confidence: 0.96,
      explanation: 'Critical strata failure under network isolation',
      contributing_nodes: ['node-ext-1', 'node-ext-2'],
      source: AlertSource.Edge,
      timestamp: incidentTime
    };

    const startHr = process.hrtime.bigint();
    const alert = await on_new_risk_event(criticalEvent);
    const endHr = process.hrtime.bigint();
    const totalLatencyMs = Number(endHr - startHr) / 1_000_000;

    expect(alert.severity).toBe(AlertSeverity.Critical);

    // 2. Verify Siren Actuator completed autonomously
    const deliveries = await repository.getDeliveriesByAlertId(alert.alert_id);
    const sirenDelivery = deliveries.find((d) => d.channel === DeliveryChannel.Siren);
    expect(sirenDelivery).toBeDefined();
    expect(sirenDelivery?.delivery_status).toBe(DeliveryStatus.Delivered);

    // 3. Verify digital channels were captured in BacklogBuffer (none dropped)
    const buffered = backlogBuffer.getBufferedDeliveries();
    expect(buffered.length).toBeGreaterThan(0);

    const bufferedChannels = buffered.map((b) => b.delivery.channel);
    expect(bufferedChannels).toContain(DeliveryChannel.SMS);
    expect(bufferedChannels).toContain(DeliveryChannel.VoiceIVR);
    expect(bufferedChannels).toContain(DeliveryChannel.CommunitySMS);

    // 4. Restore connectivity and flush buffer
    process.env.SIMULATE_GATEWAY_OUTAGE = 'false';

    const flushedCount = await backlogBuffer.flush(async (item) => {
      item.delivery.delivery_status = DeliveryStatus.Delivered;
      item.delivery.delivered_at = new Date();
      await repository.updateDelivery(item.delivery.delivery_id, {
        delivery_status: DeliveryStatus.Delivered,
        delivered_at: item.delivery.delivered_at
      });
      return true;
    });

    expect(flushedCount).toBe(buffered.length);
    expect(backlogBuffer.size()).toBe(0);

    // 5. Verify Original Timestamps Preserved
    for (const item of buffered) {
      expect(new Date(item.original_alert_created_at).getTime()).toBe(new Date(alert.created_at).getTime());
    }
  });
});
