export interface QuietHoursConfig {
  enabled: boolean;
  startHourUtc: number; // e.g. 22 (10 PM UTC)
  endHourUtc: number;   // e.g. 6 (6 AM UTC)
}

export const DEFAULT_QUIET_HOURS: QuietHoursConfig = {
  enabled: true,
  startHourUtc: 22,
  endHourUtc: 6,
};

/**
 * Checks whether the current time falls inside quiet hours.
 * IMPORTANT SAFETY RULE: Critical severity alerts ALWAYS override quiet hours!
 */
export function isNotificationSilencedByQuietHours(
  severity: "info" | "warning" | "critical",
  now: Date = new Date(),
  config: QuietHoursConfig = DEFAULT_QUIET_HOURS
): { silenced: boolean; reason?: string } {
  // CRITICAL SEVERITY OVERRIDES QUIET HOURS HARDCODED
  if (severity === "critical") {
    return {
      silenced: false,
      reason: "CRITICAL_SEVERITY_OVERRIDE_QUIET_HOURS",
    };
  }

  if (!config.enabled) {
    return { silenced: false };
  }

  const currentHour = now.getUTCHours();
  const inQuietHours =
    config.startHourUtc > config.endHourUtc
      ? currentHour >= config.startHourUtc || currentHour < config.endHourUtc
      : currentHour >= config.startHourUtc && currentHour < config.endHourUtc;

  if (inQuietHours) {
    return {
      silenced: true,
      reason: `SILENCED_DURING_QUIET_HOURS_${config.startHourUtc}:00_TO_${config.endHourUtc}:00_UTC`,
    };
  }

  return { silenced: false };
}
