/**
 * SubSense BFF Gateway -> Alert_System Client.
 * Bridges Layer 6 (Dashboard BFF) to Layer 3/4 Alert_System (:3000):
 * - Proxies alert queries, acknowledgements, feedback, and retraction
 * - Translates vocabulary between Dashboard and Alert_System contracts
 * - Subscribes to Alert_System WebSocket live feed (ws://localhost:3000/ws/alerts)
 */

import { WebSocket } from "ws";
import {
  AlertLifecycleEvent,
  AlertSeverity,
  AlertState,
  FalseAlarmReason,
} from "@subsense/shared";

export const ALERT_SYSTEM_HTTP_URL =
  process.env.ALERT_SYSTEM_URL || "http://localhost:3000";
export const ALERT_SYSTEM_WS_URL =
  process.env.ALERT_SYSTEM_WS_URL || "ws://localhost:3000/ws/alerts";
export const ALERT_SYSTEM_API_KEY =
  process.env.ALERT_SYSTEM_API_KEY || "subsense-safety-key-2026";

export function mapFeedbackReasonToVerdict(reason: string): string {
  const r = reason.toLowerCase();
  if (
    r.includes("glitch") ||
    r.includes("hardware") ||
    r.includes("defect") ||
    r.includes("instrument") ||
    r.includes("jitter")
  ) {
    return "HardwareDefect";
  }
  if (
    r.includes("false") ||
    r.includes("blasting") ||
    r.includes("vehicle") ||
    r.includes("thermal") ||
    r.includes("seismic") ||
    r.includes("noise")
  ) {
    return "FalsePositive";
  }
  if (r.includes("true") || r.includes("confirmed")) {
    return "Confirmed";
  }
  return "Unclear";
}

export function alertRecordToLifecycleEvent(record: any): AlertLifecycleEvent {
  // Normalize severity
  let severity: AlertSeverity = "warning";
  const rawSev = (record.severity || "").toLowerCase();
  if (rawSev === "critical") severity = "critical";
  else if (rawSev === "advisory" || rawSev === "info") severity = "info";

  // Normalize state
  let state: AlertState = "new";
  const rawStatus = (record.status || "").toLowerCase();
  if (rawStatus === "retracted" || rawStatus === "de-escalated") {
    state = "false_alarm";
  } else if (rawStatus === "resolved") {
    state = "resolved";
  } else if (rawStatus === "escalated") {
    state = "escalated";
  } else if (record.acknowledged_at) {
    state = "acknowledged";
  }

  // Time to critical tuple [min, max]
  const ttcSingle = record.time_to_critical_hours;
  let ttcTuple: [number, number];
  if (Array.isArray(ttcSingle) && ttcSingle.length === 2) {
    ttcTuple = [Number(ttcSingle[0]), Number(ttcSingle[1])];
  } else if (typeof ttcSingle === "number") {
    ttcTuple = [
      Math.max(0.5, Number((ttcSingle * 0.75).toFixed(1))),
      Number((ttcSingle * 1.25).toFixed(1)),
    ];
  } else {
    ttcTuple = severity === "critical" ? [1.5, 4.0] : [6.0, 14.0];
  }

  const raisedAt = record.created_at
    ? new Date(record.created_at).toISOString()
    : new Date().toISOString();

  return {
    alert_id: record.alert_id || `ALERT-${record.risk_zone_id}-${Date.now()}`,
    tenant_id: record.tenant_id || "OPCO-ECL-01",
    site_id: record.site_id || "PANEL7-JHARIA",
    zone_id: record.risk_zone_id || "PANEL7-ZONE-C",
    severity,
    state,
    raised_at: raisedAt,
    acknowledged_by: record.acknowledged_by || null,
    acknowledged_at: record.acknowledged_at
      ? new Date(record.acknowledged_at).toISOString()
      : null,
    time_to_critical_hours: ttcTuple,
    confidence_score: Number(record.confidence_score ?? 0.85),
    contributing_sensors: record.contributing_sensors || ["tilt_deg"],
    explanation_summary:
      record.explanation ||
      record.explainability?.trigger_narrative ||
      `Subsidence risk alert in zone ${record.risk_zone_id || ""}`,
  };
}

export class AlertSystemClient {
  private static wsClient: WebSocket | null = null;
  private static reconnectTimer: NodeJS.Timeout | null = null;
  private static listeners: Set<(event: string, alert: AlertLifecycleEvent) => void> =
    new Set();

  /**
   * Fetches alerts from Alert_System with query filters.
   */
  static async fetchAlerts(filter: {
    zone_id?: string;
    risk_zone_id?: string;
    severity?: string;
    status?: string;
    tenant_id?: string;
  } = {}): Promise<AlertLifecycleEvent[]> {
    const url = new URL("/api/v1/alerts", ALERT_SYSTEM_HTTP_URL);
    if (filter.zone_id || filter.risk_zone_id) {
      url.searchParams.set("risk_zone_id", (filter.risk_zone_id || filter.zone_id)!);
    }
    if (filter.severity) url.searchParams.set("severity", filter.severity);
    if (filter.status) url.searchParams.set("status", filter.status);
    if (filter.tenant_id) url.searchParams.set("tenant_id", filter.tenant_id);

    const res = await fetch(url.toString(), {
      headers: {
        "x-api-key": ALERT_SYSTEM_API_KEY,
        Accept: "application/json",
      },
    });

    if (!res.ok) {
      throw new Error(`Alert_System GET /api/v1/alerts failed: ${res.status} ${res.statusText}`);
    }

    const data = (await res.json()) as any[];
    return data.map(alertRecordToLifecycleEvent);
  }

