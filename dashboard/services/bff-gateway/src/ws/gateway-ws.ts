import { FastifyInstance } from "fastify";
import { WebSocket } from "ws";
import { NodeTelemetryRecord } from "@subsense/shared";
import { AlertEscalationEngine } from "../alert-engine/escalation-timer";

interface ConnectedClient {
  socket: WebSocket;
  tenantId: string;
  siteId: string;
  userId: string;
}

export class GatewayWebSocketServer {
  private static clients: Set<ConnectedClient> = new Set();
  private static telemetryInterval: NodeJS.Timeout | null = null;

  static register(fastify: FastifyInstance) {
    // Listen for alert engine events and broadcast immediately (≤1.5s NFR latency!)
    AlertEscalationEngine.subscribe(({ type, alert }) => {
      this.broadcastAlert(type, alert);
    });

    fastify.get("/ws/live", { websocket: true }, (connection: any, req) => {
      const socket = connection.socket;
      const query = req.query as any;
      const tenantId = query.tenant_id || "OPCO-ECL-01";
      const siteId = query.site_id || "PANEL7-JHARIA";
      const userId = query.user_id || "USR-OP-8492";

      const client: ConnectedClient = { socket, tenantId, siteId, userId };
      this.clients.add(client);

      // Send initial welcome & connection confirmation
      socket.send(
        JSON.stringify({
          event: "connected",
          data: {
            message: "SubSense BFF WebSocket Stream Established",
            tenant_id: tenantId,
            site_id: siteId,
            connected_at: new Date().toISOString(),
          },
        })
      );

      socket.on("message", (raw: any) => {
        try {
          const msg = JSON.parse(raw.toString());
          if (msg.event === "ping") {
            socket.send(JSON.stringify({ event: "pong", timestamp: Date.now() }));
          } else if (msg.event === "subscribe_site") {
            client.siteId = msg.site_id;
            client.tenantId = msg.tenant_id || client.tenantId;
          }
        } catch {
          // ignore malformed message
        }
      });

      socket.on("close", () => {
        this.clients.delete(client);
      });

      // Start periodic telemetry generation if not running
      this.ensureTelemetryBroadcasting();
    });
  }

  private static broadcastAlert(eventType: string, alert: any) {
    const payload = JSON.stringify({
      event: eventType, // e.g. 'alert_raised', 'alert_escalated'
      timestamp: new Date().toISOString(),
      alert,
    });

    for (const client of this.clients) {
      if (client?.socket && client.socket.readyState === 1) {
        // Only deliver if client is regulator OR matches tenant
        if (!alert.tenant_id || client.tenantId === alert.tenant_id || client.userId?.startsWith("USR-REG")) {
          try {
            client.socket.send(payload);
          } catch {
            // socket closed
          }
        }
      }
    }
  }

  private static ensureTelemetryBroadcasting() {
    if (this.telemetryInterval) return;

    // Periodically broadcast live node readings matching Schema 14.1
    this.telemetryInterval = setInterval(() => {
      if (this.clients.size === 0) return;

      const now = new Date().toISOString();
      const nodes = [
        {
          id: "SS-PANEL7-N042",
          tilt: 0.183 + (Math.random() - 0.5) * 0.006,
          vib: 1.42 + (Math.random() - 0.5) * 0.1,
          disp: 3.70 + (Math.random() - 0.5) * 0.05,
          crack: 0.02,
          anomaly: 0.86,
          battery: 78,
          rssi: -71,
          hops: 3,
          maint: 21,
          isStale: false,
        },
        {
          id: "SS-PANEL7-N043",
          tilt: 0.125 + (Math.random() - 0.5) * 0.004,
          vib: 0.98 + (Math.random() - 0.5) * 0.08,
          disp: 2.45 + (Math.random() - 0.5) * 0.03,
          crack: 0.01,
          anomaly: 0.42,
          battery: 85,
          rssi: -68,
          hops: 2,
          maint: 45,
          isStale: false,
        },
        {
          id: "SS-PANEL7-N044",
          tilt: 0.082 + (Math.random() - 0.5) * 0.003,
          vib: 0.54 + (Math.random() - 0.5) * 0.05,
          disp: 1.80 + (Math.random() - 0.5) * 0.02,
          crack: 0.005,
          anomaly: 0.18,
          battery: 91,
          rssi: -74,
          hops: 1,
          maint: 90,
          isStale: false,
        },
        {
          id: "SS-PANEL7-N045", // Stale sensor demonstrating Zero Silent Staleness
          tilt: 0.052,
          vib: 0.32,
          disp: 1.10,
          crack: 0.0,
          anomaly: 0.15,
          battery: 34,
          rssi: -89,
          hops: 4,
          maint: 8,
          isStale: true, // triggers amber badge!
        },
      ];

      for (const n of nodes) {
        const record: NodeTelemetryRecord = {
          tenant_id: "OPCO-ECL-01",
          site_id: "PANEL7-JHARIA",
          node_id: n.id,
          as_of: n.isStale ? new Date(Date.now() - 140 * 1000).toISOString() : now, // 140s ago for stale node (>90s)
          is_stale: n.isStale,
          readings: {
            tilt_deg: parseFloat(n.tilt.toFixed(4)),
            vibration_rms_mm_s: parseFloat(n.vib.toFixed(3)),
            displacement_mm: parseFloat(n.disp.toFixed(3)),
            crack_index: n.crack,
          },
          anomaly_score: n.anomaly,
          health: {
            battery_pct: n.battery,
            rssi_dbm: n.rssi,
            hop_count: n.hops,
            predicted_maintenance_days: n.maint,
          },
        };

        const payload = JSON.stringify({
          event: "telemetry",
          record,
        });

        for (const client of this.clients) {
          if (
            client?.socket &&
            client.socket.readyState === 1 &&
            client.tenantId === "OPCO-ECL-01" &&
            client.siteId === "PANEL7-JHARIA"
          ) {
            try {
              client.socket.send(payload);
            } catch {
              // socket closed
            }
          }
        }
      }
    }, 2500);
  }

  static stop() {
    if (this.telemetryInterval) {
      clearInterval(this.telemetryInterval);
      this.telemetryInterval = null;
    }
    for (const client of this.clients) {
      client.socket.close();
    }
    this.clients.clear();
  }
}
