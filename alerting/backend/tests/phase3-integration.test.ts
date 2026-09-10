import request from 'supertest';
import { app } from '../src/api/app';
import { repository } from '../src/db/repository';
import { AlertSeverity, AlertSource, DeliveryChannel, FeedbackVerdict, RiskEvent } from '../src/models/types';

describe('Phase 3 Integration Tests: Auth, RBAC, Multi-Tenancy & Audit Export', () => {
  let jhariaToken: string;
  let raniganjToken: string;
  let dgmsToken: string;
  let jhariaAlertId: string;
  let raniganjAlertId: string;

  beforeAll(async () => {
    repository.setForceInMemory(true);
    repository.resetMemoryStore();

    // 1. Authenticate Jharia Mine Safety Officer
    const jhariaRes = await request(app)
      .post('/api/v1/auth/login')
      .send({ username: 'officer_jharia', password: 'subsense123' });
    expect(jhariaRes.status).toBe(200);
    jhariaToken = jhariaRes.body.token;

    // 2. Authenticate Raniganj Mine Safety Officer
    const raniganjRes = await request(app)
      .post('/api/v1/auth/login')
      .send({ username: 'officer_raniganj', password: 'subsense123' });
    expect(raniganjRes.status).toBe(200);
    raniganjToken = raniganjRes.body.token;

    // 3. Authenticate DGMS Inspector
    const dgmsRes = await request(app)
      .post('/api/v1/auth/login')
      .send({ username: 'dgms_inspector', password: 'dgms2026' });
    expect(dgmsRes.status).toBe(200);
    dgmsToken = dgmsRes.body.token;

    // Create an alert for Jharia
    const jhariaEvent: RiskEvent = {
      tenant_id: 'tenant-jharia-01',
      risk_zone_id: 'zone-jharia-alpha',
      anomaly_score: 0.92,
      correlation_strength: 0.88,
      velocity_delta: 2.1,
      time_to_critical_hours: 4.2,
      confidence: 0.9,
      explanation: 'Critical strata convergence in Jharia Seam IV',
      contributing_nodes: ['node-j-1', 'node-j-2'],
      source: AlertSource.Edge,
      timestamp: new Date()
    };
    const jAlertRes = await request(app).post('/api/v1/alerts').send(jhariaEvent);
    expect(jAlertRes.status).toBe(201);
    jhariaAlertId = jAlertRes.body.alert_id;

    // Create an alert for Raniganj
    const raniganjEvent: RiskEvent = {
      tenant_id: 'tenant-raniganj-02',
      risk_zone_id: 'zone-raniganj-gamma',
      anomaly_score: 0.76,
      correlation_strength: 0.72,
      time_to_critical_hours: 50.0,
      confidence: 0.78,
      explanation: 'Warning tension crack in Raniganj North Longwall',
      contributing_nodes: ['node-r-1'],
      source: AlertSource.Cloud,
      timestamp: new Date()
    };
    const rAlertRes = await request(app).post('/api/v1/alerts').send(raniganjEvent);
    expect(rAlertRes.status).toBe(201);
    raniganjAlertId = rAlertRes.body.alert_id;
  });

  describe('1. JWT Authentication & Tenant Query Isolation', () => {
    it('should reject requests with invalid credentials', async () => {
      const res = await request(app)
        .post('/api/v1/auth/login')
        .send({ username: 'officer_jharia', password: 'wrongpassword' });
      expect(res.status).toBe(401);
    });

    it('should return self context from /api/v1/auth/me', async () => {
      const res = await request(app)
        .get('/api/v1/auth/me')
        .set('Authorization', `Bearer ${jhariaToken}`);
      expect(res.status).toBe(200);
      expect(res.body.user.username).toBe('officer_jharia');
      expect(res.body.user.tenant_id).toBe('tenant-jharia-01');
    });

    it('Officer Jharia should only receive Jharia alerts from GET /api/v1/alerts', async () => {
      const res = await request(app)
        .get('/api/v1/alerts')
        .set('Authorization', `Bearer ${jhariaToken}`);
      expect(res.status).toBe(200);
      expect(res.body.length).toBeGreaterThanOrEqual(1);
      for (const alert of res.body) {
        expect(alert.tenant_id).toBe('tenant-jharia-01');
      }
    });

    it('Officer Jharia must be FORBIDDEN (403) from accessing a Raniganj alert directly', async () => {
      const res = await request(app)
        .get(`/api/v1/alerts/${raniganjAlertId}`)
        .set('Authorization', `Bearer ${jhariaToken}`);
      expect(res.status).toBe(403);
      expect(res.body.error).toContain('Tenant Access Denied');
    });

    it('Officer Jharia must be FORBIDDEN (403) from submitting feedback for a Raniganj alert', async () => {
      const res = await request(app)
        .post(`/api/v1/alerts/${raniganjAlertId}/feedback`)
        .set('Authorization', `Bearer ${jhariaToken}`)
        .send({
          operator_id: 'usr-jharia-01',
          verdict: FeedbackVerdict.FalsePositive,
          notes: 'Unauthorized cross-tenant attempt'
        });
      expect(res.status).toBe(403);
    });

    it('DGMS Inspector should be entitled to view alerts across both tenants', async () => {
      const res = await request(app)
        .get('/api/v1/alerts')
        .set('Authorization', `Bearer ${dgmsToken}`);
      expect(res.status).toBe(200);
      const tenantIds = res.body.map((a: any) => a.tenant_id);
      expect(tenantIds).toContain('tenant-jharia-01');
      expect(tenantIds).toContain('tenant-raniganj-02');
    });

    it('DGMS Inspector must be FORBIDDEN (403) from submitting operator feedback (read-only rule)', async () => {
      const res = await request(app)
        .post(`/api/v1/alerts/${jhariaAlertId}/feedback`)
        .set('Authorization', `Bearer ${dgmsToken}`)
        .send({
          operator_id: 'usr-dgms-01',
          verdict: FeedbackVerdict.Confirmed,
          notes: 'Regulator attempt'
        });
      expect(res.status).toBe(403);
      expect(res.body.error).toContain('Regulator/DGMS role has read-only access');
    });
  });

  describe('2. End-to-End Multi-Channel Deliveries for Critical Alert', () => {
    it('should generate all Critical tier delivery channels on Jharia alert', async () => {
      const res = await request(app)
        .get(`/api/v1/alerts/${jhariaAlertId}/deliveries`)
        .set('Authorization', `Bearer ${jhariaToken}`);
      expect(res.status).toBe(200);
      const channels = res.body.map((d: any) => d.channel);

      expect(channels).toContain(DeliveryChannel.Siren);
      expect(channels).toContain(DeliveryChannel.SMS);
      expect(channels).toContain(DeliveryChannel.VoiceIVR);
      expect(channels).toContain(DeliveryChannel.DashboardBanner);
      expect(channels).toContain(DeliveryChannel.CommunitySMS);
    });
  });

  describe('3. One-Click DGMS Audit Export (CSV)', () => {
    it('should export audit log as RFC 4180 CSV with correct headers', async () => {
      const res = await request(app)
        .get('/api/v1/audit/export')
        .set('Authorization', `Bearer ${dgmsToken}`);
      expect(res.status).toBe(200);
      expect(res.headers['content-type']).toContain('text/csv');
      expect(res.headers['content-disposition']).toContain('dgms_annual_safety_audit');

      const csvText = res.text;
      expect(csvText).toContain('Log ID');
      expect(csvText).toContain('Alert ID');
      expect(csvText).toContain('Transition');
      expect(csvText).toContain('CREATED');
    });

    it('should scope audit log export to tenant for Mine Safety Officer', async () => {
      const res = await request(app)
        .get('/api/v1/audit/export')
        .set('Authorization', `Bearer ${jhariaToken}`);
      expect(res.status).toBe(200);
      expect(res.headers['content-disposition']).toContain('tenant-jharia-01');
      const csvText = res.text;
      expect(csvText).toContain('tenant-jharia-01');
      expect(csvText).not.toContain('tenant-raniganj-02');
    });
  });
});
