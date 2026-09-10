import { repository } from '../db/repository';
import { audit_logger } from '../audit/logger';
import {
  AlertRecord,
  AlertSeverity,
  AlertSource,
  AlertStatus,
  RiskEvent,
  SEVERITY_CHANNEL_MATRIX
} from '../models/types';
import { sirenActuator } from '../channels/adapters/siren';
import { dispatch_concurrent } from '../channels/dispatcher';
import { classify_severity } from './classifier';
import {
  is_active_duplicate,
  merge_telemetry,
  DEFAULT_COOLDOWN_WARNING_MINS
} from './deduplication';
import { generate_explainability_payload } from './explainability';
import { generate_idempotency_key } from './idempotency';
import { schedule_reevaluation } from './reevaluation';

export * from './classifier';
export * from './deduplication';
export * from './spatial';
export * from './escalation';
export * from './deescalation';
export * from './idempotency';
export * from './actuators';
export * from './dispatchers';
export * from './reevaluation';
export * from './explainability';
export * from './recalibration';

/**
 * Main control flow pipeline for Phase 2:
 * Ingests RiskEvent, generates explainability payload, evaluates deduplication/escalation,
 * triggers autonomous edge sirens (< 1.2s), and dispatches via resilient omni-channel matrix.
 */
export async function on_new_risk_event(
  event: RiskEvent,
  cooldown_mins: number = DEFAULT_COOLDOWN_WARNING_MINS
): Promise<AlertRecord> {
  const zone_id = event.risk_zone_id;

  // 1. Fetch currently active alerts for this zone
  const openAlerts = await repository.findActiveAlerts(zone_id);

  // 2. Check for active duplicate within cooldown
  const duplicateAlert = is_active_duplicate(zone_id, event, openAlerts, cooldown_mins);

  if (duplicateAlert) {
    console.log(
      `[RULE ENGINE] Active duplicate detected for zone ${zone_id} (Alert ID: ${duplicateAlert.alert_id}). Merging telemetry.`
    );

    const mergeResult = merge_telemetry(duplicateAlert, event);
    const explainability = generate_explainability_payload(event);
    const updatedAlertWithExplain = {
      ...mergeResult.updatedAlert,
      explainability
    };

    const updated = await repository.updateAlert(duplicateAlert.alert_id, updatedAlertWithExplain);

    if (mergeResult.escalated) {
      console.log(
        `[RULE ENGINE] Telemetry merge triggered auto-escalation to CRITICAL for alert ${updated.alert_id}!`
      );

      // Trigger siren if Edge source (< 1.2s autonomous)
      if (event.source === AlertSource.Edge) {
        await sirenActuator.send(updated, 'on_ground_local_siren');
      }

      // Dispatch critical channels concurrently
      const channels = SEVERITY_CHANNEL_MATRIX[AlertSeverity.Critical];
      await dispatch_concurrent(updated, channels);

      // Record escalation transition in audit log
      await audit_logger.persist_alert_transaction(updated, 'escalated', {
        reason: 'Accelerating velocity or TTC dropped below emergency threshold on telemetry merge',
        triggering_event: event,
        previous_severity: mergeResult.previousSeverity,
        previous_status: mergeResult.previousStatus,
        explainability
      });
    } else {
      // Record merged transition in audit log
      await audit_logger.persist_alert_transaction(updated, 'merged', {
        triggering_event: event,
        explainability
      });
    }

    return updated;
  }

  // 3. Classify severity using pure rule function
  const velocity = event.progression_rate ?? event.velocity_delta ?? 0;
  const ttc =
    event.time_to_critical_hours !== undefined
      ? event.time_to_critical_hours
      : event.time_to_critical !== undefined
      ? event.time_to_critical
      : null;

  const severity = classify_severity({
    anomaly_score: event.anomaly_score,
    correlation_strength: event.correlation_strength,
    velocity_delta: velocity,
    ttc_hours: ttc,
    confidence: event.confidence,
    contributing_nodes: event.contributing_nodes
  });

  // 4. Generate idempotency key
  const idempotencyKey = generate_idempotency_key(zone_id, event.timestamp);

  // 5. Generate dynamic explainability payload
  const explainability = generate_explainability_payload(event);

  // 6. Create alert record
  const alert = await repository.createAlert({
    tenant_id: event.tenant_id,
    risk_zone_id: zone_id,
    severity,
    status: AlertStatus.Active,
    confidence_score: event.confidence,
    time_to_critical_hours: explainability.time_to_critical_hours,
    explanation: event.explanation,
    contributing_nodes: event.contributing_nodes,
    contributing_sensors: event.contributing_sensors || [],
    source: event.source,
    idempotency_key: idempotencyKey,
    explainability
  });

  // 7. If CRITICAL and EDGE -> trigger on-ground siren autonomously (< 1.2s, network independent)
  if (severity === AlertSeverity.Critical && event.source === AlertSource.Edge) {
    await sirenActuator.send(alert, 'on_ground_local_siren');
  }

  // 8. Dispatch notifications concurrently according to severity channel matrix
  const channels = SEVERITY_CHANNEL_MATRIX[severity];
  await dispatch_concurrent(alert, channels);

  // 9. Persist audit transaction
  await audit_logger.persist_alert_transaction(alert, 'created', {
    triggering_event: event,
    channels_dispatched: channels,
    explainability
  });

  // 10. Schedule periodic re-evaluation every 60 seconds
  schedule_reevaluation(alert.alert_id, 60);

  return alert;
}
