import { AlertLifecycleEvent, AlertState, FalseAlarmReason } from "@subsense/shared";
import { withSystemScope } from "../db/client";
import { NotificationDispatcher } from "../notifications/dispatcher";
import { AuditLedger } from "./audit-ledger";

interface ActiveTimer {
  alertId: string;
  tenantId: string;
  siteId: string;
  severity: "info" | "warning" | "critical";
  timerId: NodeJS.Timeout;
  expiresAt: number;
}

export class AlertEscalationEngine {
  private static activeTimers: Map<string, ActiveTimer> = new Map();
  private static defaultTimeoutMs: number = 5 * 60 * 1000; // 5 minutes standard safety rule
  private static eventListeners: Array<(event: { type: string; alert: any }) => void> = [];

  static subscribe(listener: (event: { type: string; alert: any }) => void) {
    this.eventListeners.push(listener);
    return () => {
      this.eventListeners = this.eventListeners.filter((l) => l !== listener);
    };
  }

  private static emitEvent(type: string, alert: any) {
    for (const l of this.eventListeners) {
      try {
        l({ type, alert });
      } catch (err) {
        console.error("Error in alert event listener:", err);
      }
    }
  }

  /**
   * Overrides timeout duration (used for tests or simulation). Default is 300,000 ms (5 mins).
   */
  static setDefaultTimeoutMs(ms: number) {
    this.defaultTimeoutMs = ms;
  }

  static getActiveTimer(alertId: string): { expiresAt: number; remainingMs: number } | null {
    const timer = this.activeTimers.get(alertId);
    if (!timer) return null;
    return {
      expiresAt: timer.expiresAt,
      remainingMs: Math.max(0, timer.expiresAt - Date.now()),
    };
  }

  /**
   * Registers an alert in the escalation engine.
   * If severity is warning or critical, arms a server-side escalation timer.
   */
  static async registerAlert(
    alert: AlertLifecycleEvent,
    customTimeoutMs?: number
  ): Promise<void> {
    const timeout = customTimeoutMs ?? this.defaultTimeoutMs;

    // Dispatches initial notifications
    await NotificationDispatcher.dispatchAlert(alert);

    // Only warning and critical alerts require 5-minute audible acknowledgement
    if (alert.severity === "warning" || alert.severity === "critical") {
      // Clear any existing timer for this alertId
      this.clearTimer(alert.alert_id);

      const expiresAt = Date.now() + timeout;

      const timerId = setTimeout(async () => {
        await this.handleEscalationTimeout(alert.alert_id);
      }, timeout);

      this.activeTimers.set(alert.alert_id, {
        alertId: alert.alert_id,
        tenantId: alert.tenant_id,
        siteId: alert.site_id,
        severity: alert.severity,
        timerId,
        expiresAt,
      });
    }

    this.emitEvent("alert_raised", alert);
  }

  /**
   * Server-Side Safety Escalation: Fired automatically when 5-minute acknowledgement window expires.
   */
  static async handleEscalationTimeout(alertId: string): Promise<void> {
    this.activeTimers.delete(alertId);

    await withSystemScope(async (client) => {
      // Check if still in state 'new'
      const check = await client.query(
        "SELECT * FROM alert_lifecycle_events WHERE alert_id = $1;",
        [alertId]
      );

      if (check.rows.length === 0) return;
      const alert = check.rows[0];

      if (alert.state === "new") {
        const escalatedAt = new Date().toISOString();

        await client.query(
          `UPDATE alert_lifecycle_events 
           SET state = 'escalated', escalated_at = $1 
           WHERE alert_id = $2;`,
          [escalatedAt, alertId]
        );

        const updatedAlert: AlertLifecycleEvent = {
          ...alert,
          state: "escalated",
          escalated_at: escalatedAt,
          time_to_critical_hours: [alert.time_to_critical_min, alert.time_to_critical_max],
        };

        // CRITICAL FAIL-SAFE: Trigger automated manager phone dispatch + physical mine sirens!
        await NotificationDispatcher.dispatchAlert(updatedAlert);

        await AuditLedger.record({
          tenantId: alert.tenant_id,
          userId: "SERVER_ESCALATION_DAEMON",
          action: "ALERT_AUTOMATICALLY_ESCALATED_5MIN_TIMEOUT",
          details: {
            alertId,
            siteId: alert.site_id,
            reason: "Unacknowledged within 5-minute mandatory safety window",
          },
        });

        this.emitEvent("alert_escalated", updatedAlert);
      }
    });
  }

