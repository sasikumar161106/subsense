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

export interface AlertDeliveryRecord {
  delivery_id: string;
  alert_id: string;
  channel: DeliveryChannel;
  recipient_ref: string;
  delivery_status: DeliveryStatus;
  attempted_at: string;
  delivered_at?: string | null;
  retraction_notice?: boolean;
}

export interface AlertFeedbackRecord {
  feedback_id: string;
  alert_id: string;
  operator_id: string;
  verdict: FeedbackVerdict;
  notes?: string | null;
  feedback_hash?: string;
  submitted_at: string;
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
  explainability?: ExplainabilityPayload;
  created_at: string;
  updated_at: string;
  deliveries?: AlertDeliveryRecord[];
  feedbacks?: AlertFeedbackRecord[];
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

export enum UserRole {
  MineSafetyOfficer = 'MineSafetyOfficer',
  RegulatorDGMS = 'RegulatorDGMS'
}

export interface UserContext {
  user_id: string;
  username: string;
  role: UserRole;
  tenant_id: string | null;
  tenant_name: string;
}

export interface EdgeSirenEvent {
  type: 'SIREN_ACTIVATION';
  alert_id: string;
  zone_id: string;
  severity: AlertSeverity;
  source: 'EdgeAutonomousGPIO';
  timestamp: string;
}
