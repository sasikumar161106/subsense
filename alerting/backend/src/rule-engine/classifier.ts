import { AlertSeverity } from '../models/types';
import { get_nodes_average_sensitivity } from './recalibration';

export interface ClassificationInputs {
  anomaly_score?: number;
  correlation_strength: number;
  velocity_delta?: number;
  ttc_hours: number | null;
  confidence: number;
  contributing_nodes?: string[];
  emergency_window_hours?: number;
  apply_sensitivity_weights?: boolean;
}

export const DEFAULT_EMERGENCY_WINDOW_HOURS = 6;

/**
 * Pure function to classify the alert severity based on AI/ML risk event telemetry.
 * Factors in recalibrated node sensitivity weights.
 *
 * Rules:
 * - Advisory: single-node (contributing_nodes <= 1), confidence < 0.65, no cross-node correlation (correlation_strength < 0.5).
 * - Warning: GNN-confirmed cross-node (correlation_strength >= 0.5 or nodes > 1), confidence 0.65-0.85, ttc_hours > 48 (or >= emergency_window).
 * - Critical: confidence > 0.85, multi-node correlated, ttc_hours below a configurable emergency window (default 6h).
 */
export function classify_severity(
  anomaly_score_or_inputs: number | ClassificationInputs,
  correlation_strength?: number,
  velocity_delta?: number,
  ttc_hours?: number | null,
  confidence?: number,
  contributing_nodes?: string[],
  emergency_window_hours: number = DEFAULT_EMERGENCY_WINDOW_HOURS
): AlertSeverity {
  let inputs: ClassificationInputs;

  if (typeof anomaly_score_or_inputs === 'object' && anomaly_score_or_inputs !== null) {
    inputs = {
      emergency_window_hours: DEFAULT_EMERGENCY_WINDOW_HOURS,
      apply_sensitivity_weights: true,
      ...anomaly_score_or_inputs
    };
  } else {
    inputs = {
      anomaly_score: anomaly_score_or_inputs,
      correlation_strength: correlation_strength ?? 0,
      velocity_delta: velocity_delta ?? 0,
      ttc_hours: ttc_hours !== undefined ? ttc_hours : null,
      confidence: confidence ?? 0.5,
      contributing_nodes: contributing_nodes ?? [],
      emergency_window_hours: emergency_window_hours ?? DEFAULT_EMERGENCY_WINDOW_HOURS,
      apply_sensitivity_weights: true
    };
  }

  const nodes = inputs.contributing_nodes ?? [];
  const corr = inputs.correlation_strength;
  const ttc = inputs.ttc_hours;
  const emergencyWindow = inputs.emergency_window_hours ?? DEFAULT_EMERGENCY_WINDOW_HOURS;

  // Factor in node sensitivity weights if enabled
  const sensitivity = inputs.apply_sensitivity_weights
    ? get_nodes_average_sensitivity(nodes)
    : 1.0;
  const conf = inputs.confidence * sensitivity;

  const isMultiNode = nodes.length > 1 || corr >= 0.5;

  // 1. Critical: high confidence (>0.85), multi-node correlated, and ttc below emergency window (< 6h)
  if (conf > 0.85 && isMultiNode && ttc !== null && ttc < emergencyWindow) {
    return AlertSeverity.Critical;
  }

  // 2. Warning: GNN-confirmed cross-node, confidence 0.65-0.85 (or higher with ttc >= emergency window)
  if (isMultiNode && conf >= 0.65) {
    if (ttc === null || ttc >= emergencyWindow) {
      return AlertSeverity.Warning;
    }
    if (ttc < emergencyWindow) {
      return AlertSeverity.Critical;
    }
  }

  // 3. Advisory: single-node, confidence < 0.65, no cross-node correlation
  return AlertSeverity.Advisory;
}
