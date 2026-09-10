import request from 'supertest';
import { app } from '../src/api/app';
import { repository } from '../src/db/repository';
import { AlertSeverity, AlertSource, AlertStatus, FeedbackVerdict, RiskEvent } from '../src/models/types';

describe('SubSense Alerting System - REST API Integration Tests', () => {
  beforeEach(() => {
    repository.resetMemoryStore();
  });

  const testRiskEvent: RiskEvent = {
    tenant_id: '00000000-0000-0000-0000-000000000001',
    risk_zone_id: '11111111-1111-1111-1111-111111111111',
    anomaly_score: 0.76,
    correlation_strength: 0.82,
    progression_rate: 0.25,
    time_to_critical_hours: 50.0,
    confidence: 0.78,
    explanation: 'Correlated strata deformation across 3 roadway sensors',
    contributing_nodes: ['node-1', 'node-2'],
    contributing_sensors: ['extensometer_1', 'tilt_meter_1'],
    source: AlertSource.Cloud
  };

  test('POST /api/v1/alerts should ingest a valid RiskEvent and create an alert', async () => {
    const res = await request(app)
      .post('/api/v1/alerts')
      .send(testRiskEvent);

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('alert_id');
    expect(res.body.severity).toBe(AlertSeverity.Warning);
    expect(res.body.status).toBe(AlertStatus.Active);
    expect(res.body.contributing_nodes).toEqual(['node-1', 'node-2']);
  });

  test('POST /api/v1/alerts should reject invalid RiskEvent missing required fields', async () => {
    const res = await request(app)
      .post('/api/v1/alerts')
      .send({ tenant_id: '123' }); // missing required fields

    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  test('GET /api/v1/alerts/:id should return 404 for non-existent alert', async () => {
    const res = await request(app).get('/api/v1/alerts/00000000-0000-0000-0000-000000000000');
    expect(res.status).toBe(404);
  });

  test('GET /api/v1/alerts/:id should return alert details, deliveries, and audit history', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testRiskEvent);
    const alertId = createRes.body.alert_id;

    const res = await request(app).get(`/api/v1/alerts/${alertId}`);
    expect(res.status).toBe(200);
    expect(res.body.alert_id).toBe(alertId);
    expect(res.body).toHaveProperty('deliveries');
    expect(res.body).toHaveProperty('audit_history');
    expect(res.body.audit_history.length).toBeGreaterThan(0);
  });

  test('GET /api/v1/alerts should filter alerts by severity and zone_id', async () => {
    // Create one Warning in zone 1
    await request(app).post('/api/v1/alerts').send(testRiskEvent);

    // Create one Advisory in zone 2
    await request(app).post('/api/v1/alerts').send({
      ...testRiskEvent,
      risk_zone_id: '22222222-2222-2222-2222-222222222222',
      confidence: 0.4,
      correlation_strength: 0.1,
      contributing_nodes: ['node-9']
    });

    const filterRes = await request(app)
      .get('/api/v1/alerts')
      .query({ severity: 'Warning' });

    expect(filterRes.status).toBe(200);
    expect(filterRes.body.length).toBe(1);
    expect(filterRes.body[0].severity).toBe('Warning');
  });

  test('GET /api/v1/alerts/:id/deliveries should return delivery records', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testRiskEvent);
    const alertId = createRes.body.alert_id;

    const res = await request(app).get(`/api/v1/alerts/${alertId}/deliveries`);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
  });

  test('POST /api/v1/alerts/:id/feedback should record cryptographically linked feedback', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testRiskEvent);
    const alertId = createRes.body.alert_id;

    const feedbackRes = await request(app)
      .post(`/api/v1/alerts/${alertId}/feedback`)
      .send({
        operator_id: '00000000-0000-0000-0000-000000000099',
        verdict: FeedbackVerdict.HardwareDefect,
        notes: 'Cable degradation caused spurious displacement readings'
      });

    expect(feedbackRes.status).toBe(201);
    expect(feedbackRes.body.feedback.verdict).toBe(FeedbackVerdict.HardwareDefect);
    expect(feedbackRes.body.feedback).toHaveProperty('feedback_hash');
  });

  test('POST /api/v1/alerts/:id/retract should retract alert and dispatch notices after HardwareDefect', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testRiskEvent);
    const alertId = createRes.body.alert_id;

    // Submit feedback first
    await request(app)
      .post(`/api/v1/alerts/${alertId}/feedback`)
      .send({
        operator_id: '00000000-0000-0000-0000-000000000099',
        verdict: FeedbackVerdict.HardwareDefect,
        notes: 'Confirmed defect'
      });

    const retractRes = await request(app)
      .post(`/api/v1/alerts/${alertId}/retract`)
      .send({ reason: 'Hardware defect verified by inspection' });

    expect(retractRes.status).toBe(200);
    expect(retractRes.body.alert.status).toBe(AlertStatus.Retracted);

    const getRes = await request(app).get(`/api/v1/alerts/${alertId}`);
    expect(getRes.body.status).toBe(AlertStatus.Retracted);
    const transitions = getRes.body.audit_history.map((h: any) => h.transition);
    expect(transitions).toContain('retracted');
  });

  test('POST and GET /api/v1/community/registrants', async () => {
    const regPayload = {
      tenant_id: '00000000-0000-0000-0000-000000000001',
      risk_zone_id: '11111111-1111-1111-1111-111111111111',
      phone_number: '+919876543210',
      preferred_language: 'hi',
      opted_in: true
    };

    const postRes = await request(app).post('/api/v1/community/registrants').send(regPayload);
    expect(postRes.status).toBe(201);
    expect(postRes.body).toHaveProperty('registrant_id');
    expect(postRes.body.preferred_language).toBe('hi');

    const getRes = await request(app)
      .get('/api/v1/community/registrants')
      .query({ risk_zone_id: '11111111-1111-1111-1111-111111111111' });

    expect(getRes.status).toBe(200);
    expect(getRes.body.length).toBe(1);
    expect(getRes.body[0].phone_number).toBe('+919876543210');
  });

  test('POST /api/v1/webhooks/risk-events should ingest AI/ML risk event and trigger rule engine', async () => {
    const webhookPayload = {
      tenant_id: 'tenant-jharia-01',
      risk_zone_id: '11111111-1111-1111-1111-111111111111',
      anomaly_score: 0.88,
      correlation_strength: 0.90,
      confidence: 0.85,
      source: 'Cloud',
      plain_language_summary: 'WARNING (Zone Alpha): Tilt surge (+4.20°) and vibration surge detected at Node SS-PANEL7-N042.',
      node_id: 'SS-PANEL7-N042',
      contributing_sensors: ['tilt_deg', 'vibration_rms_mm_s']
    };

    const res = await request(app)
      .post('/api/v1/webhooks/risk-events')
      .set('x-api-key', 'subsense-safety-key-2026')
      .send(webhookPayload);

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('alert_id');
    expect(res.body.severity).toBe(AlertSeverity.Warning);
    expect(res.body.contributing_nodes).toEqual(['SS-PANEL7-N042']);
    expect(res.body.contributing_sensors).toEqual(['tilt_deg', 'vibration_rms_mm_s']);
  });
});
