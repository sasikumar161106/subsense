import { AlertSeverity, AlertStatus, AlertSource, RiskEvent } from '../src/models/types';
import {
  classify_severity,
  DEFAULT_EMERGENCY_WINDOW_HOURS
} from '../src/rule-engine/classifier';
import {
  is_active_duplicate,
  merge_telemetry,
  get_cooldown_ms,
  DEFAULT_COOLDOWN_WARNING_MINS,
  DEFAULT_COOLDOWN_CRITICAL_MINS
} from '../src/rule-engine/deduplication';
import {
  cluster_spatial_anomalies,
  should_cluster_spatial_events
} from '../src/rule-engine/spatial';
import {
  should_escalate_alert,
  escalate_alert,
  evaluate_escalation
} from '../src/rule-engine/escalation';
import { deescalate_alert } from '../src/rule-engine/deescalation';
import { generate_idempotency_key } from '../src/rule-engine/idempotency';

describe('Pure Rule Engine - Severity Classifier', () => {
  test('should classify single-node, low-confidence anomaly as Advisory', () => {
    const severity = classify_severity({
      anomaly_score: 0.3,
      correlation_strength: 0.1,
      velocity_delta: 0.05,
      ttc_hours: null,
      confidence: 0.5,
      contributing_nodes: ['node-1']
    });
    expect(severity).toBe(AlertSeverity.Advisory);
  });

  test('should classify GNN-confirmed multi-node anomaly with TTC > 48h as Warning', () => {
    const severity = classify_severity({
      anomaly_score: 0.75,
      correlation_strength: 0.8,
      velocity_delta: 0.2,
      ttc_hours: 52,
      confidence: 0.78,
      contributing_nodes: ['node-1', 'node-2']
    });
    expect(severity).toBe(AlertSeverity.Warning);
  });

  test('should classify high-confidence multi-node anomaly with TTC < 6h as Critical', () => {
    const severity = classify_severity({
      anomaly_score: 0.95,
      correlation_strength: 0.9,
      velocity_delta: 1.5,
      ttc_hours: 3.5,
      confidence: 0.92,
      contributing_nodes: ['node-1', 'node-2', 'node-3'],
      emergency_window_hours: DEFAULT_EMERGENCY_WINDOW_HOURS
    });
    expect(severity).toBe(AlertSeverity.Critical);
  });

  test('should classify as Critical when confidence is in warning range but TTC is below emergency threshold', () => {
    const severity = classify_severity({
      anomaly_score: 0.8,
      correlation_strength: 0.7,
      velocity_delta: 0.4,
      ttc_hours: 4.0, // < 6h emergency window
      confidence: 0.75,
      contributing_nodes: ['node-1', 'node-2']
    });
    expect(severity).toBe(AlertSeverity.Critical);
  });
});

