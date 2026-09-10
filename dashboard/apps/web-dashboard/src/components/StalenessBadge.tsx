import React, { useState, useEffect } from "react";
import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";

interface StalenessBadgeProps {
  asOf?: string;
  isStale?: boolean;
  thresholdSeconds?: number; // default 90s per NFR
  className?: string;
  compact?: boolean;
}

export const StalenessBadge: React.FC<StalenessBadgeProps> = ({
  asOf,
  isStale = false,
  thresholdSeconds = 90,
  className = "",
  compact = false,
}) => {
  const [ageSeconds, setAgeSeconds] = useState<number>(0);
  const [showTooltip, setShowTooltip] = useState<boolean>(false);

  useEffect(() => {
    const calculateAge = () => {
      if (!asOf) {
        setAgeSeconds(0);
        return;
      }
      const packetTime = new Date(asOf).getTime();
      const now = Date.now();
      const diffSec = Math.max(0, Math.floor((now - packetTime) / 1000));
      setAgeSeconds(diffSec);
    };

    calculateAge();
    const interval = setInterval(calculateAge, 1000);
    return () => clearInterval(interval);
  }, [asOf]);

  const exceedsThreshold = ageSeconds > thresholdSeconds || isStale;

  const formatAge = (sec: number) => {
    if (sec < 60) return `${sec}s ago`;
    const min = Math.floor(sec / 60);
    const remSec = sec % 60;
    if (min < 60) return `${min}m ${remSec}s ago`;
    const hrs = Math.floor(min / 60);
    return `${hrs}h ago`;
  };

  return (
    <div
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {exceedsThreshold ? (
        <div
          id="staleness-badge-warning"
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium tracking-wide transition-all duration-300 border bg-amber-950/70 border-amber-500/80 text-amber-300 glow-amber ${
            compact ? "px-1.5 py-0.5 text-[10px]" : ""
          }`}
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
          </span>
          <AlertTriangle className={compact ? "w-3 h-3" : "w-3.5 h-3.5 text-amber-400"} />
          <span>STALE ({formatAge(ageSeconds)})</span>
        </div>
      ) : (
        <div
          id="staleness-badge-nominal"
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium tracking-wide border bg-emerald-950/40 border-emerald-500/40 text-emerald-400 ${
            compact ? "px-1.5 py-0.5 text-[10px]" : ""
          }`}
        >
          <span className="relative flex h-2 w-2">
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
          </span>
          <CheckCircle2 className={compact ? "w-3 h-3" : "w-3.5 h-3.5 text-emerald-400"} />
          <span>LIVE ({formatAge(ageSeconds)})</span>
        </div>
      )}

      {/* Floating Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-slate-900/95 backdrop-blur border border-slate-700 rounded-lg shadow-2xl text-xs z-50 text-slate-200 pointer-events-none">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-1.5">
            <span className="font-semibold text-slate-100 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              Telemetry Heartbeat
            </span>
            <span
              className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded ${
                exceedsThreshold ? "bg-amber-900/80 text-amber-300" : "bg-emerald-900/80 text-emerald-300"
              }`}
            >
              {exceedsThreshold ? "Amber Warning" : "Nominal"}
            </span>
          </div>
          <div className="space-y-1 font-mono text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-400">Packet Timestamp:</span>
              <span>{asOf ? new Date(asOf).toLocaleTimeString() : "No sample"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Time Elapsed:</span>
              <span className={exceedsThreshold ? "text-amber-400 font-bold" : "text-emerald-400"}>
                {ageSeconds}s
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Threshold SLA:</span>
              <span>{thresholdSeconds}s maximum</span>
            </div>
            <div className="text-[10px] text-slate-400 italic pt-1 border-t border-slate-800 mt-1">
              {exceedsThreshold
                ? "Zero Silent Staleness breached. Local sensor mesh node packet delivery delayed."
                : "Heartbeat stream within real-time compliance window."}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
