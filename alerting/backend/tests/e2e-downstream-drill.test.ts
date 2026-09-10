import request from 'supertest';
import { app } from '../src/api/app';
import { repository } from '../src/db/repository';
import { AlertSeverity, AlertStatus } from '../src/models/types';

describe('Phase 3d: Hardware Drill Downstream Verification (Alert_System)', () => {
  beforeEach(() => {
    repository.resetMemoryStore();
  });

  it('should process physical MPU6050 tilt anomaly event from AI/ML, dispatch edge siren, and log audit trail', async () => {
    // Exact payload dispatched by ai-ml/integration/alert_dispatcher.py during the drill
    const hardwareDrillRiskEvent = {
      tenant_id: 'tenant-jharia-01',
      risk_zone_id: '11111111-1111-1111-1111-111111111111',
      anomaly_score: 0.94,
      correlation_strength: 0.88,
      confidence: 0.92,
      source: 'Cloud',
      explanation: 'Critical tilt anomaly on Node SS-PANEL7-N042 exceeding threshold (4.82 deg). Evacuate extraction panel.',
      contributing_nodes: ['SS-PANEL7-N042', 'SS-PANEL7-N043'],
      contributing_sensors: ['tilt_deg', 'vibration_rms_mm_s'], // Strictly zero-fabrication: no displacement or crack
      time_to_critical_hours: 1.5,
      progression_rate: 0.85,
      velocity_delta: 0.45,
      timestamp: new Date().toISOString()
    };

    // 1. Send via Webhook endpoint
    const res = await request(app)
      .post('/api/v1/webhooks/risk-events')
      .send(hardwareDrillRiskEvent);

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('alert_id');
    expect(res.body.severity).toBe(AlertSeverity.Critical);
    expect(res.body.status).toBe(AlertStatus.Active);

    const alertId = res.body.alert_id;

    // 2. Fetch full alert details, delivery log, and audit history
    const detailRes = await request(app).get(`/api/v1/alerts/${alertId}`);
    expect(detailRes.status).toBe(200);
    expect(detailRes.body.tenant_id).toBe('tenant-jharia-01');
    expect(detailRes.body.contributing_sensors).toEqual(['tilt_deg', 'vibration_rms_mm_s']);
    expect(detailRes.body.contributing_sensors).not.toContain('displacement_mm');
    expect(detailRes.body.contributing_sensors).not.toContain('crack_index');

    // 3. Verify multi-channel deliveries (including physical edge siren)
    expect(detailRes.body.deliveries.length).toBeGreaterThanOrEqual(1);
    const sirenDelivery = detailRes.body.deliveries.find((d: any) => d.channel === 'Siren');
    expect(sirenDelivery).toBeDefined();

    // 4. Verify DGMS audit trail
    expect(detailRes.body.audit_history.length).toBeGreaterThanOrEqual(1);
    expect(detailRes.body.audit_history[0].transition).toBe('created');
    expect(detailRes.body.audit_history[0].log_id).toBeDefined();
    expect(detailRes.body.audit_history[0].snapshot).toBeDefined();
  });
});
