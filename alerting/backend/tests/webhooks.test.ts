import request from 'supertest';
import { app } from '../src/api/app';
import { repository } from '../src/db/repository';
import { DeliveryChannel, DeliveryStatus } from '../src/models/types';

describe('Inbound Webhooks API', () => {
  beforeEach(() => {
    repository.resetMemoryStore();
  });

  test('POST /webhooks/sms-gateway/status should update delivery status to Delivered', async () => {
    const deliveryRecord = {
      delivery_id: 'sms-delivery-123',
      alert_id: 'alert-1',
      channel: DeliveryChannel.SMS,
      recipient_ref: '+919876543210',
      delivery_status: DeliveryStatus.Sent,
      attempted_at: new Date(),
      delivered_at: null
    };
    await repository.saveDeliveries([deliveryRecord]);

    const deliveredAt = new Date().toISOString();
    const res = await request(app)
      .post('/webhooks/sms-gateway/status')
      .send({
        delivery_id: 'sms-delivery-123',
        status: 'Delivered',
        delivered_at: deliveredAt
      });

    expect(res.status).toBe(200);
    expect(res.body.delivery.delivery_status).toBe(DeliveryStatus.Delivered);

    const check = await repository.findDeliveryById('sms-delivery-123');
    expect(check?.delivery_status).toBe(DeliveryStatus.Delivered);
  });

  test('POST /webhooks/voice-gateway/status should update delivery status and duration', async () => {
    const deliveryRecord = {
      delivery_id: 'voice-delivery-456',
      alert_id: 'alert-1',
      channel: DeliveryChannel.VoiceIVR,
      recipient_ref: '+919876543210',
      delivery_status: DeliveryStatus.Sent,
      attempted_at: new Date(),
      delivered_at: null
    };
    await repository.saveDeliveries([deliveryRecord]);

    const res = await request(app)
      .post('/webhooks/voice-gateway/status')
      .send({
        delivery_id: 'voice-delivery-456',
        status: 'completed',
        duration_seconds: 32,
        dtmf_response: '1',
        delivered_at: new Date().toISOString()
      });

    expect(res.status).toBe(200);
    expect(res.body.delivery.delivery_status).toBe(DeliveryStatus.Delivered);

    const check = await repository.findDeliveryById('voice-delivery-456');
    expect(check?.delivery_status).toBe(DeliveryStatus.Delivered);
  });

  test('POST /webhooks/sms-gateway/status should return 404 for unknown delivery_id', async () => {
    const res = await request(app)
      .post('/webhooks/sms-gateway/status')
      .send({
        delivery_id: 'non-existent-del',
        status: 'Delivered'
      });

    expect(res.status).toBe(404);
  });
});
