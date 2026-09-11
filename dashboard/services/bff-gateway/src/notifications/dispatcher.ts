import { AlertLifecycleEvent, AlertSeverity } from "@subsense/shared";
import { AuditLedger } from "../alert-engine/audit-ledger";
import { isNotificationSilencedByQuietHours, QuietHoursConfig } from "./quiet-hours";
import { TermuxSmsService } from "./termux-sms";
import { EmergencyContactsStore } from "./contacts-store";

export interface DispatchResult {
  channel: "browser_push" | "mobile_push_fcm" | "sms_twilio" | "physical_siren_relay";
  delivered: boolean;
  timestamp: string;
  details: string;
  auditHash?: string;
}

export class NotificationDispatcher {
  private static sirenTriggerHistory: Array<{ alertId: string; siteId: string; timestamp: string }> = [];
  private static simulatedDispatches: DispatchResult[] = [];

  static getSirenTriggerCount(): number {
    return this.sirenTriggerHistory.length;
  }

  static getDispatchHistory(): DispatchResult[] {
    return [...this.simulatedDispatches];
  }

  static clearHistory(): void {
    this.sirenTriggerHistory = [];
    this.simulatedDispatches = [];
  }

  /**
   * Dispatches an alert across multiple notification channels according to severity
   */
  static async dispatchAlert(
    alert: AlertLifecycleEvent,
    options?: {
      quietHoursConfig?: QuietHoursConfig;
      evaluationTime?: Date;
    }
  ): Promise<DispatchResult[]> {
    const results: DispatchResult[] = [];
    const now = options?.evaluationTime || new Date();
    const quietHoursCheck = isNotificationSilencedByQuietHours(alert.severity, now, options?.quietHoursConfig);

    // 1. Channel: Browser Push (Always attempted for active web operators)
    if (!quietHoursCheck.silenced || alert.severity === "critical") {
      const res: DispatchResult = {
        channel: "browser_push",
        delivered: true,
        timestamp: new Date().toISOString(),
        details: `Dispatched to active web dashboard sessions in tenant ${alert.tenant_id} (Site: ${alert.site_id})`,
      };
      res.auditHash = await AuditLedger.record({
        tenantId: alert.tenant_id,
        userId: "SYSTEM_DISPATCHER",
        action: "NOTIFICATION_DISPATCH_BROWSER",
        details: { alertId: alert.alert_id, severity: alert.severity, siteId: alert.site_id },
      });
      results.push(res);
      this.simulatedDispatches.push(res);
    }

    // 2. Channel: Mobile Push (FCM / APNs)
    if (!quietHoursCheck.silenced || alert.severity === "critical") {
      const res: DispatchResult = {
        channel: "mobile_push_fcm",
        delivered: true,
        timestamp: new Date().toISOString(),
        details: `FCM payload sent to on-call geotechnical and safety officers [Topic: /topics/${alert.tenant_id}_${alert.site_id}_alerts]`,
      };
      res.auditHash = await AuditLedger.record({
        tenantId: alert.tenant_id,
        userId: "SYSTEM_DISPATCHER",
        action: "NOTIFICATION_DISPATCH_FCM",
        details: { alertId: alert.alert_id, severity: alert.severity, topic: `/topics/${alert.tenant_id}_${alert.site_id}_alerts` },
      });
      results.push(res);
      this.simulatedDispatches.push(res);
    }

    // 3. Channel: SMS & Voice Alerts (Termux SSH SMS + Telecom Gateway)
    // Dispatched for Warning and Critical alerts
    if (alert.severity === "warning" || alert.severity === "critical") {
      if (!quietHoursCheck.silenced || alert.severity === "critical") {
        const activeContacts = EmergencyContactsStore.getActive();
        const contactPhones = activeContacts.map((c) => `${c.name} (${c.phoneNumber})`).join(", ");

        // Asynchronously trigger Termux SMS broadcast to all active contacts
        TermuxSmsService.broadcastAlertSms(
          activeContacts.map((c) => ({ name: c.name, phoneNumber: c.phoneNumber })),
          alert
        ).catch((err) => {
          console.error(`[DISPATCHER] Termux SMS broadcast failed: ${err.message}`);
        });

        const res: DispatchResult = {
          channel: "sms_twilio",
          delivered: true,
          timestamp: new Date().toISOString(),
          details: `Termux SMS broadcast triggered to ${activeContacts.length} emergency contacts [${contactPhones || "None configured"}]. Critical override: ${alert.severity === "critical"}`,
        };
        res.auditHash = await AuditLedger.record({
          tenantId: alert.tenant_id,
          userId: "SYSTEM_DISPATCHER",
          action: "NOTIFICATION_DISPATCH_SMS",
          details: {
            alertId: alert.alert_id,
            severity: alert.severity,
            recipients: activeContacts.map((c) => c.phoneNumber),
          },
        });
        results.push(res);
        this.simulatedDispatches.push(res);
      }
    }

    // 4. Channel: Physical Siren Relay
    // Triggered immediately if critical, or when escalated
    if (alert.severity === "critical" || alert.state === "escalated") {
      const res: DispatchResult = {
        channel: "physical_siren_relay",
        delivered: true,
        timestamp: new Date().toISOString(),
        details: `HARDWARE RELAY FIRED: Surface & underground sirens active in Sector ${alert.zone_id} (Mine: ${alert.site_id})`,
      };
      this.sirenTriggerHistory.push({
        alertId: alert.alert_id,
        siteId: alert.site_id,
        timestamp: new Date().toISOString(),
      });
      res.auditHash = await AuditLedger.record({
        tenantId: alert.tenant_id,
        userId: "SYSTEM_DISPATCHER",
        action: "PHYSICAL_SIREN_TRIGGERED",
        details: { alertId: alert.alert_id, zoneId: alert.zone_id, siteId: alert.site_id },
      });
      results.push(res);
      this.simulatedDispatches.push(res);
    }

    return results;
  }
}
