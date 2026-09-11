import React, { useState, useEffect } from "react";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { TenantProvider, useTenant } from "./contexts/TenantContext";
import { GlobalHeader } from "./components/GlobalHeader";
import { Sidebar, SidebarPage } from "./components/Sidebar";
import { AlertPriorityRegion } from "./components/AlertPriorityRegion";
import { SiteContextHeader } from "./components/SiteContextHeader";
import { PrimaryNavigation, PrimaryTab } from "./components/PrimaryNavigation";
import { AudibleAckModal } from "./components/AudibleAckModal";
import { FalseAlarmModal } from "./components/FalseAlarmModal";
import { OperationsCockpit } from "./views/OperationsCockpit";
import { GeotechTrendsView } from "./views/GeotechTrendsView";
import { MeshHealthView } from "./views/MeshHealthView";
import { AlertLogView } from "./views/AlertLogView";
import { RegulatorView } from "./views/RegulatorView";
import { AdminProvisioningView } from "./views/AdminProvisioningView";
import { ContractInspectorView } from "./views/ContractInspectorView";
import { Layer5MapStub } from "./components/Layer5MapStub";
import { SubSenseAnalyticsDashboard } from "./views/SubSenseAnalyticsDashboard";
import { AlertLifecycleEvent, FalseAlarmReason, NodeTelemetryRecord } from "@subsense/shared";
import { fetchApi } from "./services/api";
import { wsService } from "./services/socket";
import { BellRing } from "lucide-react";

