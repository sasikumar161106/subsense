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

  return (
    <div className="min-h-screen bg-[#060B14] text-slate-100 flex flex-col antialiased">
      <SubSenseAnalyticsDashboard />
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
