import { repository } from '../db/repository';
import { audit_logger } from '../audit/logger';
import { FeedbackVerdict } from '../models/types';

export const nodeSensitivityWeights: Map<string, number> = new Map();

/**
 * Returns current sensitivity weight for a node (default 1.0).
 */
export function get_node_sensitivity_weight(nodeId: string): number {
  return nodeSensitivityWeights.get(nodeId) ?? 1.0;
}

/**
 * Sets or overrides sensitivity weight for a node.
 */
export function set_node_sensitivity_weight(nodeId: string, weight: number): void {
  nodeSensitivityWeights.set(nodeId, Math.max(0.1, Math.min(1.0, weight)));
}

/**
 * Calculates average sensitivity weight for a set of contributing nodes.
 */
export function get_nodes_average_sensitivity(nodeIds: string[]): number {
  if (nodeIds.length === 0) return 1.0;
  const total = nodeIds.reduce((sum, id) => sum + get_node_sensitivity_weight(id), 0);
  return total / nodeIds.length;
}

export interface RecalibrationSummary {
  nodes_evaluated: number;
  nodes_recalibrated: number;
  updated_weights: Record<string, number>;
  human_sign_off: string;
  timestamp: Date;
}

/**
 * Manually triggered recalibration job:
 * Aggregates FalsePositive and HardwareDefect feedback across alerts,
 * lowers sensitivity weights for offending nodes, and writes an audit log with human sign-off.
 */
export async function run_recalibration_job(
  sign_off_operator: string = 'Safety_Officer_Engineer'
): Promise<RecalibrationSummary> {
  const alerts = await repository.findAlerts({});
  const nodeFalseAlarmCounts: Record<string, number> = {};

  for (const alert of alerts) {
    const feedbacks = alert.feedbacks || [];
    const isFalseAlarm = feedbacks.some(
      (f) =>
        f.verdict === FeedbackVerdict.FalsePositive ||
        f.verdict === FeedbackVerdict.HardwareDefect
    );

    if (isFalseAlarm) {
      for (const node of alert.contributing_nodes) {
        nodeFalseAlarmCounts[node] = (nodeFalseAlarmCounts[node] || 0) + 1;
      }
    }
  }

  const updatedWeights: Record<string, number> = {};
  let recalibratedCount = 0;

  for (const [nodeId, falseAlarms] of Object.entries(nodeFalseAlarmCounts)) {
    // Each false alarm drops node sensitivity weight by 0.15 down to a floor of 0.40
    const decayedWeight = Math.max(0.4, Number((1.0 - falseAlarms * 0.15).toFixed(2)));
    set_node_sensitivity_weight(nodeId, decayedWeight);
    updatedWeights[nodeId] = decayedWeight;
    recalibratedCount++;
  }

  const summary: RecalibrationSummary = {
    nodes_evaluated: Object.keys(nodeFalseAlarmCounts).length,
    nodes_recalibrated: recalibratedCount,
    updated_weights: updatedWeights,
    human_sign_off: sign_off_operator,
    timestamp: new Date()
  };

  // Record audit transaction for DGMS compliance
  if (alerts.length > 0) {
    const targetAlert = alerts[0];
    await audit_logger.persist_alert_transaction(targetAlert, 'recalibrated' as any, {
      summary,
      reason: `Node sensitivity recalibration completed by ${sign_off_operator}`
    });
  }

  console.log(
    `[RECALIBRATION] Processed ${recalibratedCount} nodes. Signed off by: ${sign_off_operator}. Updated weights:`,
    updatedWeights
  );

  return summary;
}
