import {
  generate_explainability_payload,
  build_sensor_attribution,
  build_trigger_narrative,
  extrapolate_time_to_critical
} from '../src/rule-engine/explainability';
import { AlertSource, RiskEvent } from '../src/models/types';

describe('Phase 2 Explainability Engine', () => {
  const sampleEvent: RiskEvent = {
    tenant_id: 'tenant-1',
    risk_zone_id: 'zone-1',
    zone_name: 'Main Haulage Incline',
    anomaly_score: 0.88,
    correlation_strength: 0.91,
    progression_rate: 1.8,
    velocity_delta: 1.8,
    time_to_critical_hours: 4.5,
    confidence: 0.942,
    explanation: 'Rapid subsidence detected along haulage roadway',
    contributing_nodes: ['node-07', 'node-12', 'node-03'],
    contributing_sensors: ['tilt_meter_a', 'extensometer_b', 'vibration_c'],
    source: AlertSource.Cloud
  };

  test('should format composite confidence as a calibrated percentage string', () => {
    const payload = generate_explainability_payload(sampleEvent);
    expect(payload.composite_confidence).toBe('94.2%');
  });

  test('should generate structured sensor attribution with concrete readings and modalities', () => {
    const attributions = build_sensor_attribution(sampleEvent);
    expect(attributions.length).toBe(3);

    expect(attributions[0].modality).toBe('tilt');
    expect(attributions[0].reading).toMatch(/\+\d+\.\d+°/); // e.g. +4.8°

    expect(attributions[1].modality).toBe('displacement');
    expect(attributions[1].reading).toMatch(/\d+\.\d+ mm/);

    expect(attributions[2].modality).toBe('vibration');
    expect(attributions[2].reading).toMatch(/\d+\.\d+ mm\/s²/);
  });

  test('should construct trigger narrative interpolated from real telemetry numbers', () => {
    const narrative = build_trigger_narrative(sampleEvent, 'Main Haulage Incline');
    expect(narrative).toContain('Cross-correlated 3-point shear strain detected along Main Haulage Incline');
    expect(narrative).toMatch(/displacement rate accelerated \d+% over \d+h\./);
    expect(narrative).not.toContain('{');
    expect(narrative).not.toContain('}');
  });

  test('should extrapolate plausible time-to-critical countdown when LSTM forecast is omitted', () => {
    const eventWithoutTtc: RiskEvent = {
      ...sampleEvent,
      time_to_critical_hours: null,
      time_to_critical: null,
      velocity_delta: 1.5
    };

    const payload = generate_explainability_payload(eventWithoutTtc);
    expect(payload.time_to_critical_hours).toBeDefined();
    expect(payload.time_to_critical_hours).toBeGreaterThan(0);
    expect(typeof payload.time_to_critical_hours).toBe('number');

    // Test helper directly
    const fallbackTtc = extrapolate_time_to_critical(1.5, 25.0, 10.0);
    expect(fallbackTtc).toBe(10.0); // (25-10)/1.5 = 10.0h
  });
});
