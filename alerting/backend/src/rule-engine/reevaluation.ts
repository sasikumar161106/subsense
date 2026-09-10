import { repository } from '../db/repository';
import { audit_logger } from '../audit/logger';
import { AlertRecord, AlertSeverity, AlertStatus, SEVERITY_CHANNEL_MATRIX } from '../models/types';
import { notification_dispatcher } from './dispatchers';
import { should_escalate_alert, escalate_alert } from './escalation';

export const scheduledReevaluations: Map<string, NodeJS.Timeout> = new Map();

/**
 * Pure reevaluation check on an alert:
 * Evaluates whether an active alert needs escalation due to time-to-critical decay or updated telemetry.
 */
export async function reevaluate_single_alert(
  alertId: string,
  simulatedTtcDropHours?: number
): Promise<AlertRecord | null> {
  const alert = await repository.findAlertById(alertId);
  if (!alert) return null;

  // Only re-evaluate Active or Escalated alerts
  if (alert.status !== AlertStatus.Active && alert.status !== AlertStatus.Escalated) {
    return alert;
  }

  // If a simulated TTC decay was provided (e.g. from a background sensor tick)
  let currentTtc = alert.time_to_critical_hours;
  if (simulatedTtcDropHours !== undefined && currentTtc !== null) {
    currentTtc = Math.max(0, currentTtc - simulatedTtcDropHours);
  }

  // Check if Warning should escalate to Critical
  const { shouldEscalate, reason } = should_escalate_alert(
    { ...alert, time_to_critical_hours: currentTtc },
    undefined,
    currentTtc
  );

  if (shouldEscalate && reason) {
    const escalatedRecord = escalate_alert(
      { ...alert, time_to_critical_hours: currentTtc },
      reason
    );
    const saved = await repository.updateAlert(alert.alert_id, escalatedRecord);

    // Dispatch upgraded Critical channels
    const criticalChannels = SEVERITY_CHANNEL_MATRIX[AlertSeverity.Critical];
    const deliveries = await notification_dispatcher.dispatch_concurrent(saved, criticalChannels);
    await repository.saveDeliveries(deliveries);

    // Log to DGMS audit table
    await audit_logger.persist_alert_transaction(saved, 'escalated', {
      reason,
      automated: true,
      previous_severity: alert.severity,
      previous_ttc_hours: alert.time_to_critical_hours,
      new_ttc_hours: currentTtc
    });

    console.log(
      `[RE-EVALUATION] Alert ${alert.alert_id} auto-escalated to CRITICAL: ${reason}`
    );
    return saved;
  }

  return alert;
}

/**
 * Sweeps all active alerts and re-evaluates them.
 */
export async function reevaluate_all_active_alerts(): Promise<AlertRecord[]> {
  const activeAlerts = await repository.findActiveAlerts();
  const results: AlertRecord[] = [];

  for (const alert of activeAlerts) {
    const result = await reevaluate_single_alert(alert.alert_id);
    if (result) results.push(result);
  }

  return results;
}

/**
 * Schedules periodic re-evaluation for an alert.
 */
export function schedule_reevaluation(
  alert_id: string,
  interval_secs: number = 60
): void {
  // Clear any existing timer for this alert
  if (scheduledReevaluations.has(alert_id)) {
    clearInterval(scheduledReevaluations.get(alert_id)!);
  }

  const timer = setInterval(async () => {
    try {
      await reevaluate_single_alert(alert_id);
    } catch (err) {
      console.error(`[RE-EVALUATION ERROR] Error evaluating alert ${alert_id}:`, err);
    }
  }, interval_secs * 1000);

  // Unref so it does not block node process exit in tests/scripts
  timer.unref();

  scheduledReevaluations.set(alert_id, timer);
}

export function clear_all_reevaluations(): void {
  for (const [, timer] of scheduledReevaluations) {
    clearInterval(timer);
  }
  scheduledReevaluations.clear();
}
