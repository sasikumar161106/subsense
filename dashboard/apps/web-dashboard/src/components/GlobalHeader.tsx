import React from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTenant } from "../contexts/TenantContext";
import { UserRole, ROLE_DEFINITIONS } from "@subsense/shared";
import { SubSenseLogo } from "./SubSenseLogo";
import {
  Radio,
  Search,
  Bell,
  Settings,
  Shield,
  Building2,
  CheckCircle2,
  ChevronDown,
  User,
} from "lucide-react";

interface GlobalHeaderProps {
  onOpenSettings?: () => void;
  activeAlertCount?: number;
}

export const GlobalHeader: React.FC<GlobalHeaderProps> = ({
  onOpenSettings,
  activeAlertCount = 0,
}) => {
  const { currentUser, switchRole } = useAuth();
  const { currentTenantId, setCurrentTenantId, availableTenants } = useTenant();

  return (
    <header className="bg-slate-950/95 backdrop-blur border-b border-slate-800/80 px-4 lg:px-6 py-2.5 flex items-center justify-between gap-4 sticky top-0 z-40 select-none">
      {/* Left: SubSense Brand & Subtitle */}
      <div className="flex items-center gap-3 shrink-0">
        <SubSenseLogo size="sm" />
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold tracking-tight text-white font-mono text-base">
              SubSense
            </span>
            <span className="text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
              Control Room
            </span>
          </div>
          <p className="text-[10px] text-slate-400 font-mono tracking-wide hidden sm:block">
            Smarter Mines. Safer Tomorrow.
          </p>
        </div>
      </div>

      {/* Center: Global Search Field */}
      <div className="flex-1 max-w-md hidden md:block">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search nodes, sites, alerts..."
            className="w-full bg-slate-900/90 border border-slate-800 rounded-lg pl-9 pr-14 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 font-mono focus:outline-none focus:border-slate-700 transition-colors"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-slate-800/90 border border-slate-700/60 text-[10px] font-mono text-slate-400">
            Ctrl + K
          </kbd>
        </div>
      </div>

      {/* Right: Tenant, Role Switcher & User Profile Pill */}
      <div className="flex items-center gap-3 shrink-0 text-xs font-mono">
        {/* Tenant Selector */}
        <div className="hidden lg:flex items-center gap-1.5 bg-slate-900/80 border border-slate-800 px-2.5 py-1.5 rounded-lg">
          <Building2 className="w-3.5 h-3.5 text-amber-400" />
          <select
            id="global-tenant-select"
            value={currentTenantId}
            onChange={(e) => setCurrentTenantId(e.target.value)}
            disabled={currentUser.role === "dgms_regulator"}
            className="bg-transparent text-slate-200 font-bold focus:outline-none cursor-pointer text-xs"
          >
            {availableTenants.map((t) => (
              <option key={t.id} value={t.id} className="bg-slate-900 text-slate-200">
                {t.short_code} ({t.name.split(" ")[0]})
              </option>
            ))}
          </select>
        </div>

        {/* Role Selector */}
        <div className="flex items-center gap-1.5 bg-slate-900/80 border border-slate-800 px-2.5 py-1.5 rounded-lg">
          <Shield className="w-3.5 h-3.5 text-cyan-400" />
          <select
            id="global-role-select"
            value={currentUser.role}
            onChange={(e) => switchRole(e.target.value as UserRole)}
            className="bg-transparent text-cyan-300 font-bold focus:outline-none cursor-pointer text-xs"
          >
            <option value="mine_operator" className="bg-slate-900 text-slate-200">
              Mine Operator
            </option>
            <option value="geotech_planner" className="bg-slate-900 text-slate-200">
              Geotech Planner
            </option>
            <option value="dgms_regulator" className="bg-slate-900 text-slate-200">
              DGMS Regulator
            </option>
            <option value="site_admin" className="bg-slate-900 text-slate-200">
              Site Administrator
            </option>
          </select>
        </div>

        {/* Action Icons */}
        <div className="flex items-center gap-1">
          <button
            title="Active Notifications"
            className="relative p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800 transition-colors"
          >
            <Bell className="w-4 h-4" />
            {activeAlertCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
            )}
          </button>
          <button
            onClick={onOpenSettings}
            title="Settings & System Governance"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800 transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>

        {/* User Pill */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-bold text-xs">
            {currentUser.name.charAt(0)}
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-xs font-bold text-slate-200 leading-none">
              {currentUser.name.split(" (")[0]}
            </div>
            <div className="text-[10px] text-emerald-400 flex items-center gap-1 mt-0.5">
              <CheckCircle2 className="w-2.5 h-2.5" />
              <span>MFA Verified</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
