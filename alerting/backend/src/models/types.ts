export enum AlertSeverity {
  Advisory = 'Advisory',
  Warning = 'Warning',
  Critical = 'Critical'
}

export enum AlertStatus {
  Active = 'Active',
  Escalated = 'Escalated',
  De_escalated = 'De-escalated',
  Resolved = 'Resolved',
  Retracted = 'Retracted'
}

export enum AlertSource {
  Edge = 'Edge',
  Cloud = 'Cloud'
}

export enum DeliveryChannel {
  Siren = 'Siren',
  SMS = 'SMS',
  Email = 'Email',
  PushNotification = 'PushNotification',
  DashboardBanner = 'DashboardBanner',
  VoiceIVR = 'VoiceIVR',
  CommunitySMS = 'CommunitySMS'
}

export enum DeliveryStatus {
  Queued = 'Queued',
  Sent = 'Sent',
  Delivered = 'Delivered',
  Failed = 'Failed',
  Retrying = 'Retrying'
}

export enum FeedbackVerdict {
  Confirmed = 'Confirmed',
  FalsePositive = 'FalsePositive',
  Unclear = 'Unclear',
  HardwareDefect = 'HardwareDefect'
}

export type AuditTransition = 'created' | 'merged' | 'escalated' | 'de-escalated' | 'retracted' | 'resolved';

export interface SensorAttribution {
  node_id: string;
  modality: string;
  reading: string;
}

export interface ExplainabilityPayload {
  composite_confidence: string;
  contributing_sensor_attribution: SensorAttribution[];
  trigger_narrative: string;
  time_to_critical_hours: number | null;
  displacement_velocity_mm_h?: number;
}

export interface RiskEvent {
  tenant_id: string;
  risk_zone_id: string;
  anomaly_score: number;
  correlation_strength: number;
  progression_rate?: number;
  velocity_delta?: number;
  time_to_critical?: number | null;
  time_to_critical_hours?: number | null;
  confidence: number;
  explanation: string;
  contributing_nodes: string[];
  contributing_sensors?: string[];
  sensor_readings?: Record<string, { modality: string; reading: string }>;
  zone_name?: string;
  source: AlertSource;
  timestamp?: string | Date;
}

export interface AlertRecord {
  alert_id: string;
  tenant_id: string;
  risk_zone_id: string;
  severity: AlertSeverity;
  status: AlertStatus;
  confidence_score: number;
  time_to_critical_hours: number | null;
  explanation: string;
  contributing_nodes: string[];
  contributing_sensors: string[];
  source: AlertSource;
  idempotency_key?: string | null;
  explainability?: ExplainabilityPayload;
  created_at: Date;
  updated_at: Date;
  deliveries?: AlertDeliveryRecord[];
  feedbacks?: AlertFeedbackRecord[];
}

export interface AlertDeliveryRecord {
  delivery_id: string;
  alert_id: string;
  channel: DeliveryChannel;
  recipient_ref: string;
  delivery_status: DeliveryStatus;
  attempted_at: Date;
  delivered_at?: Date | null;
  retraction_notice?: boolean;
  error?: string | null;
}

export interface AlertFeedbackRecord {
  feedback_id: string;
  alert_id: string;
  operator_id: string;
  verdict: FeedbackVerdict;
  notes?: string | null;
  feedback_hash?: string;
  submitted_at: Date;
}

export interface CommunityRegistrantRecord {
  registrant_id: string;
  tenant_id: string;
  risk_zone_id: string;
  phone_number: string;
  preferred_language: string; // ISO 639-1: hi/bn/sat/or/en
  opted_in: boolean;
}

export interface AuditLogRecord {
  log_id: string;
  alert_id: string;
  transition: AuditTransition;
  timestamp: Date;
  snapshot: Record<string, any>;
  metadata?: Record<string, any> | null;
}

/**
 * Phase 2 Severity to Channel Matrix (exact):
 * - Advisory: DashboardBanner, Email (daily digest, batched)
 * - Warning: SMS (high-priority), PushNotification, DashboardBanner (audio-visual), Email (direct, immediate)
 * - Critical: Siren (edge, autonomous), SMS (broadcast), VoiceIVR, DashboardBanner (persistent), CommunitySMS (geofenced)
 */
export const SEVERITY_CHANNEL_MATRIX: Record<AlertSeverity, DeliveryChannel[]> = {
  [AlertSeverity.Advisory]: [
    DeliveryChannel.DashboardBanner,
    DeliveryChannel.Email
  ],
  [AlertSeverity.Warning]: [
    DeliveryChannel.SMS,
    DeliveryChannel.PushNotification,
    DeliveryChannel.DashboardBanner,
    DeliveryChannel.Email
  ],
  [AlertSeverity.Critical]: [
    DeliveryChannel.Siren,
    DeliveryChannel.SMS,
    DeliveryChannel.VoiceIVR,
    DeliveryChannel.DashboardBanner,
    DeliveryChannel.CommunitySMS
  ]
};

// --- Phase 3: Auth, RBAC & Multi-Tenancy Types ---

export enum UserRole {
  MineSafetyOfficer = 'MineSafetyOfficer',
  RegulatorDGMS = 'RegulatorDGMS'
}

export interface UserRecord {
  user_id: string;
  username: string;
  password_hash: string;
  role: UserRole;
  tenant_id: string | null;
  tenant_name: string;
}

export interface RiskZoneMetadata {
  zone_id: string;
  tenant_id: string;
  zone_name: string;
  latitude: number;
  longitude: number;
  strata_profile: string;
  seam_depth_m: number;
}

export interface TenantRecord {
  tenant_id: string;
  tenant_name: string;
  coalfield_region: string;
  zones: RiskZoneMetadata[];
}

export interface AuthTokenPayload {
  user_id: string;
  username: string;
  role: UserRole;
  tenant_id: string | null;
}
