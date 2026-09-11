import { NodeTelemetryRecord, AlertLifecycleEvent } from "@subsense/shared";

type TelemetryListener = (record: NodeTelemetryRecord) => void;
type AlertListener = (alert: AlertLifecycleEvent, eventType: string) => void;

let audioCtx: AudioContext | null = null;
let sirenInterval: any = null;
let sirenOsc: OscillatorNode | null = null;
let sirenGain: GainNode | null = null;

export function startContinuousSiren() {
  try {
    if (!audioCtx) {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtxClass) {
        audioCtx = new AudioCtxClass();
      }
    }
    if (!audioCtx) return;
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }

    if (sirenInterval) return; // already active

    let toggle = false;
    const playPulse = () => {
      if (!audioCtx) return;
      const now = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(toggle ? 960 : 770, now);
      toggle = !toggle;

      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.38);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start(now);
      osc.stop(now + 0.4);
    };

    playPulse();
    sirenInterval = setInterval(playPulse, 420);
  } catch (e) {
    console.error("Audio error:", e);
  }
}

export function stopContinuousSiren() {
  if (sirenInterval) {
    clearInterval(sirenInterval);
    sirenInterval = null;
  }
}

export function playAudibleAlertChime(severity: "warning" | "critical") {
  try {
    if (!audioCtx) {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtxClass) {
        audioCtx = new AudioCtxClass();
      }
    }

    if (!audioCtx) return;
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }

    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = severity === "critical" ? "sawtooth" : "triangle";
    osc.frequency.setValueAtTime(severity === "critical" ? 880 : 587.33, now); // A5 or D5
    if (severity === "critical") {
      osc.frequency.exponentialRampToValueAtTime(440, now + 0.3);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.6);
    }

    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + (severity === "critical" ? 0.7 : 0.4));

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start(now);
    osc.stop(now + (severity === "critical" ? 0.7 : 0.4));
  } catch (err) {
    // Audio context may require prior user interaction
  }
}

export class WebSocketService {
  private socket: WebSocket | null = null;
  private telemetryListeners: Set<TelemetryListener> = new Set();
  private alertListeners: Set<AlertListener> = new Set();
  private isConnecting = false;
  private shouldReconnect = true;
  private reconnectTimeout: any = null;

  private currentTenantId: string | null = null;
  private currentSiteId: string | null = null;
  private currentUserId: string | null = null;

  connect(tenantId: string, siteId: string, userId: string) {
    this.shouldReconnect = true;

    if (this.socket) {
      if (
        this.currentTenantId === tenantId &&
        this.currentSiteId === siteId &&
        this.currentUserId === userId
      ) {
        if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
          return;
        }
      } else {
        // Scoping parameters changed: close stale socket and reconnect with new parameters
        this.socket.close();
        this.socket = null;
      }
    }

    this.currentTenantId = tenantId;
    this.currentSiteId = siteId;
    this.currentUserId = userId;
    this.isConnecting = true;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
      ? `${window.location.hostname}:3001`
      : window.location.host;
    const url = `${protocol}//${host}/ws/live?tenant_id=${tenantId}&site_id=${siteId}&user_id=${userId}`;

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.isConnecting = false;
    };

    this.socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === "telemetry" && msg.record) {
          this.telemetryListeners.forEach((fn) => fn(msg.record));
        } else if ((msg.event === "alert_raised" || msg.event === "alert_escalated") && msg.alert) {
          playAudibleAlertChime(msg.alert.severity);
          this.alertListeners.forEach((fn) => fn(msg.alert, msg.event));
        } else if (msg.event === "alert_acknowledged" || msg.event === "alert_false_alarm" || msg.event === "alert_resolved") {
          this.alertListeners.forEach((fn) => fn(msg.alert, msg.event));
        }
      } catch (err) {
        // parse error
      }
    };

    this.socket.onclose = () => {
      this.socket = null;
      this.isConnecting = false;
      if (this.shouldReconnect) {
        this.reconnectTimeout = setTimeout(() => {
          this.connect(tenantId, siteId, userId);
        }, 3000);
      }
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  subscribeTelemetry(fn: TelemetryListener) {
    this.telemetryListeners.add(fn);
    return () => {
      this.telemetryListeners.delete(fn);
    };
  }

  subscribeAlerts(fn: AlertListener) {
    this.alertListeners.add(fn);
    return () => {
      this.alertListeners.delete(fn);
    };
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}

export const wsService = new WebSocketService();
