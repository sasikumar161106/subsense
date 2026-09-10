import request from 'supertest';
import { app } from '../src/api/app';
import { repository } from '../src/db/repository';
import { run_recalibration_job, get_node_sensitivity_weight } from '../src/rule-engine/recalibration';
import { AlertSeverity, AlertSource, AlertStatus, FeedbackVerdict, RiskEvent } from '../src/models/types';

describe('Phase 2 Feedback & Retraction Loop', () => {
  beforeEach(() => {
    repository.resetMemoryStore();
  });

  const testEvent: RiskEvent = {
    tenant_id: 'tenant-1',
    risk_zone_id: 'zone-11',
    anomaly_score: 0.78,
    correlation_strength: 0.85,
    confidence: 0.8,
    time_to_critical_hours: 50.0,
    explanation: 'Correlated movement detected across sensors',
    contributing_nodes: ['node-fp-1', 'node-fp-2'],
    contributing_sensors: ['tilt_1', 'extensometer_1'],
    source: AlertSource.Cloud
  };

  test('POST /api/v1/alerts/:id/feedback should cryptographically link feedback to alert via SHA-256', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testEvent);
    const alertId = createRes.body.alert_id;

    const feedbackRes = await request(app)
      .post(`/api/v1/alerts/${alertId}/feedback`)
      .send({
        operator_id: 'operator-1',
        verdict: FeedbackVerdict.FalsePositive,
        notes: 'Confirmed false alarm from seismic blasting tremor'
      });

    expect(feedbackRes.status).toBe(201);
    expect(feedbackRes.body.feedback).toHaveProperty('feedback_hash');
    expect(feedbackRes.body.feedback.feedback_hash).toMatch(/^[a-f0-9]{64}$/); // SHA-256 64-char hex
  });

  test('POST /api/v1/alerts/:id/retract should be REJECTED if no FalsePositive/HardwareDefect feedback exists', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testEvent);
    const alertId = createRes.body.alert_id;

    // Attempt retract without any prior invalidation feedback
    const retractRes = await request(app)
      .post(`/api/v1/alerts/${alertId}/retract`)
      .send({ reason: 'Premature manual retraction attempt' });

    expect(retractRes.status).toBe(400);
    expect(retractRes.body.error).toContain('only be retracted after a FalsePositive or HardwareDefect');
  });

  test('POST /api/v1/alerts/:id/retract should succeed after FalsePositive feedback and dispatch Retraction Notice', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testEvent);
    const alertId = createRes.body.alert_id;

    // 1. Submit FalsePositive feedback
    await request(app)
      .post(`/api/v1/alerts/${alertId}/feedback`)
      .send({
        operator_id: 'operator-1',
        verdict: FeedbackVerdict.FalsePositive,
        notes: 'Blasting vibration at adjacent face'
      });

    // 2. Now attempt retract
    const retractRes = await request(app)
      .post(`/api/v1/alerts/${alertId}/retract`)
      .send({ reason: 'Blasting vibration confirmed on ground' });

    expect(retractRes.status).toBe(200);
    expect(retractRes.body.alert.status).toBe(AlertStatus.Retracted);
    expect(retractRes.body.retraction_deliveries).toBeDefined();
    expect(retractRes.body.retraction_deliveries.length).toBeGreaterThan(0);

    const retractionNoticeFlags = retractRes.body.retraction_deliveries.map(
      (d: any) => d.retraction_notice
    );
    expect(retractionNoticeFlags.every(Boolean)).toBe(true);
  });

  test('Recalibration job should aggregate false alarms, decay node sensitivity, and log audit sign-off', async () => {
    const createRes = await request(app).post('/api/v1/alerts').send(testEvent);
    const alertId = createRes.body.alert_id;

    await request(app)
      .post(`/api/v1/alerts/${alertId}/feedback`)
      .send({
        operator_id: 'operator-1',
        verdict: FeedbackVerdict.FalsePositive,
        notes: 'Node fp-1 has noisy wiring'
      });

    const weightBefore = get_node_sensitivity_weight('node-fp-1');
    const summary = await run_recalibration_job('Chief_Inspector_Verma');
    const weightAfter = get_node_sensitivity_weight('node-fp-1');

    expect(summary.nodes_recalibrated).toBeGreaterThan(0);
    expect(summary.human_sign_off).toBe('Chief_Inspector_Verma');
    expect(weightAfter).toBeLessThan(weightBefore);
  });
});