const DashboardLayout: React.FC = () => {
  const { currentUser } = useAuth();
  const { currentTenantId, currentSiteId } = useTenant();

  const [sidebarPage, setSidebarPage] = useState<SidebarPage>("operations");
  const [primaryTab, setPrimaryTab] = useState<PrimaryTab>("sensor_overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"new_analytics" | "legacy_control">("new_analytics");

  const [activeAlerts, setActiveAlerts] = useState<AlertLifecycleEvent[]>([]);
  const [ackModalAlert, setAckModalAlert] = useState<AlertLifecycleEvent | null>(null);
  const [falseAlarmModalAlert, setFalseAlarmModalAlert] = useState<AlertLifecycleEvent | null>(null);
  const [sirenNotification, setSirenNotification] = useState<string | null>(null);

  // Sync role to default view
  useEffect(() => {
    switch (currentUser.role) {
      case "mine_operator":
        setSidebarPage("operations");
        setPrimaryTab("sensor_overview");
        break;
      case "geotech_planner":
        setSidebarPage("trends");
        setPrimaryTab("analytics");
        break;
      case "dgms_regulator":
        setSidebarPage("reports");
        setPrimaryTab("reports");
        break;
      case "site_admin":
        setSidebarPage("settings");
        break;
    }
  }, [currentUser.role]);

  // Load active alerts
  const refreshAlerts = async () => {
    try {
      const res = await fetchApi(`/alerts?site_id=${currentSiteId}`, {
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });
      if (res.alerts) {
        setActiveAlerts(res.alerts);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refreshAlerts();
    const interval = setInterval(refreshAlerts, 4000);
    return () => clearInterval(interval);
  }, [currentTenantId, currentSiteId]);

  // Real-time alert listener
  useEffect(() => {
    const unsub = wsService.subscribeAlerts(() => {
      refreshAlerts();
    });
    return unsub;
  }, []);

  // Sync sidebar and primary tab navigation
  const handleSelectSidebarPage = (page: SidebarPage) => {
    setSidebarPage(page);
    if (page === "operations" || page === "sensors") setPrimaryTab("sensor_overview");
    else if (page === "map") setPrimaryTab("map_view");
    else if (page === "mesh") setPrimaryTab("node_health");
    else if (page === "trends") setPrimaryTab("analytics");
    else if (page === "reports") setPrimaryTab("reports");
  };

  const handleSelectPrimaryTab = (tab: PrimaryTab) => {
    setPrimaryTab(tab);
    if (tab === "sensor_overview") setSidebarPage("operations");
    else if (tab === "map_view") setSidebarPage("map");
    else if (tab === "node_health") setSidebarPage("mesh");
    else if (tab === "analytics") setSidebarPage("trends");
    else if (tab === "reports") setSidebarPage("reports");
  };

  // Alert actions
  const handleAcknowledgeAlert = async (alertId: string, comment: string) => {
    await fetchApi(`/alerts/${alertId}/acknowledge`, {
      method: "POST",
      body: JSON.stringify({ user_id: currentUser.userId, comment }),
      tenantId: currentTenantId,
      userRole: currentUser.role,
      userId: currentUser.userId,
    });
    await refreshAlerts();
  };

  const handleFlagFalseAlarm = async (
    alertId: string,
    reason: FalseAlarmReason,
    notes: string,
    featureVector?: Record<string, any>
  ) => {
    await fetchApi(`/alerts/${alertId}/false-alarm`, {
      method: "POST",
      body: JSON.stringify({ reason, notes, feature_vector_snapshot: featureVector }),
      tenantId: currentTenantId,
      userRole: currentUser.role,
      userId: currentUser.userId,
    });
    await refreshAlerts();
  };

  const handleResolveAlert = async (alert: AlertLifecycleEvent) => {
    await fetchApi(`/alerts/${alert.alert_id}/resolve`, {
      method: "POST",
      tenantId: currentTenantId,
      userRole: currentUser.role,
      userId: currentUser.userId,
    });
    await refreshAlerts();
  };

  const handleSimulateDrill = async (severity: "warning" | "critical") => {
    await fetchApi("/alerts/simulate", {
      method: "POST",
      body: JSON.stringify({
        site_id: currentSiteId,
        severity,
        explanation:
          severity === "critical"
            ? "Accelerated extensometer displacement exceeding 3.7mm with continuous vibration pulses indicating impending strata delamination."
            : "Sustained tilt increase at N042, corroborated by 3 neighboring nodes over 40 minutes.",
      }),
      tenantId: currentTenantId,
      userRole: currentUser.role,
      userId: currentUser.userId,
    });
    await refreshAlerts();
  };

  const handleTriggerSiren = async () => {
    if (confirm("CONFIRM EMERGENCY EVACUATION: Trigger surface and underground sirens now?")) {
      const res = await fetchApi("/siren/trigger", {
        method: "POST",
        body: JSON.stringify({
          site_id: currentSiteId,
          reason: "Manual operator control-room protocol initiation",
        }),
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });

      setSirenNotification(`SIRENS ACTIVATED across ${currentSiteId}. Audit signature: ${res.audit_signature}`);
      setTimeout(() => setSirenNotification(null), 8000);
    }
  };

  const activeAlertCount = activeAlerts.filter(
    (a) => a.state !== "resolved" && a.state !== "false_alarm"
  ).length;

  const renderConsoleView = () => {
    switch (sidebarPage) {
      case "operations":
      case "sensors":
        return <OperationsCockpit />;
      case "trends":
        return <GeotechTrendsView />;
      case "mesh":
        return <MeshHealthView />;
      case "alerts":
        return (
          <AlertLogView
            onAcknowledgeClick={(a) => setAckModalAlert(a)}
            onFalseAlarmClick={(a) => setFalseAlarmModalAlert(a)}
            onResolveClick={handleResolveAlert}
            onSimulateDrill={handleSimulateDrill}
          />
        );
      case "reports":
        return <RegulatorView />;
      case "settings":
        return <AdminProvisioningView />;
      case "contracts":
        return <ContractInspectorView />;
      case "map":
        return (
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl min-h-[520px]">
            <Layer5MapStub telemetryMap={new Map()} selectedNodeId={null} onSelectNode={() => {}} />
          </div>
        );
      default:
        return <OperationsCockpit />;
    }
  };

  return (
    <div className="min-h-screen bg-[#060B14] text-slate-100 flex flex-col antialiased">
      {/* Top Dual-Mode Switcher Bar */}
      <div className="bg-slate-950/90 backdrop-blur border-b border-slate-800/80 px-4 py-1.5 flex flex-wrap items-center justify-between gap-2 text-xs sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 font-bold uppercase tracking-wider">Interface:</span>
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("new_analytics")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                viewMode === "new_analytics"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              📊 3D Analytics & Spatial Twin
            </button>
            <button
              onClick={() => setViewMode("legacy_control")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                viewMode === "legacy_control"
                  ? "bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              🎛️ Operations Cockpit & Multi-Role Console
            </button>
          </div>
        </div>

        {/* Quick Siren and Drill actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleSimulateDrill("warning")}
            className="px-2 py-0.5 text-[11px] font-mono rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/20 transition-colors"
          >
            Drill (Warning)
          </button>
          <button
            onClick={() => handleSimulateDrill("critical")}
            className="px-2 py-0.5 text-[11px] font-mono rounded bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-colors"
          >
            Drill (Critical)
          </button>
          <button
            onClick={handleTriggerSiren}
            className="px-2.5 py-0.5 text-[11px] font-mono font-bold rounded bg-red-600 text-white hover:bg-red-500 flex items-center gap-1 shadow-sm transition-colors"
          >
            <BellRing className="w-3 h-3 animate-pulse" />
            Siren Protocol
          </button>
        </div>
      </div>

      {sirenNotification && (
        <div className="bg-red-600/90 text-white font-mono text-xs px-4 py-2 text-center font-bold animate-pulse shadow-md">
          {sirenNotification}
        </div>
      )}

      {viewMode === "new_analytics" ? (
        <SubSenseAnalyticsDashboard />
      ) : (
        <div className="flex flex-col flex-1">
          <GlobalHeader
            activeAlertCount={activeAlertCount}
            onOpenSettings={() => setSidebarPage("settings")}
          />

          <AlertPriorityRegion
            activeAlerts={activeAlerts}
            onAcknowledgeClick={(a) => setAckModalAlert(a)}
            onFalseAlarmClick={(a) => setFalseAlarmModalAlert(a)}
            onResolveClick={handleResolveAlert}
            onSimulateDrill={handleSimulateDrill}
            onSirenTrigger={handleTriggerSiren}
            userRole={currentUser.role}
          />

          <SiteContextHeader />

          <div className="flex flex-1 overflow-hidden">
            <Sidebar
              currentPage={sidebarPage}
              onSelectPage={handleSelectSidebarPage}
              activeAlertCount={activeAlertCount}
              collapsed={sidebarCollapsed}
              onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
            />

            <main className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-4">
              <PrimaryNavigation
                activeTab={primaryTab}
                onSelectTab={handleSelectPrimaryTab}
              />
              {renderConsoleView()}
            </main>
          </div>
        </div>
      )}

      {/* Modals */}
      <AudibleAckModal
        alert={ackModalAlert}
        isOpen={ackModalAlert !== null}
        onClose={() => setAckModalAlert(null)}
        onConfirmAck={handleAcknowledgeAlert}
      />

      <FalseAlarmModal
        alert={falseAlarmModalAlert}
        isOpen={falseAlarmModalAlert !== null}
        onClose={() => setFalseAlarmModalAlert(null)}
        onSubmitFalseAlarm={handleFlagFalseAlarm}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <TenantProvider>
        <DashboardLayout />
      </TenantProvider>
    </AuthProvider>
  );
};

export default App;
