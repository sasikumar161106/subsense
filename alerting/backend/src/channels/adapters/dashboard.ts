import { WebSocket, WebSocketServer } from 'ws';
import { Server as HttpServer } from 'http';
import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';

class DashboardWebSocketManager {
  private wss: WebSocketServer | null = null;
  private connectedClients: Set<WebSocket> = new Set();

  public init(server: HttpServer): void {
    if (this.wss) return;

    this.wss = new WebSocketServer({ server, path: '/ws/alerts' });

    this.wss.on('connection', (ws: WebSocket) => {
      this.connectedClients.add(ws);
      console.log(`[WEBSOCKET] Dashboard client connected. Total clients: ${this.connectedClients.size}`);

      // Send initial handshake
      ws.send(
        JSON.stringify({
          type: 'CONNECTED',
          timestamp: new Date().toISOString(),
          message: 'SubSense Real-Time Alert Stream Active'
        })
      );

      ws.on('close', () => {
        this.connectedClients.delete(ws);
        console.log(`[WEBSOCKET] Client disconnected. Remaining: ${this.connectedClients.size}`);
      });
    });
  }

  public broadcast(type: string, payload: any): void {
    const message = JSON.stringify({ type, payload, timestamp: new Date().toISOString() });
    for (const client of this.connectedClients) {
      if (client.readyState === WebSocket.OPEN) {
        try {
          client.send(message);
        } catch (err) {
          console.error('[WEBSOCKET BROADCAST ERROR]', err);
        }
      }
    }
  }

  public getClientCount(): number {
    return this.connectedClients.size;
  }
}

export const wsManager = new DashboardWebSocketManager();

export class DashboardBannerAdapter implements ChannelAdapter {
  channel = DeliveryChannel.DashboardBanner;

  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    const isRetraction = context?.isRetraction;

    wsManager.broadcast(isRetraction ? 'ALERT_RETRACTED' : 'ALERT_BANNER', {
      alert_id: alert.alert_id,
      severity: alert.severity,
      status: alert.status,
      zone_id: alert.risk_zone_id,
      explanation: alert.explanation,
      confidence: alert.confidence_score,
      time_to_critical_hours: alert.time_to_critical_hours,
      explainability: alert.explainability,
      recipient,
      isRetraction,
      reason: context?.retractionReason
    });

    console.log(
      `[DASHBOARD BANNER] Broadcasted ${isRetraction ? 'RETRACTION' : alert.severity} banner to UI clients (Recipient: ${recipient})`
    );

    return {
      status: DeliveryStatus.Delivered,
      delivered_at: new Date(),
      external_ref: `ws-broadcast-${alert.alert_id.substring(0, 8)}`
    };
  }
}

export const dashboardBannerAdapter = new DashboardBannerAdapter();
