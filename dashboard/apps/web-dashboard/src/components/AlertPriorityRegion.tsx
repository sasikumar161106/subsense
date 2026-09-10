import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  Flame,
  ShieldCheck,
  Clock,
  Volume2,
  Check,
  XCircle,
  HelpCircle,
  BellRing,
} from "lucide-react";
import { AlertLifecycleEvent } from "@subsense/shared";

interface AlertPriorityRegionProps {
  activeAlerts: AlertLifecycleEvent[];
  onAcknowledgeClick: (alert: AlertLifecycleEvent) => void;
  onFalseAlarmClick: (alert: AlertLifecycleEvent) => void;
  onResolveClick: (alert: AlertLifecycleEvent) => void;
  onSimulateDrill: (severity: "warning" | "critical") => void;
  onSirenTrigger: () => void;
  userRole: string;
}

export const AlertPriorityRegion: React.FC<AlertPriorityRegionProps> = ({
  activeAlerts,
  onAcknowledgeClick,
  onFalseAlarmClick,
  onResolveClick,
  onSimulateDrill,
  onSirenTrigger,
  userRole,
}) => {
  const criticalOrWarningAlerts = activeAlerts.filter(
    (a) =>
      (a.severity === "critical" || a.severity === "warning") &&
      a.state !== "resolved" &&
      a.state !== "false_alarm"
  );

  const highestAlert = criticalOrWarningAlerts[0];
  const isCritical = highestAlert?.severity === "critical";

  // 5-minute countdown calculation for highest unacknowledged alert
  const [countdownSeconds, setCountdownSeconds] = useState<number>(300);

  useEffect(() => {
    if (!highestAlert) return;

    const calculateRemaining = () => {
      const raisedTime = new Date(highestAlert.raised_at).getTime();
      const fiveMinLimit = raisedTime + 5 * 60 * 1000;
      const remaining = Math.max(0, Math.floor((fiveMinLimit - Date.now()) / 1000));
      setCountdownSeconds(remaining);
    };

    calculateRemaining();
    const timer = setInterval(calculateRemaining, 1000);
    return () => clearInterval(timer);
  }, [highestAlert]);

  const formatCountdown = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  return (
    <div
      id="alert-priority-region"
      aria-label="Alert Priority Region"
      className="w-full transition-all duration-300 z-30 select-none"
    >
      {highestAlert ? (
        <div
          className={`w-full px-4 lg:px-6 py-3 border-b transition-colors duration-200 ${
            isCritical
              ? "bg-gradient-to-r from-red-950/90 via-slate-950 to-slate-950 border-red-600/90 shadow-[0_4px_20px_rgba(239,68,68,0.25)]"
              : "bg-gradient-to-r from-amber-950/80 via-slate-950 to-slate-950 border-amber-500/80 shadow-[0_4px_16px_rgba(245,158,11,0.2)]"
          }`}
        >
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3">
            {/* Left: Critical Badge & Alert Content */}
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div
                className={`p-2 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                  isCritical
                    ? "bg-red-600 text-white shadow-lg shadow-red-600/40 animate-pulse"
                    : "bg-amber-500 text-slate-950 font-bold"
                }`}
              >
                {isCritical ? <Flame className="w-5 h-5 text-white" /> : <AlertTriangle className="w-5 h-5" />}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span
                    className={`text-[11px] font-mono font-extrabold uppercase px-2 py-0.5 rounded tracking-wider ${
                      isCritical
                        ? "bg-red-600 text-white"
                        : "bg-amber-500 text-slate-950"
                    }`}
                  >
                    {highestAlert.severity === "critical" ? "CRITICAL ALERT" : "WARNING ALERT"}
                  </span>
                  <span className="text-xs font-mono font-bold text-slate-100">
                    {highestAlert.alert_id}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    {highestAlert.site_id} • {highestAlert.zone_id}
                  </span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold uppercase ${
                      highestAlert.state === "new"
                        ? "bg-red-950 text-red-300 border border-red-700 animate-pulse"
                        : highestAlert.state === "acknowledged"
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-600"
                        : "bg-purple-950 text-purple-300 border border-purple-600"
                    }`}
                  >
                    STATUS: {highestAlert.state.toUpperCase()}
                  </span>
                </div>

                <p className="text-xs text-slate-200 leading-relaxed max-w-4xl truncate sm:whitespace-normal font-sans">
                  {highestAlert.explanation_summary}
                </p>
              </div>
            </div>

            {/* Middle: Escalation Countdown Ladder */}
            <div className="flex items-center gap-3 shrink-0 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-lg font-mono text-xs">
              <div className="flex items-center gap-1.5 text-slate-400">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span>
                  {highestAlert.state === "new" ? "5-Min Timeout:" : "Countdown:"}
                </span>
              </div>
              <span
                className={`text-sm font-bold tracking-wider ${
                  highestAlert.state === "new"
                    ? countdownSeconds < 60
                      ? "text-red-400 animate-ping"
                      : "text-amber-400"
                    : "text-emerald-400"
                }`}
              >
                {highestAlert.state === "new" ? formatCountdown(countdownSeconds) : "DISARMED"}
              </span>
            </div>

            {/* Right: Action Buttons */}
            <div className="flex flex-wrap items-center gap-2 shrink-0 font-mono text-xs">
              {highestAlert.state === "new" ? (
                <button
                  id="btn-audible-acknowledge"
                  onClick={() => onAcknowledgeClick(highestAlert)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-md transition-colors"
                >
                  <Volume2 className="w-3.5 h-3.5" />
                  <span>Audible Acknowledge</span>
                </button>
              ) : (
                <button
                  disabled
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 font-bold opacity-90 cursor-default"
                >
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span>ACKNOWLEDGED</span>
                </button>
              )}

              <button
                id="btn-flag-false-alarm"
                onClick={() => onFalseAlarmClick(highestAlert)}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-medium transition-colors"
              >
                <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
                <span>False Alarm</span>
              </button>

              <button
                id="btn-resolve-alert"
                onClick={() => onResolveClick(highestAlert)}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-700 text-emerald-400 font-medium transition-colors"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Resolve</span>
              </button>

              <button
                id="btn-manual-siren"
                onClick={onSirenTrigger}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-red-700 hover:bg-red-600 text-white font-bold border border-red-500 shadow-md shadow-red-950 transition-colors"
              >
                <BellRing className="w-3.5 h-3.5 animate-bounce" />
                <span>Trigger Siren</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Empty State Banner — Clear Sector Status */
        <div className="w-full bg-slate-950/90 border-b border-slate-800/80 px-4 lg:px-6 py-2">
          <div className="flex items-center justify-between gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 text-emerald-400">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="font-bold tracking-wide uppercase">
                Alert Priority Region: Nominal
              </span>
              <span className="text-slate-400 hidden sm:inline">
                — Zero active critical subsidence breaches across monitored sector panels.
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-[11px] hidden md:inline">
                Simulate Drill:
              </span>
              <button
                id="btn-drill-warning"
                onClick={() => onSimulateDrill("warning")}
                className="px-2 py-0.5 rounded bg-amber-950/60 hover:bg-amber-900/80 border border-amber-700/60 text-amber-300 text-[11px] font-medium transition-colors"
              >
                + Test Warning
              </button>
              <button
                id="btn-drill-critical"
                onClick={() => onSimulateDrill("critical")}
                className="px-2 py-0.5 rounded bg-red-950/60 hover:bg-red-900/80 border border-red-700/60 text-red-300 text-[11px] font-medium transition-colors"
              >
                + Test Critical
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