  /**
   * Operator acknowledges alert, disarming the countdown
   */
  static async acknowledgeAlert(
    alertId: string,
    userId: string,
    comment?: string
  ): Promise<AlertLifecycleEvent> {
    this.clearTimer(alertId);

    return await withSystemScope(async (client) => {
      const ackAt = new Date().toISOString();
      const res = await client.query(
        `UPDATE alert_lifecycle_events 
         SET state = 'acknowledged', acknowledged_by = $1, acknowledged_at = $2 
         WHERE alert_id = $3
         RETURNING *;`,
        [userId, ackAt, alertId]
      );

      if (res.rows.length === 0) {
        throw new Error(`Alert ${alertId} not found`);
      }

      const alert = res.rows[0];
      await AuditLedger.record({
        tenantId: alert.tenant_id,
        userId,
        action: "ALERT_ACKNOWLEDGED_AUDIBLE_CONFIRMED",
        details: { alertId, comment: comment || "Acknowledged by operator" },
      });

      const updatedAlert: AlertLifecycleEvent = {
        ...alert,
        state: "acknowledged",
        acknowledged_by: userId,
        acknowledged_at: ackAt,
        time_to_critical_hours: [alert.time_to_critical_min, alert.time_to_critical_max],
      };

      this.emitEvent("alert_acknowledged", updatedAlert);
      return updatedAlert;
    });
  }

  /**
   * False Alarm categorization feeding Layer 4 retraining loop
   */
  static async flagFalseAlarm(
    alertId: string,
    userId: string,
    reason: FalseAlarmReason,
    notes: string,
    featureVectorSnapshot?: Record<string, any>
  ): Promise<AlertLifecycleEvent> {
    this.clearTimer(alertId);

    return await withSystemScope(async (client) => {
      const res = await client.query(
        `UPDATE alert_lifecycle_events 
         SET state = 'false_alarm', false_alarm_reason = $1, false_alarm_notes = $2 
         WHERE alert_id = $3
         RETURNING *;`,
        [reason, notes, alertId]
      );

      if (res.rows.length === 0) {
        throw new Error(`Alert ${alertId} not found`);
      }

      const alert = res.rows[0];

      // Dispatched to Layer 4 AI retraining queue / webhook stub
      await AuditLedger.record({
        tenantId: alert.tenant_id,
        userId,
        action: "LAYER4_RETRAINING_FALSE_ALARM_VECTOR_EMITTED",
        details: {
          alertId,
          reason,
          notes,
          featureVector: featureVectorSnapshot || {
            contributing_sensors: alert.contributing_sensors,
            confidence_score: alert.confidence_score,
            false_alarm_flag: true,
          },
        },
      });

      const updatedAlert: AlertLifecycleEvent = {
        ...alert,
        state: "false_alarm",
        false_alarm_reason: reason,
        false_alarm_notes: notes,
        time_to_critical_hours: [alert.time_to_critical_min, alert.time_to_critical_max],
      };

      this.emitEvent("alert_false_alarm", updatedAlert);
      return updatedAlert;
    });
  }

  /**
   * Resolves an alert
   */
  static async resolveAlert(
    alertId: string,
    userId: string
  ): Promise<AlertLifecycleEvent> {
    this.clearTimer(alertId);

    return await withSystemScope(async (client) => {
      const resolvedAt = new Date().toISOString();
      const res = await client.query(
        `UPDATE alert_lifecycle_events 
         SET state = 'resolved', resolved_at = $1, resolved_by = $2 
         WHERE alert_id = $3
         RETURNING *;`,
        [resolvedAt, userId, alertId]
      );

      if (res.rows.length === 0) {
        throw new Error(`Alert ${alertId} not found`);
      }

      const alert = res.rows[0];
      await AuditLedger.record({
        tenantId: alert.tenant_id,
        userId,
        action: "ALERT_RESOLVED",
        details: { alertId, resolvedAt },
      });

      const updatedAlert: AlertLifecycleEvent = {
        ...alert,
        state: "resolved",
        resolved_at: resolvedAt,
        resolved_by: userId,
        time_to_critical_hours: [alert.time_to_critical_min, alert.time_to_critical_max],
      };

      this.emitEvent("alert_resolved", updatedAlert);
      return updatedAlert;
    });
  }

  private static clearTimer(alertId: string): void {
    const active = this.activeTimers.get(alertId);
    if (active) {
      clearTimeout(active.timerId);
      this.activeTimers.delete(alertId);
    }
  }

  static clearAllTimers(): void {
    for (const timer of this.activeTimers.values()) {
      clearTimeout(timer.timerId);
    }
    this.activeTimers.clear();
  }
}
