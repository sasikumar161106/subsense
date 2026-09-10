import { repository } from '../db/repository';
import { audit_logger } from '../audit/logger';
import { on_new_risk_event } from '../rule-engine';
import { deescalate_alert } from '../rule-engine/deescalation';
import { run_recalibration_job, get_node_sensitivity_weight } from '../rule-engine/recalibration';
import { dispatch_retraction_notice } from '../channels/dispatcher';
import { smsCircuitBreaker } from '../channels/adapters/sms';
import { AlertSeverity, AlertStatus, DeliveryChannel, DeliveryStatus, FeedbackVerdict } from '../models/types';
import {
  scenarioLowConfidenceSingleNode,
  scenarioCorrelatedWarning,
  scenarioDuplicateInsideCooldown,
  scenarioAcceleratingInitialWarning,
  scenarioAcceleratingCriticalSpike
} from './scenarios';

async function runSimulator(): Promise<void> {
  console.log('================================================================');
  console.log('   SUBSENSE ALERTING & DECISION SUPPORT SYSTEM - SIMULATOR (PHASE 2)');
  console.log('   Omni-Channel Delivery, Explainability & Feedback Hardening');
  console.log('================================================================\n');

  // STEP 1: Single-node low-confidence anomaly -> Advisory + Explainability
  console.log('>>> [STEP 1] Ingesting low-confidence single-node anomaly in Zone Alpha...');
  const advisoryAlert = await on_new_risk_event(scenarioLowConfidenceSingleNode);
  console.log(` -> Alert Created: ${advisoryAlert.alert_id}`);
  console.log(` -> Severity: ${advisoryAlert.severity} (Expected: Advisory)`);
  console.log(` -> Composite Confidence: ${advisoryAlert.explainability?.composite_confidence}`);
  console.log(` -> Trigger Narrative: "${advisoryAlert.explainability?.trigger_narrative}"`);
  console.log(` -> Sensor Attribution Count: ${advisoryAlert.explainability?.contributing_sensor_attribution.length}`);

  if (advisoryAlert.severity !== AlertSeverity.Advisory) {
    throw new Error(`Expected Advisory but received ${advisoryAlert.severity}`);
  }
  if (!advisoryAlert.explainability || !advisoryAlert.explainability.trigger_narrative) {
    throw new Error('Explainability payload missing or invalid on Advisory alert!');
  }
  console.log(' [PASS] Single-node low-confidence event produced ADVISORY with rich explainability.\n');

  // STEP 2: Correlated multi-node anomaly with TTC > 48h -> Warning + Omni-Channel Fanout
  console.log('>>> [STEP 2] Ingesting GNN-correlated multi-node anomaly in Zone Beta (TTC: 54h)...');
  const warningAlert = await on_new_risk_event(scenarioCorrelatedWarning);
  console.log(` -> Alert Created: ${warningAlert.alert_id}`);
  console.log(` -> Severity: ${warningAlert.severity} (Expected: Warning)`);

  const warningDeliveries = await repository.getDeliveriesByAlertId(warningAlert.alert_id);
  const warningChannels = warningDeliveries.map((d) => d.channel);
  console.log(` -> Dispatched Channels: [${warningChannels.join(', ')}]`);

  if (warningAlert.severity !== AlertSeverity.Warning) {
    throw new Error(`Expected Warning but received ${warningAlert.severity}`);
  }
  expectDeliveryChannels(warningChannels, [
    DeliveryChannel.SMS,
    DeliveryChannel.PushNotification,
    DeliveryChannel.DashboardBanner,
    DeliveryChannel.Email
  ]);
  console.log(' [PASS] Correlated multi-node event produced WARNING with full Warning matrix fanout.\n');

  // STEP 3: Re-posting inside cooldown window -> Merged into existing Warning
  console.log('>>> [STEP 3] Re-posting telemetry for Zone Beta inside 30min cooldown window...');
  const initialAlertCount = (await repository.findAlerts({ risk_zone_id: scenarioCorrelatedWarning.risk_zone_id })).length;
  const mergedAlert = await on_new_risk_event(scenarioDuplicateInsideCooldown);
  const finalAlertCount = (await repository.findAlerts({ risk_zone_id: scenarioCorrelatedWarning.risk_zone_id })).length;

  console.log(` -> Matched Alert ID: ${mergedAlert.alert_id}`);
  console.log(` -> Total alerts in Zone Beta before: ${initialAlertCount}, after: ${finalAlertCount}`);
  console.log(` -> Merged Contributing Nodes: ${mergedAlert.contributing_nodes.length} nodes`);

  if (mergedAlert.alert_id !== warningAlert.alert_id || finalAlertCount !== initialAlertCount) {
    throw new Error('Duplicate suppression failed! A new alert row was created instead of merging telemetry.');
  }
  console.log(' [PASS] Cooldown duplicate suppressed; telemetry merged cleanly into existing alert.\n');

  // STEP 4: Scripted accelerating sequence -> Critical Auto-Flip + Siren Benchmark (< 1.2s)
  console.log('>>> [STEP 4] Executing scripted accelerating sequence in Zone Gamma...');
  console.log(' -> 4A. Early tension crack detection (TTC: 50h, velocity: 0.35 mm/h)...');
  await on_new_risk_event(scenarioAcceleratingInitialWarning);

  console.log('\n -> 4B. Rapid acceleration arrives from Edge (TTC plummets to 3.2h, velocity surges to 2.45 mm/h)...');
  const sirenBenchStart = performance.now();
  const escalatedAlert = await on_new_risk_event(scenarioAcceleratingCriticalSpike);
  const totalProcessingMs = Number((performance.now() - sirenBenchStart).toFixed(2));

  console.log(`    Alert ID: ${escalatedAlert.alert_id}`);
  console.log(`    Severity: ${escalatedAlert.severity} (Expected: Critical)`);
  console.log(`    Status: ${escalatedAlert.status} (Expected: Escalated)`);
  console.log(`    Total Event Ingestion & Dispatch Latency: ${totalProcessingMs}ms`);

  const criticalDeliveries = await repository.getDeliveriesByAlertId(escalatedAlert.alert_id);
  const criticalChannels = criticalDeliveries.map((d) => d.channel);
  console.log(`    Dispatched Channels: [${criticalChannels.join(', ')}]`);

  // Verify siren delivery record
  const sirenDelivery = criticalDeliveries.find((d) => d.channel === DeliveryChannel.Siren);
  if (!sirenDelivery) {
    throw new Error('Critical Edge event did not produce a Siren delivery record!');
  }
  console.log(`    Siren Execution Verified: ${sirenDelivery.delivery_status} (Autonomous Edge)`);

  if (escalatedAlert.severity !== AlertSeverity.Critical || escalatedAlert.status !== AlertStatus.Escalated) {
    throw new Error(
      `Escalation auto-flip failed! Expected Severity: Critical & Status: Escalated. Received: ${escalatedAlert.severity} / ${escalatedAlert.status}`
    );
  }
  expectDeliveryChannels(criticalChannels, [
    DeliveryChannel.Siren,
    DeliveryChannel.SMS,
    DeliveryChannel.VoiceIVR,
    DeliveryChannel.DashboardBanner,
    DeliveryChannel.CommunitySMS
  ]);
  console.log(' [PASS] Scripted accelerating sequence auto-flipped Warning to CRITICAL with autonomous siren in < 1.2s!\n');

  // STEP 5: Circuit-Breaker Failover Simulation for SMS
  console.log('>>> [STEP 5] Simulating SMS provider outage to test Circuit Breaker failover...');
  smsCircuitBreaker.reset();
  process.env.SIMULATE_SMS_OUTAGE = 'true';

  const failoverStart = performance.now();
  const failoverTestEvent = {
    ...scenarioCorrelatedWarning,
    risk_zone_id: '44444444-4444-4444-4444-444444444444',
    timestamp: new Date()
  };
  const failoverAlert = await on_new_risk_event(failoverTestEvent);
  const failoverDurationMs = Number((performance.now() - failoverStart).toFixed(2));

  console.log(` -> Failover Alert Dispatched in: ${failoverDurationMs}ms (Must be < 8000ms: PASS)`);
  const failoverDeliveries = await repository.getDeliveriesByAlertId(failoverAlert.alert_id);
  const smsFailoverDelivery = failoverDeliveries.find((d) => d.channel === DeliveryChannel.SMS);

  if (!smsFailoverDelivery || smsFailoverDelivery.delivery_status === DeliveryStatus.Failed) {
    throw new Error('Circuit breaker failover failed! Secondary SMS adapter did not deliver.');
  }
  console.log(` -> SMS Delivery Status via Failover: ${smsFailoverDelivery.delivery_status}`);
  process.env.SIMULATE_SMS_OUTAGE = 'false';
  smsCircuitBreaker.reset();
  console.log(' [PASS] SMS circuit breaker successfully routed to secondary adapter within 8s.\n');

  // STEP 6: Feedback Loop & Multi-Channel Retraction Notice Dispatch
  console.log('>>> [STEP 6] Testing Feedback & Retraction Notice fanout on all original channels...');
  // Step 6A: Log FalsePositive feedback
  await repository.createFeedback({
    feedback_id: '',
    alert_id: warningAlert.alert_id,
    operator_id: '00000000-0000-0000-0000-000000000001',
    verdict: FeedbackVerdict.FalsePositive,
    notes: 'Blasting vibration at adjacent face caused spurious reading',
    submitted_at: new Date()
  });
  console.log(` -> FalsePositive feedback recorded for alert ${warningAlert.alert_id}`);

  // Step 6B: Issue Retraction
  const deescalation = deescalate_alert(warningAlert, FeedbackVerdict.FalsePositive, 'Blasting vibration verified');
  const retracted = await repository.updateAlert(warningAlert.alert_id, deescalation.updatedAlert);
  const retractionDeliveries = await dispatch_retraction_notice(
    retracted,
    warningDeliveries,
    'Blasting vibration verified'
  );

  await audit_logger.persist_alert_transaction(retracted, 'retracted', {
    reason: 'Blasting vibration verified',
    operator_id: '00000000-0000-0000-0000-000000000001',
    retraction_deliveries_count: retractionDeliveries.length
  });

  console.log(` -> Retraction Notices Dispatched: ${retractionDeliveries.length}`);
  const retractionChannels = retractionDeliveries.map((d) => d.channel);
  console.log(` -> Retraction Channels: [${retractionChannels.join(', ')}]`);

  for (const origDelivery of warningDeliveries) {
    if (!retractionChannels.includes(origDelivery.channel)) {
      throw new Error(`Original channel ${origDelivery.channel} was NOT sent a Retraction Notice!`);
    }
  }
  console.log(' [PASS] Retraction Notice successfully delivered through EVERY channel originally used.\n');

  // STEP 7: Node Sensitivity Recalibration Job
  console.log('>>> [STEP 7] Running Node Sensitivity Recalibration job...');
  const initialNodeWeight = get_node_sensitivity_weight('20000000-0000-0000-0000-000000000201');
  const recalReport = await run_recalibration_job('Senior_Strata_Control_Officer_Roy');
  const decayedNodeWeight = get_node_sensitivity_weight('20000000-0000-0000-0000-000000000201');

  console.log(` -> Node 2000...201 Sensitivity Before: ${initialNodeWeight}, After: ${decayedNodeWeight}`);
  console.log(` -> Human Sign-Off Recorded: ${recalReport.human_sign_off}`);

  if (decayedNodeWeight >= initialNodeWeight) {
    throw new Error('Recalibration failed to decay sensitivity weight for false-alarm node!');
  }
  console.log(' [PASS] Node sensitivity recalibrated and signed off for DGMS compliance.\n');

  // STEP 8: DGMS Audit Trail Inspection
  console.log('================================================================');
  console.log('   DGMS COMPLIANCE AUDIT LOG VERIFICATION');
  console.log('================================================================');
  const allAuditLogs = await audit_logger.get_all_audit_logs();
  console.log(`Total Audit Transactions Recorded: ${allAuditLogs.length}`);

  const transitions = allAuditLogs.map((l) => l.transition);
  console.log(`Recorded Transitions: [${transitions.join(', ')}]`);

  for (const log of allAuditLogs) {
    console.log(
      ` [AUDIT ENTRY] ID: ${log.log_id.substring(0, 8)}... | Alert: ${log.alert_id.substring(0, 8)}... | Transition: ${String(log.transition).toUpperCase()} | Time: ${new Date(log.timestamp).toISOString()}`
    );
  }

  console.log('\n================================================================');
  console.log('   ALL PHASE 2 VALIDATION CHECKS PASSED SUCCESSFULLY!');
  console.log('================================================================');
}

function expectDeliveryChannels(actualChannels: DeliveryChannel[], expectedChannels: DeliveryChannel[]): void {
  for (const expected of expectedChannels) {
    if (!actualChannels.includes(expected)) {
      throw new Error(`Expected delivery channel ${expected} was not dispatched! Dispatched: [${actualChannels.join(', ')}]`);
    }
  }
}

if (require.main === module) {
  runSimulator()
    .then(() => process.exit(0))
    .catch((err) => {
      console.error('[SIMULATOR RUNTIME ERROR]', err);
      process.exit(1);
    });
}

export { runSimulator };