  /**
   * Retrieves single alert by ID.
   */
  static async getAlertById(alertId: string): Promise<AlertLifecycleEvent> {
    const url = `${ALERT_SYSTEM_HTTP_URL}/api/v1/alerts/${alertId}`;
    const res = await fetch(url, {
      headers: {
        "x-api-key": ALERT_SYSTEM_API_KEY,
        Accept: "application/json",
      },
    });

    if (!res.ok) {
      throw new Error(`Alert_System GET /api/v1/alerts/${alertId} failed: ${res.status}`);
    }

    const data = await res.json();
    return alertRecordToLifecycleEvent(data);
  }

  /**
   * Acknowledges an alert in Alert_System.
   */
  static async acknowledgeAlert(
    alertId: string,
    userId: string,
    comment?: string
  ): Promise<AlertLifecycleEvent> {
    const url = `${ALERT_SYSTEM_HTTP_URL}/api/v1/alerts/${alertId}/acknowledge`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ALERT_SYSTEM_API_KEY,
      },
      body: JSON.stringify({ operator_id: userId, comment }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Alert_System acknowledge failed: ${res.status} ${errText}`);
    }

    const data = (await res.json()) as any;
    return alertRecordToLifecycleEvent(data.alert || data);
  }

  /**
   * Submits operator feedback (translating FalseAlarmReason -> FeedbackVerdict).
   */
  static async submitFeedback(
    alertId: string,
    userId: string,
    reason: string,
    notes?: string
  ): Promise<{ feedback: any; alert: AlertLifecycleEvent }> {
    const verdict = mapFeedbackReasonToVerdict(reason);
    const url = `${ALERT_SYSTEM_HTTP_URL}/api/v1/alerts/${alertId}/feedback`;

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ALERT_SYSTEM_API_KEY,
      },
      body: JSON.stringify({
        operator_id: userId,
        verdict,
        notes: notes || `Dashboard operator flagged: ${reason}`,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Alert_System feedback failed: ${res.status} ${errText}`);
    }

    const data = (await res.json()) as any;
    return {
      feedback: data.feedback,
      alert: alertRecordToLifecycleEvent(data.alert || data),
    };
  }

  /**
   * Retracts an alert in Alert_System.
   */
  static async retractAlert(
    alertId: string,
    userId: string,
    reason?: string
  ): Promise<{ alert: AlertLifecycleEvent; retraction_deliveries: any[] }> {
    const url = `${ALERT_SYSTEM_HTTP_URL}/api/v1/alerts/${alertId}/retract`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ALERT_SYSTEM_API_KEY,
      },
      body: JSON.stringify({
        operator_id: userId,
        reason: reason || "False alarm verified by dashboard operator",
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Alert_System retract failed: ${res.status} ${errText}`);
    }

    const data = (await res.json()) as any;
    return {
      alert: alertRecordToLifecycleEvent(data.alert || data),
      retraction_deliveries: data.retraction_deliveries || [],
    };
  }

  /**
   * Subscribes to Alert_System WebSocket stream and forwards incoming alerts.
   */
  static subscribeToAlertStream(
    listener: (event: string, alert: AlertLifecycleEvent) => void
  ): () => void {
    this.listeners.add(listener);
    this.ensureWebSocketConnected();

    return () => {
      this.listeners.delete(listener);
    };
  }

  private static ensureWebSocketConnected() {
    if (this.wsClient && (this.wsClient.readyState === WebSocket.OPEN || this.wsClient.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.wsClient = new WebSocket(ALERT_SYSTEM_WS_URL);

      this.wsClient.on("open", () => {
        console.log(`[BFF -> ALERT_SYSTEM] Connected to WebSocket at ${ALERT_SYSTEM_WS_URL}`);
      });

      this.wsClient.on("message", (raw: any) => {
        try {
          const parsed = JSON.parse(raw.toString());
          // Alert_System sends { type: 'alert_created' | 'siren_triggered' | 'alert_retracted', alert: AlertRecord }
          const eventType = parsed.type === "alert_retracted" ? "alert_retracted" : "alert_raised";
          const rawAlert = parsed.alert || parsed.payload || parsed;
          if (rawAlert && (rawAlert.alert_id || rawAlert.risk_zone_id)) {
            const mapped = alertRecordToLifecycleEvent(rawAlert);
            for (const listener of this.listeners) {
              listener(eventType, mapped);
            }
          }
        } catch (e) {
          // non-json or ping
        }
      });

      this.wsClient.on("error", (err) => {
        // Silently handle connection refusal during development / offline tests
      });

      this.wsClient.on("close", () => {
        this.wsClient = null;
        if (!this.reconnectTimer) {
          this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            if (this.listeners.size > 0) {
              this.ensureWebSocketConnected();
            }
          }, 5000);
        }
      });
    } catch {
      // ignore init errors
    }
  }
}
