import React from "react";
import { Cpu, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface SensorSummaryKpisProps {
  totalNodes?: number;
  healthyNodes?: number;
  atRiskNodes?: number;
  offlineNodes?: number;
}

export const SensorSummaryKpis: React.FC<SensorSummaryKpisProps> = ({
  totalNodes = 24,
  healthyNodes = 21,
  atRiskNodes = 2,
  offlineNodes = 1,
}) => {
  const healthyPct = ((healthyNodes / totalNodes) * 100).toFixed(1);
  const atRiskPct = ((atRiskNodes / totalNodes) * 100).toFixed(1);
  const offlinePct = ((offlineNodes / totalNodes) * 100).toFixed(1);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
      {/* 1. Total Nodes */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
          <span>Total Nodes</span>
          <Cpu className="w-3.5 h-3.5 text-slate-400" />
        </div>
        <div className="text-xl font-bold text-white tracking-tight">{totalNodes}</div>
        <div className="text-[10px] text-slate-400">Deployed Mesh Array</div>
      </div>

      {/* 2. Healthy Nodes */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
          <span>Healthy Nodes</span>
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-emerald-400 tracking-tight">{healthyNodes}</span>
          <span className="text-xs font-semibold text-emerald-500/80">({healthyPct}%)</span>
        </div>
        <div className="text-[10px] text-slate-400">Nominal Telemetry</div>
      </div>

      {/* 3. Nodes at Risk */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
          <span>Nodes at Risk</span>
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-amber-400 tracking-tight">{atRiskNodes}</span>
          <span className="text-xs font-semibold text-amber-500/80">({atRiskPct}%)</span>
        </div>
        <div className="text-[10px] text-slate-400">Warning / Tilt Creep</div>
      </div>

      {/* 4. Offline Nodes */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-400 uppercase tracking-wider">
          <span>Offline Nodes</span>
          <XCircle className="w-3.5 h-3.5 text-red-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-red-400 tracking-tight">{offlineNodes}</span>
          <span className="text-xs font-semibold text-red-500/80">({offlinePct}%)</span>
        </div>
        <div className="text-[10px] text-slate-400">Stale &gt;90s or Inactive</div>
      </div>
    </div>
  );
};
