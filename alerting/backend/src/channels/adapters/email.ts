import nodemailer, { Transporter } from 'nodemailer';
import { AlertRecord, AlertSeverity, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';

export interface DailyDigestEntry {
  alert_id: string;
  severity: AlertSeverity;
  zone_id: string;
  explanation: string;
  timestamp: Date;
}

export const dailyDigestQueue: DailyDigestEntry[] = [];

let transporter: Transporter | null = null;

export async function getEmailTransporter(): Promise<Transporter> {
  if (!transporter) {
    // In local sandbox / testing without live SMTP credentials, use JSON/stream transport or Ethereal
    if (process.env.SMTP_HOST && process.env.SMTP_USER) {
      transporter = nodemailer.createTransport({
        host: process.env.SMTP_HOST,
        port: Number(process.env.SMTP_PORT || 587),
        auth: {
          user: process.env.SMTP_USER,
          pass: process.env.SMTP_PASS
        }
      });
    } else {
      // Sandbox fallback transport
      transporter = nodemailer.createTransport({
        streamTransport: true,
        newline: 'windows',
        buffer: true
      });
    }
  }
  return transporter;
}

/**
 * Builds multipart HTML brief matching specification:
 * - Time-to-critical badge
 * - Placeholder map snippet (SVG/HTML subsidence zone visualizer)
 * - Sensor attribution list
 * - One-click acknowledgment link back to feedback endpoint
 */
export function generateEmailHtmlBrief(
  alert: AlertRecord,
  context?: DeliveryContext
): string {
  const isRetraction = context?.isRetraction;
  const baseUrl = process.env.API_BASE_URL || 'http://localhost:3000';
  const ackUrl = `${baseUrl}/api/v1/alerts/${alert.alert_id}/feedback?operator_id=00000000-0000-0000-0000-000000000001&verdict=Confirmed`;
  const falsePositiveUrl = `${baseUrl}/api/v1/alerts/${alert.alert_id}/feedback?operator_id=00000000-0000-0000-0000-000000000001&verdict=FalsePositive`;

  const severityColor =
    alert.severity === AlertSeverity.Critical ? '#dc2626' : alert.severity === AlertSeverity.Warning ? '#ea580c' : '#2563eb';

  const sensorRows = (alert.explainability?.contributing_sensor_attribution || [])
    .map(
      (s) =>
        `<tr>
          <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-family: monospace;">${s.node_id}</td>
          <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-transform: capitalize;">${s.modality}</td>
          <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: ${severityColor};">${s.reading}</td>
        </tr>`
    )
    .join('');

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>SubSense Alert Brief</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px;">
  <div style="max-width: 640px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden;">
    
    <!-- Header -->
    <div style="background: ${isRetraction ? '#475569' : severityColor}; padding: 20px 24px;">
      <h2 style="margin: 0; color: #ffffff; font-size: 20px;">
        ${isRetraction ? 'ℹ️ RETRACTION NOTICE: Subsidence Alert Lifted' : `⚠️ SubSense ${alert.severity} Alert Brief`}
      </h2>
      <p style="margin: 4px 0 0 0; color: #f1f5f9; font-size: 14px;">
        Mine Risk Zone: <strong>${alert.risk_zone_id}</strong>
      </p>
    </div>

    <!-- Body -->
    <div style="padding: 24px;">
      
      <!-- TTC & Confidence Badge -->
      <div style="display: flex; gap: 16px; margin-bottom: 20px;">
        <div style="background: #0f172a; padding: 12px 16px; border-radius: 8px; border: 1px solid #334155; flex: 1;">
          <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase;">Time To Critical</div>
          <div style="font-size: 20px; font-weight: bold; color: #f8fafc;">
            ${alert.time_to_critical_hours !== null ? `${alert.time_to_critical_hours} hrs` : 'N/A'}
          </div>
        </div>
        <div style="background: #0f172a; padding: 12px 16px; border-radius: 8px; border: 1px solid #334155; flex: 1;">
          <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase;">Confidence</div>
          <div style="font-size: 20px; font-weight: bold; color: #38bdf8;">
            ${alert.explainability?.composite_confidence || `${(alert.confidence_score * 100).toFixed(1)}%`}
          </div>
        </div>
      </div>

      <!-- Narrative -->
      <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 8px 0; color: #cbd5e1; font-size: 14px;">AI Trigger Narrative</h4>
        <p style="margin: 0; background: #0f172a; padding: 12px; border-radius: 6px; border-left: 4px solid ${severityColor}; font-size: 14px; line-height: 1.5;">
          ${alert.explainability?.trigger_narrative || alert.explanation}
        </p>
      </div>

      <!-- Placeholder Map Snippet -->
      <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 8px 0; color: #cbd5e1; font-size: 14px;">GIS Subsidence Contour (Zone Map)</h4>
        <div style="background: #0f172a; border-radius: 8px; border: 1px dashed #475569; padding: 20px; text-align: center;">
          <svg width="100%" height="90" viewBox="0 0 300 90" style="max-width: 300px; margin: 0 auto; display: block;">
            <circle cx="150" cy="45" r="40" fill="none" stroke="${severityColor}" stroke-width="2" stroke-dasharray="4,4" />
            <circle cx="150" cy="45" r="22" fill="${severityColor}" fill-opacity="0.25" stroke="${severityColor}" stroke-width="1.5" />
            <circle cx="150" cy="45" r="6" fill="${severityColor}" />
            <text x="150" y="84" font-size="10" fill="#94a3b8" text-anchor="middle">Zone Geofence Center (Lat 23.79°, Lon 86.43°)</text>
          </svg>
        </div>
      </div>

      <!-- Contributing Sensors -->
      <div style="margin-bottom: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #cbd5e1; font-size: 14px;">Contributing Sensor Attribution</h4>
        <table style="width: 100%; border-collapse: collapse; background: #0f172a; border-radius: 6px; overflow: hidden; font-size: 13px;">
          <thead>
            <tr style="background: #1e293b; color: #94a3b8; text-align: left;">
              <th style="padding: 8px;">Node</th>
              <th style="padding: 8px;">Modality</th>
              <th style="padding: 8px;">Reading</th>
            </tr>
          </thead>
          <tbody>
            ${sensorRows || '<tr><td colspan="3" style="padding: 8px; color: #64748b;">No individual sensor telemetry attached</td></tr>'}
          </tbody>
        </table>
      </div>

      <!-- One-Click Feedback Actions -->
      <div>
        <h4 style="margin: 0 0 12px 0; color: #cbd5e1; font-size: 14px;">One-Click Operator Acknowledgment</h4>
        <div style="display: flex; gap: 12px;">
          <a href="${ackUrl}" style="background: #16a34a; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 13px; display: inline-block;">
            ✅ Confirm Subsidence Hazard
          </a>
          <a href="${falsePositiveUrl}" style="background: #475569; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 13px; display: inline-block;">
            ❌ Report False Alarm
          </a>
        </div>
      </div>

    </div>
  </div>
</body>
</html>
  `.trim();
}

export class EmailAdapter implements ChannelAdapter {
  channel = DeliveryChannel.Email;

  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    if (process.env.SIMULATE_GATEWAY_OUTAGE === 'true') {
      throw new Error('Network Unreachable: SMTP Relay Host Unreachable');
    }

    // Advisory tier: Queue into daily digest instead of immediate sending
    if (alert.severity === AlertSeverity.Advisory && !context?.isRetraction) {
      dailyDigestQueue.push({
        alert_id: alert.alert_id,
        severity: alert.severity,
        zone_id: alert.risk_zone_id,
        explanation: alert.explanation,
        timestamp: new Date()
      });

      console.log(
        `[EMAIL ADAPTER] Advisory alert ${alert.alert_id} queued into Daily Digest batch (Queue size: ${dailyDigestQueue.length})`
      );

      return {
        status: DeliveryStatus.Queued,
        external_ref: `digest-queue-${alert.alert_id.substring(0, 8)}`,
        meta: { mode: 'DAILY_DIGEST_BATCHED', queueSize: dailyDigestQueue.length }
      };
    }

    // Warning and Critical (or retractions): Direct, immediate delivery
    const htmlContent = generateEmailHtmlBrief(alert, context);
    const transporter = await getEmailTransporter();

    try {
      const info = await transporter.sendMail({
        from: '"SubSense Mine Safety System" <alerts@subsense.org>',
        to: recipient,
        subject: context?.isRetraction
          ? `[RETRACTED] SubSense Hazard Notice: Zone ${alert.risk_zone_id.substring(0, 8)}`
          : `[${alert.severity.toUpperCase()} ALERT] Coal Mine Subsidence Warning: Zone ${alert.risk_zone_id.substring(0, 8)}`,
        html: htmlContent
      });

      console.log(
        `[EMAIL ADAPTER] Direct multipart brief dispatched to ${recipient} (MessageID: ${info.messageId || 'local-stream'})`
      );

      return {
        status: DeliveryStatus.Delivered,
        delivered_at: new Date(),
        external_ref: info.messageId || `mail-${alert.alert_id.substring(0, 8)}`
      };
    } catch (err: any) {
      console.error(`[EMAIL ADAPTER] Failed to send email to ${recipient}:`, err.message);
      return {
        status: DeliveryStatus.Failed,
        error: err.message
      };
    }
  }
}

export const emailAdapter = new EmailAdapter();
