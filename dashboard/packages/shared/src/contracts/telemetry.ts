import { z } from "zod";

export const NodeReadingsSchema = z.object({
  tilt_deg: z.number().describe("Tilt angle measured in degrees"),
  vibration_rms_mm_s: z.number().describe("Vibration root mean square in mm/s"),
  displacement_mm: z.number().nullable().describe("Extensometer subsidence displacement in mm"),
  crack_index: z.number().min(0).max(1).nullable().describe("Normalized crack propagation index (0 to 1)"),
});

export const NodeHealthSchema = z.object({
  battery_pct: z.number().min(0).max(100).describe("Battery percentage (0-100)"),
  rssi_dbm: z.number().describe("Received signal strength indicator in dBm"),
  hop_count: z.number().int().nonnegative().describe("Radio mesh hop count to gateway"),
  predicted_maintenance_days: z.number().nonnegative().describe("Days until recommended maintenance/discharge"),
});

// Contract 14.1: Real-time node telemetry & health record (WebSocket broadcast)
export const NodeTelemetryRecordSchema = z.object({
  tenant_id: z.string().min(1).describe("Operating company tenant identifier (e.g. OPCO-ECL-01)"),
  site_id: z.string().min(1).describe("Mine site/panel identifier (e.g. PANEL7-JHARIA)"),
  node_id: z.string().min(1).describe("Sensor mesh node identifier (e.g. SS-PANEL7-N042)"),
  as_of: z.string().datetime().describe("ISO 8601 UTC timestamp of sample"),
  is_stale: z.boolean().describe("Staleness flag indicating if packet exceeds heartbeat threshold"),
  readings: NodeReadingsSchema,
  anomaly_score: z.number().min(0).max(1).describe("Layer 4 AI anomaly confidence score (0 to 1)"),
  health: NodeHealthSchema,
});

export type NodeReadings = z.infer<typeof NodeReadingsSchema>;
export type NodeHealth = z.infer<typeof NodeHealthSchema>;
export type NodeTelemetryRecord = z.infer<typeof NodeTelemetryRecordSchema>;
