import { AlertRecord, AlertStatus, FeedbackVerdict } from '../models/types';

export interface DeescalationResult {
  retracted: boolean;
  updatedAlert: AlertRecord;
  reason: string;
}

/**
 * Pure function: Given a "ruled out as hardware fault" input (e.g. HardwareDefect feedback or operator override),
 * updates the alert status to Retracted.
 */
export function deescalate_alert(
  alert: AlertRecord,
  verdictOrReason: FeedbackVerdict | string,
  notes?: string | null
): DeescalationResult {
  const isHardwareDefect =
    verdictOrReason === FeedbackVerdict.HardwareDefect ||
    (typeof verdictOrReason === 'string' &&
      verdictOrReason.toLowerCase().includes('hardware'));

  const reason = notes
    ? `${verdictOrReason}: ${notes}`
    : `Alert retracted due to: ${verdictOrReason}`;

  const updatedAlert: AlertRecord = {
    ...alert,
    status: AlertStatus.Retracted,
    explanation: `${alert.explanation} [RETRACTED: ${reason}]`,
    updated_at: new Date()
  };

  return {
    retracted: true,
    updatedAlert,
    reason
  };
}
