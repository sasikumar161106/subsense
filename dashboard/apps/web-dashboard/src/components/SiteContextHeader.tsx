import React from "react";
import { useTenant } from "../contexts/TenantContext";
import {
  MapPin,
  Cpu,
  Activity,
  Clock,
  ChevronRight,
  ShieldCheck,
  Radio,
  Layers,
} from "lucide-react";

interface SiteContextHeaderProps {
  totalNodesCount?: number;
  meshHealthLabel?: string;
  lastUpdated?: string;
  isLive?: boolean;
}

export const SiteContextHeader: React.FC<SiteContextHeaderProps> = ({
  totalNodesCount = 24,
  meshHealthLabel = "Healthy",
  lastUpdated = "09 Sep 2026, 04:15 PM",
  isLive = true,
}) => {
  const { currentTenantId, currentSiteId, availableTenants, availableSites } = useTenant();

  const tenantObj = availableTenants.find((t) => t.id === currentTenantId);
  const opCoName = tenantObj ? tenantObj.name : "Eastern Coalfields Limited";
  const opCoCode = tenantObj ? tenantObj.short_code : "ECL";

  const siteObj = availableSites.find((s) => s.id === currentSiteId);
  const siteTitle = siteObj ? siteObj.name : "Jharia Panel 7";

  return (
    <div className="bg-slate-900/70 border border-slate-800/90 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 font-mono select-none shadow-sm">
      {/* Left: Breadcrumbs & Site Title */}
      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <span>{opCoName}</span>
          <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
          <span className="text-cyan-400 font-semibold">{siteTitle}</span>
        </div>

        <div className="flex items-center gap-3">
          <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            {siteTitle}
          </h1>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-bold border border-slate-700">
            {opCoCode}
          </span>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800/80">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>LIVE</span>
          </div>
        </div>
      </div>

      {/* Right: Compact Metadata Badges */}
      <div className="flex flex-wrap items-center gap-2.5 sm:gap-4 text-xs">
        {/* Location */}
        <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800/80 px-3 py-1.5 rounded-lg">
          <MapPin className="w-3.5 h-3.5 text-slate-400" />
          <div>
            <div className="text-[10px] text-slate-400 uppercase">Location</div>
            <div className="text-slate-200 font-semibold">Jharia, Jharkhand</div>
          </div>
        </div>

        {/* Total Nodes */}
        <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800/80 px-3 py-1.5 rounded-lg">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <div>
            <div className="text-[10px] text-slate-400 uppercase">Total Nodes</div>
            <div className="text-slate-200 font-semibold">{totalNodesCount}</div>
          </div>
        </div>

        {/* Mesh Health */}
        <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800/80 px-3 py-1.5 rounded-lg">
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
          <div>
            <div className="text-[10px] text-slate-400 uppercase">Mesh Health</div>
            <div className="text-emerald-400 font-semibold">{meshHealthLabel}</div>
          </div>
        </div>

        {/* Last Updated */}
        <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800/80 px-3 py-1.5 rounded-lg">
          <Clock className="w-3.5 h-3.5 text-amber-400" />
          <div>
            <div className="text-[10px] text-slate-400 uppercase">Last Updated</div>
            <div className="text-slate-200 font-semibold">{lastUpdated}</div>
          </div>
        </div>
      </div>
    </div>
  );
};
