import { sirenActuator } from '../src/channels/adapters/siren';
import { smsAdapter, smsCircuitBreaker } from '../src/channels/adapters/sms';
import { emailAdapter, dailyDigestQueue } from '../src/channels/adapters/email';
import { communitySmsAdapter, COMMUNITY_TEMPLATES } from '../src/channels/adapters/community-sms';
import { backlogBuffer } from '../src/channels/buffer';
import {
  AlertRecord,
  AlertSeverity,
  AlertSource,
  AlertStatus,
  DeliveryChannel,
  DeliveryStatus
} from '../src/models/types';

describe('Phase 2 Channel Adapters & Resilience', () => {
  const sampleAlert: AlertRecord = {
    alert_id: 'test-alert-1',
    tenant_id: 'tenant-1',
    risk_zone_id: 'zone-alpha-1',
    severity: AlertSeverity.Critical,
    status: AlertStatus.Active,
    confidence_score: 0.94,
    time_to_critical_hours: 3.5,
    explanation: 'Test Critical event',
    contributing_nodes: ['node-1'],
    contributing_sensors: ['tilt_1'],
    source: AlertSource.Edge,
    created_at: new Date(Date.now() - 60000),
    updated_at: new Date()
  };

  test('SirenActuator must execute autonomous edge GPIO call in under 1200ms', async () => {
    const startTime = performance.now();
    const result = await sirenActuator.send(sampleAlert, 'on_ground_local_siren');
    const duration = performance.now() - startTime;

    expect(result.status).toBe(DeliveryStatus.Delivered);
    expect(duration).toBeLessThan(1200);
    expect(result.duration_ms).toBeDefined();
    expect(result.duration_ms!).toBeLessThan(1200);
  });

  test('SmsAdapter Circuit Breaker should failover to secondary adapter during outage', async () => {
    smsCircuitBreaker.reset();
    process.env.SIMULATE_SMS_OUTAGE = 'true';

    const failoverStart = performance.now();
    const result = await smsAdapter.send(sampleAlert, '+919876543210');
    const elapsed = performance.now() - failoverStart;

    expect(result.status).toBe(DeliveryStatus.Sent);
    expect(result.meta?.provider).toBe('SECONDARY_FALLBACK_GATEWAY');
    expect(result.meta?.failover).toBe(true);
    expect(elapsed).toBeLessThan(8000);

    process.env.SIMULATE_SMS_OUTAGE = 'false';
    smsCircuitBreaker.reset();
  });

  test('CommunitySMS adapter should correctly interpolate localized templates across all 5 languages', async () => {
    const languages = ['hi', 'bn', 'sat', 'or', 'en'];

    for (const lang of languages) {
      const res = await communitySmsAdapter.send(sampleAlert, '+919999999999', {
        communityLanguage: lang,
        zoneName: 'Seam IV East'
      });

      expect(res.status).toBe(DeliveryStatus.Sent);
      expect(res.meta?.language).toBe(lang);
      expect(res.meta?.interpolated_message).toContain('Seam IV East');
      expect(res.meta?.interpolated_message).not.toContain('{zone_name}');
      expect(res.meta?.interpolated_message).not.toContain('{instruction}');
    }
  });

  test('EmailAdapter should batch Advisory alerts into daily digest queue without immediate send', async () => {
    const initialQueueLen = dailyDigestQueue.length;
    const advisoryAlert: AlertRecord = {
      ...sampleAlert,
      severity: AlertSeverity.Advisory
    };

    const res = await emailAdapter.send(advisoryAlert, 'planner@coalmine.in');
    expect(res.status).toBe(DeliveryStatus.Queued);
    expect(dailyDigestQueue.length).toBe(initialQueueLen + 1);
  });

  test('BacklogBuffer should buffer delivery and preserve original alert created_at timestamp', async () => {
    backlogBuffer.clear();
    const originalCreatedAt = new Date('2026-09-09T03:00:00.000Z');

    const deliveryRecord = {
      delivery_id: 'del-buf-1',
      alert_id: sampleAlert.alert_id,
      channel: DeliveryChannel.SMS,
      recipient_ref: '+919876543210',
      delivery_status: DeliveryStatus.Queued,
      attempted_at: new Date(),
      delivered_at: null
    };

    backlogBuffer.bufferDelivery(deliveryRecord, originalCreatedAt);
    expect(backlogBuffer.size()).toBe(1);

    const buffered = backlogBuffer.getBufferedDeliveries()[0];
    expect(buffered.original_alert_created_at.toISOString()).toBe(originalCreatedAt.toISOString());

    // Test flush
    let flushedTime: Date | null = null;
    const flushedCount = await backlogBuffer.flush(async (item) => {
      flushedTime = item.original_alert_created_at;
      return true;
    });

    expect(flushedCount).toBe(1);
    expect(backlogBuffer.size()).toBe(0);
    expect(flushedTime!.toISOString()).toBe(originalCreatedAt.toISOString());
  });
});
