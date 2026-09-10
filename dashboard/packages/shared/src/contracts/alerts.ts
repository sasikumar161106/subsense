import { z } from "zod";

export const AlertSeveritySchema = z.enum(["info", "warning", "critical"]);
export const AlertStateSchema = z.enum([
  "new",
  "acknowledged",
  "escalated",
  "resolved",
  "false_alarm",
]);

export const FalseAlarmReasonSchema = z.enum([
  "surface_blasting",
  "heavy_vehicle_impact",
  "thermal_expansion_anomaly",
  "sensor_hardware_glitch",
  "telecom_packet_jitter",
  "unrelated_seismic_activity",
  "other_operational_noise",
]);

// Contract 14.2: Alert lifecycle event (REST response / push notification)
export const AlertLifecycleEventSchema = z.object({
  alert_id: z.string().min(1).describe("Unique alert event identifier (e.g. ALERT-PANEL7-20260909-0412)"),
  tenant_id: z.string().min(1).describe("Operating company tenant identifier (e.g. OPCO-ECL-01)"),
  site_id: z.string().min(1).describe("Mine site/panel identifier (e.g. PANEL7-JHARIA)"),
  zone_id: z.string().min(1).describe("Mine zone or sector (e.g. PANEL7-ZONE-C)"),
  severity: AlertSeveritySchema,
  state: AlertStateSchema,
  raised_at: z.string().datetime().describe("ISO 8601 UTC timestamp when alert was triggered"),
  acknowledged_by: z.string().nullable().describe("User ID of operator who acknowledged the alert"),
  acknowledged_at: z.string().datetime().nullable().describe("ISO 8601 UTC timestamp of acknowledgement"),
  time_to_critical_hours: z.tuple([z.number(), z.number()]).describe("Estimated [min, max] hours before critical subsidence threshold breach"),
  confidence_score: z.number().min(0).max(1).describe("Layer 4 AI confidence level (0 to 1)"),
  contributing_sensors: z.array(z.string()).describe("List of sensor parameters triggering alert"),
  explanation_summary: z.string().describe("Human-readable analytical rationale from Layer 4"),
  
  // Lifecycle metadata
  escalated_at: z.string().datetime().nullable().optional(),
  resolved_at: z.string().datetime().nullable().optional(),
  resolved_by: z.string().nullable().optional(),
  false_alarm_reason: FalseAlarmReasonSchema.nullable().optional(),
  false_alarm_notes: z.string().nullable().optional(),
});

export const AlertAcknowledgePayloadSchema = z.object({
  user_id: z.string().min(1),
  user_role: z.string().min(1),
  comment: z.string().optional(),
});

export const FalseAlarmSubmissionSchema = z.object({
  user_id: z.string().min(1),
  reason: FalseAlarmReasonSchema,
  notes: z.string().min(3),
  feature_vector_snapshot: z.record(z.any()).optional(),
});

export type AlertSeverity = z.infer<typeof AlertSeveritySchema>;
export type AlertState = z.infer<typeof AlertStateSchema>;
export type FalseAlarmReason = z.infer<typeof FalseAlarmReasonSchema>;
export type AlertLifecycleEvent = z.infer<typeof AlertLifecycleEventSchema>;
export type AlertAcknowledgePayload = z.infer<typeof AlertAcknowledgePayloadSchema>;
export type FalseAlarmSubmission = z.infer<typeof FalseAlarmSubmissionSchema>;
