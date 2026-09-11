import { exec } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export interface SmsDispatchLog {
  id: string;
  timestamp: string;
  recipientName: string;
  phoneNumber: string;
  message: string;
  command: string;
  success: boolean;
  output: string;
  error?: string;
  durationMs: number;
}

export class TermuxSmsService {
  private static host: string = process.env.TERMUX_SSH_HOST || "127.0.0.1";
  private static port: number = parseInt(process.env.TERMUX_SSH_PORT || "8022", 10);
  private static user: string = process.env.TERMUX_SSH_USER || "";
  private static password: string = process.env.TERMUX_SSH_PASSWORD || "1234";
  private static dispatchHistory: SmsDispatchLog[] = [];

  static getConfig() {
    return {
      host: this.host,
      port: this.port,
      user: this.user,
      password: this.password,
    };
  }

  static setConfig(config: { host?: string; port?: number; user?: string; password?: string }) {
    if (config.host) this.host = config.host;
    if (config.port) this.port = config.port;
    if (config.user !== undefined) this.user = config.user;
    if (config.password !== undefined) this.password = config.password;
  }

  static getHistory(): SmsDispatchLog[] {
    return [...this.dispatchHistory];
  }

  static clearHistory(): void {
    this.dispatchHistory = [];
  }

  /**
   * Sanitizes phone number to standard format (digits and leading plus sign only)
   */
  static sanitizePhoneNumber(phone: string): string {
    return phone.trim().replace(/[^\d+]/g, "");
  }

  /**
   * Escapes a message safely for bash/sh execution inside single quotes:
   * Replaces ' with '\''
   */
  static escapeShellMessage(msg: string): string {
    return msg.replace(/'/g, "'\\''").replace(/\r?\n/g, " ");
  }

  /**
   * Prepares the askpass script on Windows/Linux to provide SSH password non-interactively
   */
  private static getAskpassScript(): string {
    const isWindows = process.platform === "win32";
    const scriptPath = path.join(
      os.tmpdir(),
      isWindows ? "subsense_askpass.bat" : "subsense_askpass.sh"
    );

    const scriptContent = isWindows
      ? `@echo ${this.password}\r\n`
      : `#!/bin/sh\necho "${this.password}"\n`;

    fs.writeFileSync(scriptPath, scriptContent, { mode: 0o755 });
    return scriptPath;
  }

  /**
   * Dispatches a single SMS via Termux SSH:
   * ssh -p 8022 127.0.0.1 "termux-sms-send -n <phone> '<msg>'"
   */
  static async sendSms(
    phoneNumber: string,
    message: string,
    recipientName: string = "Emergency Contact"
  ): Promise<SmsDispatchLog> {
    const startTime = Date.now();
    const sanitizedPhone = this.sanitizePhoneNumber(phoneNumber);
    const escapedMsg = this.escapeShellMessage(message);

    const target = this.user ? `${this.user}@${this.host}` : this.host;
    const askpassScript = this.getAskpassScript();

    // Check if ed25519 identity file exists
    const idKeyPath = path.join(os.homedir(), ".ssh", "id_ed25519");
    const keyFlag = fs.existsSync(idKeyPath) ? `-i "${idKeyPath}"` : "";

    const cmd = `ssh -p ${this.port} ${keyFlag} -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${target} "termux-sms-send -n ${sanitizedPhone} '${escapedMsg}'"`;

    const logEntry: SmsDispatchLog = {
      id: `SMS-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      timestamp: new Date().toISOString(),
      recipientName,
      phoneNumber: sanitizedPhone,
      message,
      command: cmd,
      success: false,
      output: "",
      durationMs: 0,
    };

    const env = {
      ...process.env,
      SSH_ASKPASS: askpassScript,
      SSH_ASKPASS_REQUIRE: "force",
      DISPLAY: process.env.DISPLAY || ":0",
    };

    return new Promise((resolve) => {
      exec(cmd, { env, timeout: 20000 }, (err, stdout, stderr) => {
        logEntry.durationMs = Date.now() - startTime;
        logEntry.output = (stdout + "\n" + stderr).trim();

        if (err) {
          logEntry.success = false;
          logEntry.error = err.message;
          console.error(`[TERMUX SMS] Failed to send SMS to ${sanitizedPhone}: ${err.message}`);
        } else {
          logEntry.success = true;
          console.log(`[TERMUX SMS] Successfully executed SMS command to ${sanitizedPhone} (${logEntry.durationMs}ms)`);
        }

        this.dispatchHistory.unshift(logEntry);
        if (this.dispatchHistory.length > 100) {
          this.dispatchHistory = this.dispatchHistory.slice(0, 100);
        }

        resolve(logEntry);
      });
    });
  }

  /**
   * Broadcasts an emergency alert SMS to an array of recipients concurrently
   */
  static async broadcastAlertSms(
    recipients: Array<{ name: string; phoneNumber: string }>,
    alert: {
      alert_id?: string;
      severity: string;
      site_id?: string;
      zone_id?: string;
      explanation_summary?: string;
    }
  ): Promise<SmsDispatchLog[]> {
    if (!recipients || recipients.length === 0) {
      console.warn("[TERMUX SMS] No active recipients configured for SMS broadcast.");
      return [];
    }

    const severityUpper = alert.severity.toUpperCase();
    const isCritical = alert.severity === "critical";
    const site = alert.site_id || "PANEL7-JHARIA";
    const zone = alert.zone_id || "ZONE-C";
    const time = new Date().toLocaleTimeString("en-IN", { hour12: false });

    const message = isCritical
      ? `[SubSense CRITICAL ALERT] Strata collapse risk in ${site} (${zone}). Immediate roof displacement. EVACUATE MINE PANEL NOW. Time: ${time}`
      : `[SubSense WARNING] Strata deformation detected in ${site} (${zone}). Inspect monitoring stations and stand by. Time: ${time}`;

    console.log(`[TERMUX SMS] Initiating broadcast to ${recipients.length} recipients for ${severityUpper} alert...`);

    const promises = recipients.map((r) =>
      this.sendSms(r.phoneNumber, message, r.name)
    );

    return Promise.all(promises);
  }
}
