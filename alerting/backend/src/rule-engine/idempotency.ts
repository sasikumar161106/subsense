import * as crypto from 'crypto';

export const DEFAULT_IDEMPOTENCY_WINDOW_SECS = 300; // 5 minutes

/**
 * Pure function: Generates an idempotency key from risk_zone_id and event_window_epoch.
 * key = hash(risk_zone_id + event_window_epoch)
 */
export function generate_idempotency_key(
  risk_zone_id: string,
  event_time: Date | number | string = Date.now(),
  window_size_secs: number = DEFAULT_IDEMPOTENCY_WINDOW_SECS
): string {
  const timestampMs = typeof event_time === 'number' ? event_time : new Date(event_time).getTime();
  const epochSecs = Math.floor(timestampMs / 1000);
  const event_window_epoch = Math.floor(epochSecs / window_size_secs);

  const raw = `${risk_zone_id}_${event_window_epoch}`;
  return crypto.createHash('sha256').update(raw).digest('hex');
}