describe('Pure Rule Engine - Deduplication & Cooldown', () => {
  test('should return correct cooldown durations in ms', () => {
    expect(get_cooldown_ms(AlertSeverity.Warning)).toBe(DEFAULT_COOLDOWN_WARNING_MINS * 60 * 1000);
    expect(get_cooldown_ms(AlertSeverity.Critical)).toBe(DEFAULT_COOLDOWN_CRITICAL_MINS * 60 * 1000);
  });

  test('should identify an active duplicate within the cooldown window', () => {
    const now = Date.now();
    const alert = {
      alert_id: 'alert-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Active,
      confidence_score: 0.75,
      time_to_critical_hours: 50,
      explanation: 'Test Warning',
      contributing_nodes: ['node-1'],
      contributing_sensors: ['sensor-1'],
      source: AlertSource.Cloud,
      created_at: new Date(now - 5 * 60 * 1000), // 5 min ago (within 30min cooldown)
      updated_at: new Date(now - 5 * 60 * 1000)
    };

    const newEvent: RiskEvent = {
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.78,
      correlation_strength: 0.8,
      confidence: 0.78,
      explanation: 'Follow-up event',
      contributing_nodes: ['node-2'],
      source: AlertSource.Cloud,
      timestamp: new Date(now)
    };

    const duplicate = is_active_duplicate('zone-1', newEvent, [alert]);
    expect(duplicate).not.toBeNull();
    expect(duplicate?.alert_id).toBe('alert-1');
  });

  test('should NOT identify as duplicate if timestamp is past the cooldown window', () => {
    const now = Date.now();
    const alert = {
      alert_id: 'alert-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Active,
      confidence_score: 0.75,
      time_to_critical_hours: 50,
      explanation: 'Old Warning',
      contributing_nodes: ['node-1'],
      contributing_sensors: ['sensor-1'],
      source: AlertSource.Cloud,
      created_at: new Date(now - 35 * 60 * 1000), // 35 min ago (> 30min cooldown)
      updated_at: new Date(now - 35 * 60 * 1000)
    };

    const newEvent: RiskEvent = {
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.78,
      correlation_strength: 0.8,
      confidence: 0.78,
      explanation: 'Follow-up event',
      contributing_nodes: ['node-2'],
      source: AlertSource.Cloud,
      timestamp: new Date(now)
    };

    const duplicate = is_active_duplicate('zone-1', newEvent, [alert]);
    expect(duplicate).toBeNull();
  });

  test('should merge telemetry and union contributing nodes without duplicates', () => {
    const alert = {
      alert_id: 'alert-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Active,
      confidence_score: 0.75,
      time_to_critical_hours: 50,
      explanation: 'Initial warning',
      contributing_nodes: ['node-1', 'node-2'],
      contributing_sensors: ['sensor-a'],
      source: AlertSource.Cloud,
      created_at: new Date(),
      updated_at: new Date()
    };

    const event: RiskEvent = {
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.79,
      correlation_strength: 0.85,
      confidence: 0.82,
      velocity_delta: 0.2,
      time_to_critical_hours: 48,
      explanation: 'Telemetry update',
      contributing_nodes: ['node-2', 'node-3'], // node-2 overlaps
      contributing_sensors: ['sensor-b'],
      source: AlertSource.Cloud
    };

    const { updatedAlert, escalated } = merge_telemetry(alert, event);
    expect(updatedAlert.contributing_nodes).toEqual(['node-1', 'node-2', 'node-3']);
    expect(updatedAlert.contributing_sensors).toEqual(['sensor-a', 'sensor-b']);
    expect(updatedAlert.confidence_score).toBe(0.82);
    expect(updatedAlert.time_to_critical_hours).toBe(48);
    expect(escalated).toBe(false);
  });
});

describe('Pure Rule Engine - Escalation Logic', () => {
  test('should auto-escalate Warning to Critical when TTC drops below 6h', () => {
    const alert = {
      alert_id: 'alert-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Active,
      confidence_score: 0.8,
      time_to_critical_hours: 50,
      explanation: 'Embankment warning',
      contributing_nodes: ['node-1', 'node-2'],
      contributing_sensors: ['sensor-a'],
      source: AlertSource.Cloud,
      created_at: new Date(),
      updated_at: new Date()
    };

    const result = evaluate_escalation(alert, { ttc_hours: 4.2 });
    expect(result.escalated).toBe(true);
    expect(result.updatedAlert.severity).toBe(AlertSeverity.Critical);
    expect(result.updatedAlert.status).toBe(AlertStatus.Escalated);
  });

  test('should auto-escalate Warning to Critical when velocity accelerates sharply', () => {
    const alert = {
      alert_id: 'alert-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Warning,
      status: AlertStatus.Active,
      confidence_score: 0.8,
      time_to_critical_hours: 24,
      explanation: 'Embankment warning',
      contributing_nodes: ['node-1', 'node-2'],
      contributing_sensors: ['sensor-a'],
      source: AlertSource.Cloud,
      created_at: new Date(),
      updated_at: new Date()
    };

    const result = evaluate_escalation(alert, { velocity_delta: 2.1 });
    expect(result.escalated).toBe(true);
    expect(result.updatedAlert.severity).toBe(AlertSeverity.Critical);
    expect(result.updatedAlert.status).toBe(AlertStatus.Escalated);
  });
});

