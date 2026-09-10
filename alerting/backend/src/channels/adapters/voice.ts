import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';

export interface VoiceCallLog {
  call_sid: string;
  recipient: string;
  duration_seconds: number;
  dtmf_input: string;
  status: string;
  timestamp: Date;
}

export const voiceCallHistory: VoiceCallLog[] = [];

export class VoiceIvrAdapter implements ChannelAdapter {
  channel = DeliveryChannel.VoiceIVR;

  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    if (process.env.SIMULATE_GATEWAY_OUTAGE === 'true') {
      throw new Error('Network Unreachable: Telco Voice SIP Trunk Down');
    }
    const callSid = `CA${Date.now().toString(16).toUpperCase()}${Math.floor(Math.random() * 1000)}`;
    const simulatedDuration = 28; // seconds
    const simulatedDtmf = '1'; // '1' acknowledges automated evacuation notice

    const log: VoiceCallLog = {
      call_sid: callSid,
      recipient,
      duration_seconds: simulatedDuration,
      dtmf_input: simulatedDtmf,
      status: 'completed',
      timestamp: new Date()
    };
    voiceCallHistory.push(log);

    console.log(
      `[VOICE IVR ADAPTER] Call placed to ${recipient}. SID: ${callSid} | Duration: ${simulatedDuration}s | DTMF: '${simulatedDtmf}' (Acknowledged)`
    );

    return {
      status: DeliveryStatus.Delivered,
      delivered_at: new Date(),
      external_ref: callSid,
      duration_ms: simulatedDuration * 1000,
      meta: {
        call_sid: callSid,
        duration_seconds: simulatedDuration,
        dtmf_response: simulatedDtmf,
        ivr_flow: 'CRITICAL_EVACUATION_PROMPT'
      }
    };
  }
}

export const voiceIvrAdapter = new VoiceIvrAdapter();
