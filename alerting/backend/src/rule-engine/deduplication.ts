import { AlertRecord, AlertSeverity, AlertStatus, RiskEvent } from '../models/types';
import { DEFAULT_EMERGENCY_WINDOW_HOURS } from './classifier';

export const DEFAULT_COOLDOWN_WARNING_MINS = 30;
export const DEFAULT_COOLDOWN_CRITICAL_MINS = 10;
export const DEFAULT_COOLDOWN_ADVISORY_MINS = 30;

/**
 * Returns the cooldown duration in milliseconds based on severity or custom override.
 */
export function get_cooldown_ms(severity: AlertSeverity, customCooldownMins?: number): number {
  if (customCooldownMins !== undefined && customCooldownMins !== null) {
    return customCooldownMins * 60 * 1000;
  }
  switch (severity) {
    case AlertSeverity.Critical:
      return DEFAULT_COOLDOWN_CRITICAL_MINS * 60 * 1000;
    case AlertSeverity.Warning:
      return DEFAULT_COOLDOWN_WARNING_MINS * 60 * 1000;
    case AlertSeverity.Advisory:
    default:
      return DEFAULT_COOLDOWN_ADVISORY_MINS * 60 * 1000;
  }
}

/**
 * Pure function to check if a risk event is an active duplicate for a given alert.
 */
export function is_alert_within_cooldown(
  alert: Pick<AlertRecord, 'severity' | 'status' | 'updated_at' | 'created_at'>,
  eventTime: Date | number = Date.now(),
  customCooldownMins?: number
): boolean {
  if (alert.status !== AlertStatus.Active && alert.status !== AlertStatus.Escalated) {
    return false;
  }

  const alertTimestamp = new Date(alert.updated_at || alert.created_at).getTime();
  const currentTimestamp = typeof eventTime === 'number' ? eventTime : new Date(eventTime).getTime();
  const cooldownMs = get_cooldown_ms(alert.severity, customCooldownMins);

  return currentTimestamp >= alertTimestamp && (currentTimestamp - alertTimestamp) <= cooldownMs;
}

/**
 * Pure function: Given a zone_id, a new RiskEvent, and currently open alerts,
 * returns an active duplicate alert if one exists within its cooldown window.
 */
export function is_active_duplicate(
  zone_id: string,
  event: RiskEvent,
  openAlerts: AlertRecord[],
  cooldown_mins?: number
): AlertRecord | null {
  const eventTime = event.timestamp ? new Date(event.timestamp).getTime() : Date.now();

  for (const alert of openAlerts) {
    if (alert.risk_zone_id === zone_id) {
      if (is_alert_within_cooldown(alert, eventTime, cooldown_mins)) {
        return alert;
      }
    }
  }

  return null;
}

export interface MergedAlertResult {
  updatedAlert: AlertRecord;
  escalated: boolean;
  previousSeverity: AlertSeverity;
  previousStatus: AlertStatus;
}

/**
 * Pure function to merge incoming risk event telemetry into an existing active alert.
 * Evaluates whether merged values (accelerated velocity or dropped TTC) trigger auto-escalation.
 */
export function merge_telemetry(
  alert: AlertRecord,
  event: RiskEvent,
  emergency_window_hours: number = DEFAULT_EMERGENCY_WINDOW_HOURS
): MergedAlertResult {
  const previousSeverity = alert.severity;
  const previousStatus = alert.status;

  const mergedNodes = Array.from(
    new Set([...alert.contributing_nodes, ...event.contributing_nodes])
  );
  const mergedSensors = Array.from(
    new Set([...alert.contributing_sensors, ...(event.contributing_sensors || [])])
  );

  const updatedConfidence = Math.max(alert.confidence_score, event.confidence);

  const eventTtc = event.time_to_critical_hours !== undefined
    ? event.time_to_critical_hours
    : event.time_to_critical !== undefined ? event.time_to_critical : null;

  let updatedTtc = alert.time_to_critical_hours;
  if (eventTtc !== null && eventTtc !== undefined) {
    updatedTtc = updatedTtc !== null ? Math.min(updatedTtc, eventTtc) : eventTtc;
  }

  const velocity = event.progression_rate ?? event.velocity_delta ?? 0;

  // Check auto-escalation condition:
  // Active Warning whose velocity accelerates or whose ttc drops under emergency threshold
  let severity = alert.severity;
  let status = alert.status;
  let escalated = false;

  const ttcDroppedBelowEmergency = updatedTtc !== null && updatedTtc < emergency_window_hours;
  const velocityAccelerated = velocity >= 1.0; // Significant acceleration threshold

  if (alert.severity === AlertSeverity.Warning && (ttcDroppedBelowEmergency || velocityAccelerated)) {
    severity = AlertSeverity.Critical;
    status = AlertStatus.Escalated;
    escalated = true;
  } else if (alert.severity === AlertSeverity.Advisory && (mergedNodes.length > 1 || event.correlation_strength >= 0.5)) {
    if (ttcDroppedBelowEmergency) {
      severity = AlertSeverity.Critical;
      status = AlertStatus.Escalated;
      escalated = true;
    } else if (updatedConfidence >= 0.65) {
      severity = AlertSeverity.Warning;
    }
  }

  const updatedAlert: AlertRecord = {
    ...alert,
    severity,
    status,
    confidence_score: updatedConfidence,
    time_to_critical_hours: updatedTtc,
    contributing_nodes: mergedNodes,
    contributing_sensors: mergedSensors,
    explanation: `${alert.explanation} | Merged telemetry: +${event.contributing_nodes.length} nodes, TTC: ${updatedTtc ?? 'N/A'}h`,
    updated_at: new Date()
  };

  return {
    updatedAlert,
    escalated,
    previousSeverity,
    previousStatus
  };
}
