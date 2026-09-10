import React from "react";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";
import {
  LayoutDashboard,
  Activity,
  Bell,
  Network,
  TrendingUp,
  FileText,
  MapPin,
  Settings,
  ChevronLeft,
  ChevronRight,
  Wifi,
  FileCode2,
} from "lucide-react";

export type SidebarPage =
  | "operations"
  | "sensors"
  | "alerts"
  | "mesh"
  | "trends"
  | "reports"
  | "map"
  | "contracts"
  | "settings";

interface SidebarProps {
  currentPage: SidebarPage;
  onSelectPage: (page: SidebarPage) => void;
  activeAlertCount?: number;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onSelectPage,
  activeAlertCount = 0,
  collapsed,
  onToggleCollapse,
}) => {
  const { currentTenantId, currentSiteId, availableTenants } = useTenant();
  const { currentUser } = useAuth();

  const tenantObj = availableTenants.find((t) => t.id === currentTenantId);
  const tenantName = tenantObj ? `${tenantObj.short_code} (${tenantObj.name.split(" ")[0]})` : currentTenantId;

  const navItems: { id: SidebarPage; label: string; icon: any; badge?: number }[] = [
    { id: "operations", label: "Operations", icon: LayoutDashboard },
    { id: "sensors", label: "Live Sensor View", icon: Activity },
    { id: "alerts", label: "Alerts", icon: Bell, badge: activeAlertCount },
    { id: "mesh", label: "Mesh Health", icon: Network },
    { id: "trends", label: "Trends", icon: TrendingUp },
    { id: "reports", label: "Reports", icon: FileText },
    { id: "map", label: "Map & GIS", icon: MapPin },
    { id: "contracts", label: "Data Contracts", icon: FileCode2 },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  return (
    <aside
      className={`bg-slate-950/90 border-r border-slate-800/80 flex flex-col justify-between shrink-0 transition-all duration-300 z-30 select-none ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Navigation Links */}
      <div className="p-3 space-y-1">
        <div className="flex items-center justify-between px-2 py-1.5 mb-2 text-[11px] font-mono text-slate-400 uppercase tracking-wider">
          {!collapsed && <span>Command Navigation</span>}
          <button
            onClick={onToggleCollapse}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors ml-auto"
          >
            {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
          </button>
        </div>

        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;

            return (
              <button
                key={item.id}
                id={`sidebar-link-${item.id}`}
                onClick={() => onSelectPage(item.id)}
                title={collapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-mono font-medium transition-all duration-150 relative ${
                  isActive
                    ? "bg-blue-600/15 text-blue-400 border border-blue-500/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/80 border border-transparent"
                }`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 transition-colors ${
                    isActive ? "text-blue-400" : "text-slate-400"
                  }`}
                />
                {!collapsed && (
                  <span className="flex-1 text-left truncate">{item.label}</span>
                )}
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                      isActive
                        ? "bg-red-500 text-white"
                        : "bg-red-500/20 text-red-400 border border-red-500/40"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Tenant & Site Context Card */}
      <div className="p-3 border-t border-slate-800/80 font-mono">
        {!collapsed ? (
          <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800/90 text-xs space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-slate-400 uppercase tracking-wider">
              <span>Tenant Context</span>
              <div className="flex items-center gap-1 text-emerald-400 font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Online</span>
              </div>
            </div>
            <div className="text-slate-200 font-bold truncate">{tenantName}</div>
            <div className="text-[11px] text-cyan-400 flex items-center gap-1 truncate">
              <MapPin className="w-3 h-3 shrink-0 text-cyan-400" />
              <span>{currentSiteId}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 p-1 text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" title="Connection: Online"></span>
            <div title={`Site: ${currentSiteId}`}>
              <MapPin className="w-4 h-4 text-cyan-400" />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
