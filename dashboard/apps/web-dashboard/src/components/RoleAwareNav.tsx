import React from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTenant } from "../contexts/TenantContext";
import { UserRole, ROLE_DEFINITIONS } from "@subsense/shared";
import {
  Activity,
  LineChart,
  Network,
  Bell,
  FileText,
  Settings,
  Shield,
  Radio,
  Building2,
  FileCode2,
} from "lucide-react";

export type NavTab =
  | "cockpit"
  | "trends"
  | "mesh"
  | "alerts"
  | "regulator"
  | "admin"
  | "contracts";

interface RoleAwareNavProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
}

export const RoleAwareNav: React.FC<RoleAwareNavProps> = ({ currentTab, onSelectTab }) => {
  const { currentUser, roleMetadata, switchRole } = useAuth();
  const { currentTenantId, setCurrentTenantId, availableTenants } = useTenant();

  // Role-appropriate tab availability
  const getVisibleTabs = (): { id: NavTab; label: string; icon: any }[] => {
    switch (currentUser.role) {
      case "mine_operator":
        return [
          { id: "cockpit", label: "Operations Cockpit", icon: Activity },
          { id: "alerts", label: "Alert Log & Acks", icon: Bell },
          { id: "mesh", label: "Local Mesh Health", icon: Network },
          { id: "contracts", label: "Data Contracts (14.x)", icon: FileCode2 },
        ];
      case "geotech_planner":
        return [
          { id: "trends", label: "Geotechnical Forecast Cones", icon: LineChart },
          { id: "cockpit", label: "Mine Strata Overview", icon: Activity },
          { id: "mesh", label: "Mesh Telemetry Health", icon: Network },
          { id: "contracts", label: "Data Contracts (14.x)", icon: FileCode2 },
        ];
      case "dgms_regulator":
        return [
          { id: "regulator", label: "DGMS Compliance Rollup", icon: Shield },
          { id: "alerts", label: "Cross-Mine Audit Ledger", icon: Bell },
          { id: "trends", label: "Jurisdiction Subsidence Trends", icon: LineChart },
          { id: "contracts", label: "Data Contracts (14.x)", icon: FileCode2 },
        ];
      case "site_admin":
        return [
          { id: "admin", label: "Zero-Downtime Provisioning", icon: Settings },
          { id: "mesh", label: "Gateway Network Topology", icon: Network },
          { id: "cockpit", label: "Live System Health", icon: Activity },
          { id: "contracts", label: "Data Contracts (14.x)", icon: FileCode2 },
        ];
      default:
        return [{ id: "cockpit", label: "Cockpit", icon: Activity }];
    }
  };

  const tabs = getVisibleTabs();

  return (
    <header className="bg-slate-950 border-b border-slate-800 sticky top-0 z-30">
      {/* Top utility bar: Branding, Tenant Selector, Role Switcher */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-900">
        {/* SubSense Brand Title */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-600 to-amber-400 flex items-center justify-center font-bold text-slate-950 shadow-md shadow-amber-500/20">
            <Radio className="w-4 h-4 text-slate-950 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-white font-mono text-sm sm:text-base">
                SubSense
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Layer 6 Cockpit
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono hidden sm:block">
              Smart Mine Subsidence Monitoring Platform (TDD-APP-006 Rev 2.1)
            </p>
          </div>
        </div>

        {/* Center/Right Controls: Tenant Switcher & Role Selector */}
        <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
          {/* Tenant Selector (Multi-Tenancy) */}
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-2.5 py-1.5 rounded-lg">
            <Building2 className="w-3.5 h-3.5 text-amber-400" />
            <label className="text-slate-400 text-[11px]">Tenant:</label>
            <select
              id="tenant-select"
              value={currentTenantId}
              onChange={(e) => setCurrentTenantId(e.target.value)}
              disabled={currentUser.role === "dgms_regulator"}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer font-bold"
            >
              {availableTenants.map((t) => (
                <option key={t.id} value={t.id} className="bg-slate-900 text-slate-200">
                  {t.short_code} ({t.name})
                </option>
              ))}
            </select>
            {currentUser.role === "dgms_regulator" && (
              <span className="text-[10px] bg-purple-950 text-purple-300 px-1 rounded border border-purple-800">
                Multi-Tenant Permit Scope
              </span>
            )}
          </div>

          {/* Role Switcher */}
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-2.5 py-1.5 rounded-lg">
            <Shield className="w-3.5 h-3.5 text-cyan-400" />
            <label className="text-slate-400 text-[11px]">Active Role:</label>
            <select
              id="role-select"
              value={currentUser.role}
              onChange={(e) => switchRole(e.target.value as UserRole)}
              className="bg-transparent text-cyan-300 font-bold focus:outline-none cursor-pointer"
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

          {/* Logged in User Pill */}
          <div className="hidden lg:flex items-center gap-2 pl-2 border-l border-slate-800">
            <div className="text-right">
              <div className="text-[11px] font-bold text-slate-200">{currentUser.name}</div>
              <div className="text-[10px] text-emerald-400 flex items-center justify-end gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> MFA Verified
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dynamic Role-Based Navigation Tabs */}
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center gap-1 overflow-x-auto py-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;

          return (
            <button
              key={tab.id}
              id={`nav-tab-${tab.id}`}
              onClick={() => onSelectTab(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-mono font-medium whitespace-nowrap transition-colors duration-150 ${
                isActive
                  ? "bg-slate-800 text-amber-400 border border-slate-700 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? "text-amber-400" : "text-slate-500"}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </header>
  );
};
