import { FastifyPluginAsync } from "fastify";
import { withTenantScope } from "../db/client";

export interface TrendDataPoint {
  timestamp: string;
  tilt_deg: number;
  displacement_mm: number;
  vibration_rms: number;
  crack_index: number;
  is_downsampled: boolean;
}

export interface ForecastDataPoint {
  timestamp: string;
  p10: number; // 10th percentile (lower bound)
  p50: number; // 50th percentile (median prediction)
  p90: number; // 90th percentile (upper bound / critical risk envelope)
}

export interface GeotechnicalEventMarker {
  id: string;
  type: "blast" | "rainfall" | "false_alarm";
  timestamp: string;
  title: string;
  description: string;
  value: number; // e.g. explosive charge kg, rainfall mm/hr
}

export const trendsRoutes: FastifyPluginAsync = async (fastify) => {
  fastify.get<{
    Querystring: {
      site_id?: string;
      node_id?: string;
      range?: "1h" | "24h" | "7d" | "30d";
    };
  }>("/api/v1/geotech/trends", async (request, reply) => {
    const session = (request as any).userSession;
    const range = request.query.range || "24h";
    const siteId = request.query.site_id || "PANEL7-JHARIA";
    const nodeId = request.query.node_id || "SS-PANEL7-N042";

    // Generate downsampled historical timeline leading up to now
    const now = Date.now();
    const historyPoints: TrendDataPoint[] = [];
    const count = range === "1h" ? 60 : range === "24h" ? 48 : range === "7d" ? 56 : 60;
    const intervalMs =
      range === "1h"
        ? 60 * 1000
        : range === "24h"
        ? 30 * 60 * 1000
        : range === "7d"
        ? 3 * 3600 * 1000
        : 12 * 3600 * 1000;

    let baseTilt = 0.12;
    let baseDisplacement = 2.4;

    for (let i = count; i >= 0; i--) {
      const ts = new Date(now - i * intervalMs).toISOString();
      // Slight upward creep with natural fluctuation
      const noise = (Math.sin(i * 0.4) + Math.cos(i * 0.7)) * 0.015;
      baseTilt += 0.001;
      baseDisplacement += 0.02;

      historyPoints.push({
        timestamp: ts,
        tilt_deg: parseFloat((baseTilt + noise).toFixed(4)),
        displacement_mm: parseFloat((baseDisplacement + noise * 5).toFixed(3)),
        vibration_rms: parseFloat((0.8 + Math.sin(i * 0.5) * 0.4).toFixed(3)),
        crack_index: parseFloat(Math.min(0.08, 0.01 + (count - i) * 0.001).toFixed(4)),
        is_downsampled: range !== "1h",
      });
    }

    // Mocked LSTM forecast forward trajectory (next 12 hours) with 10th / 50th / 90th uncertainty cones
    const forecastPoints: ForecastDataPoint[] = [];
    const lastDisplacement = historyPoints[historyPoints.length - 1].displacement_mm;
    const forecastIntervalMs = 30 * 60 * 1000; // 30 min steps

    for (let j = 1; j <= 24; j++) {
      const ts = new Date(now + j * forecastIntervalMs).toISOString();
      const spread = j * 0.08; // uncertainty widens into the future
      const medianIncrease = j * 0.06;

      const p50 = parseFloat((lastDisplacement + medianIncrease).toFixed(3));
      const p10 = parseFloat((p50 - spread).toFixed(3));
      const p90 = parseFloat((p50 + spread * 1.5).toFixed(3));

      forecastPoints.push({
        timestamp: ts,
        p10,
        p50,
        p90,
      });
    }

    // Interactive event markers
    const eventMarkers: GeotechnicalEventMarker[] = [
      {
        id: "EVT-BLAST-01",
        type: "blast",
        timestamp: new Date(now - 14 * 3600 * 1000).toISOString(),
        title: "Controlled Face Blast (Seam 7)",
        description: "280 kg ANFO delayed detonator charge in West drift. Induced transient vibration.",
        value: 280,
      },
      {
        id: "EVT-RAIN-01",
        type: "rainfall",
        timestamp: new Date(now - 8 * 3600 * 1000).toISOString(),
        title: "Heavy Infiltration Event",
        description: "Intense precipitation (48 mm/hr) saturated overburden sandstone layer.",
        value: 48,
      },
      {
        id: "EVT-FALSE-01",
        type: "false_alarm",
        timestamp: new Date(now - 3 * 3600 * 1000).toISOString(),
        title: "Heavy Haulage Truck Impact",
        description: "60-ton dumper vibration surge flagged and filtered by operator.",
        value: 60,
      },
    ];

    return {
      site_id: siteId,
      node_id: nodeId,
      range,
      downsample_window: range === "1h" ? "1_minute" : range === "24h" ? "30_minutes" : "3_hours",
      history: historyPoints,
      forecast_lstm: {
        model: "BiLSTM-Subsidence-Predictor-v2.1",
        confidence_interval: "90%",
        points: forecastPoints,
      },
      event_markers: eventMarkers,
    };
  });
};
