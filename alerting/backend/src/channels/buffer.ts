import { AlertDeliveryRecord } from '../models/types';

export interface BufferedDeliveryItem {
  delivery: AlertDeliveryRecord;
  original_alert_created_at: Date;
  buffered_at: Date;
  attempts: number;
}

class BacklogBuffer {
  private buffer: BufferedDeliveryItem[] = [];

  public bufferDelivery(
    delivery: AlertDeliveryRecord,
    originalAlertCreatedAt: Date
  ): void {
    const item: BufferedDeliveryItem = {
      delivery,
      original_alert_created_at: originalAlertCreatedAt,
      buffered_at: new Date(),
      attempts: 0
    };
    this.buffer.push(item);
    console.warn(
      `[BACKLOG BUFFER] Buffered delivery ${delivery.delivery_id} for channel ${delivery.channel}. Original alert created_at: ${originalAlertCreatedAt.toISOString()} preserved.`
    );
  }

  public getBufferedDeliveries(): BufferedDeliveryItem[] {
    return [...this.buffer];
  }

  public size(): number {
    return this.buffer.length;
  }

  public clear(): void {
    this.buffer = [];
  }

  /**
   * Flushes pending buffered items once connectivity is restored.
   * Guarantees the original alert created_at is preserved in the delivery metadata.
   */
  public async flush(
    flushHandler: (item: BufferedDeliveryItem) => Promise<boolean>
  ): Promise<number> {
    if (this.buffer.length === 0) return 0;

    console.log(`[BACKLOG BUFFER] Flushing ${this.buffer.length} buffered deliveries...`);
    const remaining: BufferedDeliveryItem[] = [];
    let flushedCount = 0;

    for (const item of this.buffer) {
      try {
        const success = await flushHandler(item);
        if (success) {
          flushedCount++;
        } else {
          item.attempts++;
          remaining.push(item);
        }
      } catch {
        item.attempts++;
        remaining.push(item);
      }
    }

    this.buffer = remaining;
    console.log(
      `[BACKLOG BUFFER] Flush complete: ${flushedCount} flushed, ${remaining.length} remain buffered.`
    );
    return flushedCount;
  }
}

export const backlogBuffer = new BacklogBuffer();
