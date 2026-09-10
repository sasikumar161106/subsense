import { AlertSource, RiskEvent } from '../models/types';

export const TENANT_ID = '00000000-0000-0000-0000-000000000001';

export const ZONES = {
  ZONE_ALPHA: '11111111-1111-1111-1111-111111111111', // Underground Longwall Face
  ZONE_BETA: '22222222-2222-2222-2222-222222222222',  // Main Haulage Incline
  ZONE_GAMMA: '33333333-3333-3333-3333-333333333333'  // Surface Overburden Dump
};

/**
 * Scenario 1: Low-Confidence Single-Node Noise -> Advisory
 */
export const scenarioLowConfidenceSingleNode: RiskEvent = {
  tenant_id: TENANT_ID,
  risk_zone_id: ZONES.ZONE_ALPHA,
  zone_name: 'Underground Longwall Seam IV',
  anomaly_score: 0.35,
  correlation_strength: 0.12,
  progression_rate: 0.05,
  velocity_delta: 0.05,
  time_to_critical_hours: null,
  confidence: 0.45, // < 0.65
  explanation: 'Minor tilt deviation recorded on single edge node',
  contributing_nodes: ['10000000-0000-0000-0000-000000000101'],
  contributing_sensors: ['tilt_sensor_a'],
  source: AlertSource.Cloud
};

/**
 * Scenario 2: Correlated Multi-Node Event with TTC > 48h -> Warning
 */
export const scenarioCorrelatedWarning: RiskEvent = {
  tenant_id: TENANT_ID,
  risk_zone_id: ZONES.ZONE_BETA,
  zone_name: 'Main Haulage Incline Roadway',
  anomaly_score: 0.72,
  correlation_strength: 0.81, // GNN-confirmed spatial correlation
  progression_rate: 0.22,
  velocity_delta: 0.22,
  time_to_critical_hours: 54.0, // > 48 hours
  confidence: 0.76, // 0.65 - 0.85
  explanation: 'GNN detected correlated strata displacement across 3 roadway sensors',
  contributing_nodes: [
    '20000000-0000-0000-0000-000000000201',
    '20000000-0000-0000-0000-000000000202',
    '20000000-0000-0000-0000-000000000203'
  ],
  contributing_sensors: ['extensometer_1', 'borehole_stress_cell', 'vibration_sensor_a'],
  source: AlertSource.Cloud
};

/**
 * Scenario 3: Telemetry arriving inside cooldown window -> Merged into existing Warning
 */
export const scenarioDuplicateInsideCooldown: RiskEvent = {
  tenant_id: TENANT_ID,
  risk_zone_id: ZONES.ZONE_BETA,
  zone_name: 'Main Haulage Incline Roadway',
  anomaly_score: 0.75,
  correlation_strength: 0.85,
  progression_rate: 0.28,
  velocity_delta: 0.28,
  time_to_critical_hours: 51.5,
  confidence: 0.79,
  explanation: 'Subsequent telemetry update from adjacent sensor node',
  contributing_nodes: [
    '20000000-0000-0000-0000-000000000202',
    '20000000-0000-0000-0000-000000000204' // new node added
  ],
  contributing_sensors: ['extensometer_2'],
  source: AlertSource.Cloud
};

/**
 * Scenario 4A: Early Warning for Zone Gamma
 */
export const scenarioAcceleratingInitialWarning: RiskEvent = {
  tenant_id: TENANT_ID,
  risk_zone_id: ZONES.ZONE_GAMMA,
  zone_name: 'Surface Overburden Dump Slope',
  anomaly_score: 0.68,
  correlation_strength: 0.74,
  progression_rate: 0.35,
  velocity_delta: 0.35,
  time_to_critical_hours: 50.0,
  confidence: 0.74,
  explanation: 'Initial tension crack movement detected on upper embankment bench',
  contributing_nodes: [
    '30000000-0000-0000-0000-000000000301',
    '30000000-0000-0000-0000-000000000302'
  ],
  contributing_sensors: ['crack_meter_1', 'inclinometer_1'],
  source: AlertSource.Cloud
};

/**
 * Scenario 4B: Rapid Acceleration -> Auto-flip to Critical (Escalated)
 */
export const scenarioAcceleratingCriticalSpike: RiskEvent = {
  tenant_id: TENANT_ID,
  risk_zone_id: ZONES.ZONE_GAMMA,
  zone_name: 'Surface Overburden Dump Slope',
  anomaly_score: 0.96,
  correlation_strength: 0.92,
  progression_rate: 2.45, // velocity surges sharply (> 1.0)
  velocity_delta: 2.45,
  time_to_critical_hours: 3.2, // drops under emergency threshold (< 6h)
  confidence: 0.94, // > 0.85
  explanation: 'CRITICAL: Rapid shear failure acceleration detected! Evacuate crest.',
  contributing_nodes: [
    '30000000-0000-0000-0000-000000000301',
    '30000000-0000-0000-0000-000000000302',
    '30000000-0000-0000-0000-000000000303'
  ],
  contributing_sensors: ['inclinometer_2', 'seismic_geophone'],
  source: AlertSource.Edge // Edge source triggers local siren!
};
