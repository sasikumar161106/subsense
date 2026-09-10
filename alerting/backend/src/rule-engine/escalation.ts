import { AlertRecord, AlertSeverity, AlertStatus } from '../models/types';
import { DEFAULT_EMERGENCY_WINDOW_HOURS } from './classifier';

export const VELOCITY_ACCELERATION_THRESHOLD = 1.0; // mm/h or delta rate threshold

export interface EscalationResult {
  escalated: boolean;
  updatedAlert: AlertRecord;
  reason?: string;
}

/**
 * Pure function: Checks if an active Warning alert qualifies for automatic escalation to Critical.
 *
 * Rules:
 * - Alert must currently be Active or Warning.
 * - Triggers if velocity delta accelerates (>= 1.0) OR
 * - Triggers if time-to-critical drops below emergency window (< 6h).
 */
export function should_escalate_alert(
  alert: Pick<AlertRecord, 'severity' | 'status' | 'time_to_critical_hours'>,
  velocity_delta?: number,
  ttc_hours?: number | null,
  emergency_window_hours: number = DEFAULT_EMERGENCY_WINDOW_HOURS
): { shouldEscalate: boolean; reason?: string } {
  // Only Warning (or active non-critical) alerts can escalate to Critical
  if (alert.severity === AlertSeverity.Critical && alert.status === AlertStatus.Escalated) {
    return { shouldEscalate: false };
  }

  const effectiveTtc = ttc_hours !== undefined ? ttc_hours : alert.time_to_critical_hours;
  const effectiveVelocity = velocity_delta ?? 0;

  if (effectiveTtc !== null && effectiveTtc !== undefined && effectiveTtc < emergency_window_hours) {
    return {
      shouldEscalate: true,
      reason: `Time-to-critical (${effectiveTtc.toFixed(1)}h) dropped below emergency threshold (${emergency_window_hours}h)`
    };
  }

  if (effectiveVelocity >= VELOCITY_ACCELERATION_THRESHOLD) {
    return {
      shouldEscalate: true,
      reason: `Deformation velocity accelerated sharply (${effectiveVelocity.toFixed(2)} mm/h >= ${VELOCITY_ACCELERATION_THRESHOLD})`
    };
  }

  return { shouldEscalate: false };
}

/**
 * Pure function: Auto-flips an alert to Critical with status Escalated.
 */
export function escalate_alert(alert: AlertRecord, reason: string): AlertRecord {
  return {
    ...alert,
    severity: AlertSeverity.Critical,
    status: AlertStatus.Escalated,
    explanation: `${alert.explanation} [AUTO-ESCALATED TO CRITICAL: ${reason}]`,
    updated_at: new Date()
  };
}

/**
 * Evaluates telemetry against an alert and returns the escalated alert record if conditions are met.
 */
export function evaluate_escalation(
  alert: AlertRecord,
  telemetry: { velocity_delta?: number; ttc_hours?: number | null },
  emergency_window_hours: number = DEFAULT_EMERGENCY_WINDOW_HOURS
): EscalationResult {
  const { shouldEscalate, reason } = should_escalate_alert(
    alert,
    telemetry.velocity_delta,
    telemetry.ttc_hours,
    emergency_window_hours
  );

  if (!shouldEscalate || !reason) {
    return {
      escalated: false,
      updatedAlert: alert
    };
  }

  const updatedAlert = escalate_alert(alert, reason);

  return {
    escalated: true,
    updatedAlert,
    reason
  };
}
