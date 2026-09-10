import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';

export interface AdapterDeliveryResult {
  status: DeliveryStatus;
  delivered_at?: Date | null;
  external_ref?: string;
  error?: string | null;
  duration_ms?: number;
  meta?: Record<string, any>;
}

export interface DeliveryContext {
  isRetraction?: boolean;
  retractionReason?: string;
  zoneName?: string;
  communityLanguage?: string;
}

export interface ChannelAdapter {
  channel: DeliveryChannel;
  send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult>;
}
