import React from "react";
import {
  Activity,
  MapPin,
  Network,
  BarChart3,
  FileText,
} from "lucide-react";

export type PrimaryTab = "sensor_overview" | "map_view" | "node_health" | "analytics" | "reports";

interface PrimaryNavigationProps {
  activeTab: PrimaryTab;
  onSelectTab: (tab: PrimaryTab) => void;
}

export const PrimaryNavigation: React.FC<PrimaryNavigationProps> = ({
  activeTab,
  onSelectTab,
}) => {
  const tabs: { id: PrimaryTab; label: string; icon: any }[] = [
    { id: "sensor_overview", label: "Sensor Overview", icon: Activity },
    { id: "map_view", label: "Map View", icon: MapPin },
    { id: "node_health", label: "Node Health", icon: Network },
    { id: "analytics", label: "Analytics", icon: BarChart3 },
    { id: "reports", label: "Reports", icon: FileText },
  ];

  return (
    <div className="flex items-center gap-1 border-b border-slate-800 pb-0 overflow-x-auto select-none font-mono text-xs">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            id={`primary-tab-${tab.id}`}
            onClick={() => onSelectTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition-all duration-150 whitespace-nowrap ${
              isActive
                ? "border-blue-500 text-blue-400 bg-blue-950/20"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40"
            }`}
          >
            <Icon className={`w-4 h-4 ${isActive ? "text-blue-400" : "text-slate-400"}`} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
};