describe('Pure Rule Engine - De-escalation & Retraction', () => {
  test('should retract alert when hardware defect verdict is received', () => {
    const alert = {
      alert_id: 'alert-1',
      tenant_id: 'tenant-1',
      risk_zone_id: 'zone-1',
      severity: AlertSeverity.Advisory,
      status: AlertStatus.Active,
      confidence_score: 0.6,
      time_to_critical_hours: null,
      explanation: 'Initial advisory',
      contributing_nodes: ['node-1'],
      contributing_sensors: ['sensor-1'],
      source: AlertSource.Cloud,
      created_at: new Date(),
      updated_at: new Date()
    };

    const result = deescalate_alert(alert, 'HardwareDefect', 'Broken tilt cable');
    expect(result.retracted).toBe(true);
    expect(result.updatedAlert.status).toBe(AlertStatus.Retracted);
    expect(result.updatedAlert.explanation).toContain('RETRACTED');
  });
});

describe('Pure Rule Engine - Spatial Clustering', () => {
  test('should cluster adjacent events occurring within 5 minutes', () => {
    const now = Date.now();
    const event1: RiskEvent = {
      tenant_id: 't-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.7,
      correlation_strength: 0.8,
      confidence: 0.75,
      explanation: 'Node 1 triggered',
      contributing_nodes: ['node-1'],
      source: AlertSource.Cloud,
      timestamp: new Date(now)
    };

    const event2: RiskEvent = {
      tenant_id: 't-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.75,
      correlation_strength: 0.85,
      confidence: 0.8,
      explanation: 'Node 2 triggered',
      contributing_nodes: ['node-2'],
      source: AlertSource.Cloud,
      timestamp: new Date(now + 2 * 60 * 1000) // 2 minutes later
    };

    const clusters = cluster_spatial_anomalies([event1, event2]);
    expect(clusters.length).toBe(1);
    expect(clusters[0].length).toBe(2);
  });

  test('should NOT cluster events separated by more than 5 minutes', () => {
    const now = Date.now();
    const event1: RiskEvent = {
      tenant_id: 't-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.7,
      correlation_strength: 0.8,
      confidence: 0.75,
      explanation: 'Node 1 triggered',
      contributing_nodes: ['node-1'],
      source: AlertSource.Cloud,
      timestamp: new Date(now)
    };

    const event2: RiskEvent = {
      tenant_id: 't-1',
      risk_zone_id: 'zone-1',
      anomaly_score: 0.75,
      correlation_strength: 0.85,
      confidence: 0.8,
      explanation: 'Node 2 triggered',
      contributing_nodes: ['node-2'],
      source: AlertSource.Cloud,
      timestamp: new Date(now + 10 * 60 * 1000) // 10 minutes later (> 5 min)
    };

    const clusters = cluster_spatial_anomalies([event1, event2]);
    expect(clusters.length).toBe(2);
  });
});

describe('Pure Rule Engine - Idempotency', () => {
  test('should generate identical idempotency key for events in same window', () => {
    const now = 1700000000000;
    const key1 = generate_idempotency_key('zone-1', now);
    const key2 = generate_idempotency_key('zone-1', now + 10000); // 10s later (within 300s window)

    expect(key1).toBe(key2);
  });

  test('should generate different keys for different risk zones', () => {
    const now = 1700000000000;
    const key1 = generate_idempotency_key('zone-1', now);
    const key2 = generate_idempotency_key('zone-2', now);

    expect(key1).not.toBe(key2);
  });
});
