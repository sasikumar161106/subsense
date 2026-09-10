import { AlertRecord, DeliveryChannel, DeliveryStatus } from '../../models/types';
import { KNOWN_ZONE_NAMES } from '../../rule-engine/explainability';
import { AdapterDeliveryResult, ChannelAdapter, DeliveryContext } from './base';

export interface CommunityLanguageTemplate {
  alert: string;
  retraction: string;
}

export const COMMUNITY_TEMPLATES: Record<string, CommunityLanguageTemplate> = {
  hi: {
    alert: 'चेतावनी: {zone_name} क्षेत्र में ज़मीन धंसने का गंभीर ख़तरा है। कृपया तुरंत सुरक्षित स्थान पर जाएँ। निर्देश: {instruction}',
    retraction: 'सूचना: {zone_name} क्षेत्र में भू-धंसान की चेतावनी वापस ले ली गई है। क्षेत्र सुरक्षित है।'
  },
  bn: {
    alert: 'সতর্কতা: {zone_name} অঞ্চলে ভূমিধসের জরুরি ঝুঁকি রয়েছে। অবিলম্বে নিরাপদ স্থানে সরে যান। নির্দেশ: {instruction}',
    retraction: 'বিজ্ঞপ্তি: {zone_name} অঞ্চলের জন্য ভূমিধসের সতর্কতা প্রত্যাহার করা হয়েছে। এলাকাটি নিরাপদ।'
  },
  sat: {
    alert: 'Hoñdar: {zone_name} jaiga re hasa dhasao botor menak-a. Tayom te dharwak jagah te calak-pe. Hukuma: {instruction}',
    retraction: 'Badhay: {zone_name} jaiga re hasa dhasao botor bond akana. Jaiga bhalik menak-a.'
  },
  or: {
    alert: 'ସତର୍କତା: {zone_name} ଅଞ୍ଚଳରେ ଭୂ-ଅବପାତର ଆଶଙ୍କା ରହିଛି। ଦୟାକରି ତୁରନ୍ତ ସୁରକ୍ଷିତ ସ୍ଥାନକୁ ଯାଆନ୍ତୁ। ନିର୍ଦ୍ଦେଶ: {instruction}',
    retraction: 'ସୂଚନା: {zone_name} ଅଞ୍ଚଳ ପାଇଁ ସତର୍କତା ପ୍ରତ୍ୟାହାର କରାଯାଇଛି। ପରିସ୍ଥିତି ସ୍ଵାଭାବିକ ଅଛି।'
  },
  en: {
    alert: 'CRITICAL SAFETY ALERT: Active ground subsidence hazard detected in {zone_name}. Evacuate immediately to designated muster point. Instructions: {instruction}',
    retraction: 'NOTICE: Ground subsidence safety alert for {zone_name} has been RETRACTED. The area is confirmed safe.'
  }
};

export class CommunitySmsAdapter implements ChannelAdapter {
  channel = DeliveryChannel.CommunitySMS;

  async send(
    alert: AlertRecord,
    recipient: string,
    context?: DeliveryContext
  ): Promise<AdapterDeliveryResult> {
    if (process.env.SIMULATE_GATEWAY_OUTAGE === 'true') {
      throw new Error('Network Unreachable: Local BTS Cell Broadcast Offline');
    }
    const lang = context?.communityLanguage || 'en';
    const templateGroup = COMMUNITY_TEMPLATES[lang] || COMMUNITY_TEMPLATES.en;
    const isRetraction = context?.isRetraction;

    const rawTemplate = isRetraction ? templateGroup.retraction : templateGroup.alert;
    const zoneName =
      context?.zoneName ||
      KNOWN_ZONE_NAMES[alert.risk_zone_id] ||
      `Zone ${alert.risk_zone_id.substring(0, 8)}`;

    const evacuationInstruction =
      alert.time_to_critical_hours !== null && alert.time_to_critical_hours < 6
        ? 'Immediate evacuation within 30 minutes to Open Field Sector 4.'
        : 'Prepare for potential evacuation and avoid low-lying roadways.';

    const messageText = rawTemplate
      .replace('{zone_name}', zoneName)
      .replace('{instruction}', evacuationInstruction);

    console.log(
      `[COMMUNITY SMS (${lang.toUpperCase()})] Dispatched to resident ${recipient}: "${messageText.substring(0, 80)}..."`
    );

    return {
      status: DeliveryStatus.Sent,
      delivered_at: new Date(),
      external_ref: `comm-sms-${recipient.replace(/[^0-9]/g, '')}-${Date.now()}`,
      meta: {
        language: lang,
        zone_name: zoneName,
        interpolated_message: messageText
      }
    };
  }
}

export const communitySmsAdapter = new CommunitySmsAdapter();
