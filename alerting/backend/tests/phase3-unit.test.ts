import { classify_severity } from '../src/rule-engine/classifier';
import { is_active_duplicate, get_cooldown_ms } from '../src/rule-engine/deduplication';
import { evaluate_escalation } from '../src/rule-engine/escalation';
import { generate_idempotency_key } from '../src/rule-engine/idempotency';
import { encrypt_phone_number, decrypt_phone_number, mask_phone_number } from '../src/security/encryption';
import { AlertRecord, AlertSeverity, AlertStatus, AlertSource, RiskEvent } from '../src/models/types';

describe('Phase 3 Unit Tests: Engine Boundaries, Security & Deduplication', () => {
  describe('1. Severity Classification Boundaries', () => {
    it('should classify boundary events below 0.65 confidence and single-node as Advisory', () => {
      const severity = classify_severity({
        anomaly_score: 0.5,
        correlation_strength: 0.3,
        velocity_delta: 0.1,
        ttc_hours: null,
        confidence: 0.64,
        contributing_nodes: ['node-1']
      });
      expect(severity).toBe(AlertSeverity.Advisory);
    });

    it('should classify multi-node correlated events with confidence 0.65-0.85 as Warning', () => {
      const severity = classify_severity({
        anomaly_score: 0.75,
        correlation_strength: 0.7,
        velocity_delta: 0.3,
        ttc_hours: 50,
        confidence: 0.75,
        contributing_nodes: ['node-1', 'node-2']
      });
      expect(severity).toBe(AlertSeverity.Warning);
    });

    it('should classify high-confidence (>=0.85) or emergency TTC (<6h) as Critical', () => {
      const severity = classify_severity({
        anomaly_score: 0.75,
        correlation_strength: 0.7,
        velocity_delta: 0.3,
        ttc_hours: 4.5, // Emergency window
        confidence: 0.75,
        contributing_nodes: ['node-1', 'node-2']
      });
      expect(severity).toBe(AlertSeverity.Critical);
    });
  });

  describe('2. Cooldown Deduplication Timing', () => {
    it('should return 30 minutes for Warning and 10 minutes for Critical', () => {
      expect(get_cooldown_ms(AlertSeverity.Warning)).toBe(30 * 60 * 1000);
      expect(get_cooldown_ms(AlertSeverity.Critical)).toBe(10 * 60 * 1000);
      expect(get_cooldown_ms(AlertSeverity.Advisory)).toBe(30 * 60 * 1000);
    });

    it('should match an active alert inside the cooldown window', () => {
      const existingAlert: AlertRecord = {
        alert_id: 'alert-1',
        tenant_id: 'tenant-1',
        risk_zone_id: 'zone-1',
        severity: AlertSeverity.Warning,
        status: AlertStatus.Active,
        confidence_score: 0.75,
        time_to_critical_hours: 40,
        explanation: 'Active alert',
        contributing_nodes: ['node-1'],
        contributing_sensors: ['sensor-1'],
        source: AlertSource.Edge,
        created_at: new Date(Date.now() - 5 * 60 * 1000), // 5 minutes ago
        updated_at: new Date(Date.now() - 5 * 60 * 1000)
      };

      const event: RiskEvent = {
        tenant_id: 'tenant-1',
        risk_zone_id: 'zone-1',
        anomaly_score: 0.75,
        correlation_strength: 0.7,
        confidence: 0.75,
        explanation: 'Incoming duplicate',
        contributing_nodes: ['node-1'],
        source: AlertSource.Edge
      };

      const match = is_active_duplicate('zone-1', event, [existingAlert]);
      expect(match).not.toBeNull();
      expect(match?.alert_id).toBe('alert-1');
    });

    it('should NOT match if event timestamp exceeds the cooldown window', () => {
      const expiredAlert: AlertRecord = {
        alert_id: 'alert-old',
        tenant_id: 'tenant-1',
        risk_zone_id: 'zone-1',
        severity: AlertSeverity.Warning,
        status: AlertStatus.Active,
        confidence_score: 0.75,
        time_to_critical_hours: 40,
        explanation: 'Old alert',
        contributing_nodes: ['node-1'],
        contributing_sensors: ['sensor-1'],
        source: AlertSource.Edge,
        created_at: new Date(Date.now() - 35 * 60 * 1000), // 35 minutes ago (>30m)
        updated_at: new Date(Date.now() - 35 * 60 * 1000)
      };

      const event: RiskEvent = {
        tenant_id: 'tenant-1',
        risk_zone_id: 'zone-1',
        anomaly_score: 0.75,
        correlation_strength: 0.7,
        confidence: 0.75,
        explanation: 'Incoming after window',
        contributing_nodes: ['node-1'],
        source: AlertSource.Edge
      };

      const match = is_active_duplicate('zone-1', event, [expiredAlert]);
      expect(match).toBeNull();
    });
  });

  describe('3. Auto-Escalation Threshold Triggers', () => {
    const baseWarningAlert: AlertRecord = {
      alert_id: 'warn-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Active,
      confidence_score: 0.75,
      time_to_critical_hours: 24,
      explanation: 'Base warning',
      contributing_nodes: ['node-1'],
      contributing_sensors: ['sensor-1'],
      source: AlertSource.Edge,
      created_at: new Date(),
      updated_at: new Date()
    };

    it('should auto-escalate Warning to Critical when velocity delta surges >= 1.0 mm/h', () => {
      const result = evaluate_escalation(baseWarningAlert, { velocity_delta: 1.85 });
      expect(result.escalated).toBe(true);
      expect(result.updatedAlert.severity).toBe(AlertSeverity.Critical);
      expect(result.updatedAlert.status).toBe(AlertStatus.Escalated);
    });

    it('should auto-escalate Warning to Critical when TTC drops below emergency threshold (6h)', () => {
      const result = evaluate_escalation(baseWarningAlert, { ttc_hours: 3.2 });
      expect(result.escalated).toBe(true);
      expect(result.updatedAlert.severity).toBe(AlertSeverity.Critical);
      expect(result.updatedAlert.status).toBe(AlertStatus.Escalated);
    });
  });

  describe('4. Idempotency Key Collisions', () => {
    it('should generate identical keys for identical window and zone', () => {
      const date = new Date('2026-09-09T08:15:30.000Z');
      const key1 = generate_idempotency_key('zone-alpha', date);
      const key2 = generate_idempotency_key('zone-alpha', new Date('2026-09-09T08:15:45.000Z'));
      expect(key1).toBe(key2);
    });

    it('should generate different keys for different risk zones or time windows', () => {
      const date = new Date('2026-09-09T08:15:30.000Z');
      const key1 = generate_idempotency_key('zone-alpha', date);
      const key2 = generate_idempotency_key('zone-beta', date);
      const key3 = generate_idempotency_key('zone-alpha', new Date('2026-09-09T08:35:00.000Z'));

      expect(key1).not.toBe(key2);
      expect(key1).not.toBe(key3);
    });
  });

  describe('5. Security: AES-256-GCM Encryption at Rest', () => {
    const rawPhoneNumber = '+919876543210';

    it('should encrypt phone numbers at rest with aes256gcm prefix', () => {
      const encrypted = encrypt_phone_number(rawPhoneNumber);
      expect(encrypted).toMatch(/^aes256gcm:[0-9a-f]{24}:[0-9a-f]{32}:[0-9a-f]+$/);
      expect(encrypted).not.toContain(rawPhoneNumber);
    });

    it('should decrypt stored ciphertext back to exact original plain text', () => {
      const encrypted = encrypt_phone_number(rawPhoneNumber);
      const decrypted = decrypt_phone_number(encrypted);
      expect(decrypted).toBe(rawPhoneNumber);
    });

    it('should mask phone number preserving dial code and last 4 digits', () => {
      const masked = mask_phone_number(rawPhoneNumber);
      expect(masked).toBe('+9198****3210');
    });

    it('should fail cleanly if auth tag or ciphertext is tampered with', () => {
      const encrypted = encrypt_phone_number(rawPhoneNumber);
      const tampered = encrypted.slice(0, -2) + 'ff';
      const result = decrypt_phone_number(tampered);
      expect(result).toBe('[DECRYPTION_FAILED]');
    });
  });
});
