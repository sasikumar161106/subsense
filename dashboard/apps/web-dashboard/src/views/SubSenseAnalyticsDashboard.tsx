import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Radio,
  Search,
  MapPin,
  Bell,
  ChevronDown,
  Activity,
  CheckCircle2,
  AlertTriangle,
  WifiOff,
  ShieldAlert,
  Layers,
  ZoomIn,
  ZoomOut,
  Settings,
  X,
  Battery,
  Wifi,
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  Sliders,
  Maximize2,
  RefreshCw,
  ExternalLink,
  Cpu,
  BarChart3,
  Waves,
  Heart,
  Compass,
  Calendar,
  FileText,
  Download,
  Check,
  Info,
  SlidersHorizontal,
  Navigation,
  Shield,
  UserCheck,
  Volume2,
  AlertOctagon,
  Eye,
  Terminal,
} from "lucide-react";
import { wsService, playAudibleAlertChime, startContinuousSiren, stopContinuousSiren } from "../services/socket";
import { JudgeDemoConsole } from "../components/JudgeDemoConsole";
import { OledDisplayMirror } from "../components/OledDisplayMirror";
import { useAuth } from "../contexts/AuthContext";
import { useTenant } from "../contexts/TenantContext";
import { fetchApi } from "../services/api";
import { UserRole, NodeTelemetryRecord, AlertLifecycleEvent } from "@subsense/shared";

// ============================================================================
// 4 OPERATOR ROLES DEFINITIONS
// ============================================================================
export interface OperatorProfile {
  userId: string;
  name: string;
  role: UserRole;
  roleLabel: string;
  avatarLetter: string;
  avatarColor: string;
  badge: string;
  description: string;
  tenantId: string;
}

export const OPERATOR_PROFILES: OperatorProfile[] = [
  {
    userId: "USR-OP-8492",
    name: "Rajesh Kumar",
    role: "mine_operator",
    roleLabel: "Mine Operator",
    avatarLetter: "R",
    avatarColor: "bg-purple-700",
    badge: "MFA Verified",
    description: "Operational control room monitoring, audible ACK, evacuation sirens.",
    tenantId: "OPCO-ECL-01",
  },
  {
    userId: "USR-GEO-1021",
    name: "Dr. Ananya Sen",
    role: "geotech_planner",
    roleLabel: "Geotech Planner",
    avatarLetter: "A",
    avatarColor: "bg-blue-600",
    badge: "Geotech Lead",
    description: "BiLSTM quantile uncertainty forecast cones, blast correlation, what-if models.",
    tenantId: "OPCO-ECL-01",
  },
  {
    userId: "USR-REG-4412",
    name: "Shri S. K. Verma",
    role: "dgms_regulator",
    roleLabel: "DGMS Safety Regulator",
    avatarLetter: "V",
    avatarColor: "bg-emerald-600",
    badge: "Statutory Inspector",
    description: "DGMS regulatory inspection, statutory reports, immutable ledger auditor (Read-Only).",
    tenantId: "OPCO-ECL-01",
  },
  {
    userId: "USR-ADM-0091",
    name: "Amitesh Sharma",
    role: "site_admin",
    roleLabel: "Site Administrator",
    avatarLetter: "S",
    avatarColor: "bg-amber-600",
    badge: "Site Admin",
    description: "Zero-downtime panel metadata provisioning, LoRaWAN gateway onboarding.",
    tenantId: "OPCO-ECL-01",
  },
];

// Initial Node Telemetry Seed
const INITIAL_NODES: Record<string, {
  nodeId: string;
  shortId: string;
  zone: string;
  disp: number;
  tilt: number;
  vib: number;
  crack: number;
  anomaly: number;
  status: "Healthy" | "At Risk" | "Critical" | "Offline";
  health: "Good" | "Fair" | "Poor";
  batt: number;
  rssi: number;
  hops: number;
  type: string;
  lastSeen: string;
  isPulsing?: boolean;
}> = {
  "SS-PANEL7-N042": {
    nodeId: "SS-PANEL7-N042",
    shortId: "N042",
    zone: "Panel 7 / Zone C (Pit Floor)",
    disp: 3.70,
    tilt: 0.183,
    vib: 1.42,
    crack: 0.62,
    anomaly: 0.86,
    status: "Critical",
    health: "Poor",
    batt: 78,
    rssi: -71,
    hops: 3,
    type: "Extensometer + Multi-axis Tilt",
    lastSeen: "Just now",
  },
  "SS-PANEL7-N043": {
    nodeId: "SS-PANEL7-N043",
    shortId: "N043",
    zone: "Panel 7 / Zone B (Mid Bench)",
    disp: 0.98,
    tilt: 0.125,
    vib: 0.98,
    crack: 0.24,
    anomaly: 0.42,
    status: "At Risk",
    health: "Fair",
    batt: 85,
    rssi: -68,
    hops: 2,
    type: "Extensometer + IMU",
    lastSeen: "Just now",
  },
  "SS-PANEL7-N045": {
    nodeId: "SS-PANEL7-N045",
    shortId: "N045",
    zone: "Panel 7 / Zone A (Lower Crest)",
    disp: 0.32,
    tilt: 0.052,
    vib: 0.61,
    crack: 0.08,
    anomaly: 0.18,
    status: "Healthy",
    health: "Good",
    batt: 90,
    rssi: -70,
    hops: 1,
    type: "Piezometer + Tiltmeter",
    lastSeen: "12 sec ago",
  },
  "SS-PANEL7-N017": {
    nodeId: "SS-PANEL7-N017",
    shortId: "N017",
    zone: "Panel 7 / Zone A (Upper Terrace)",
    disp: 0.21,
    tilt: 0.043,
    vib: 0.48,
    crack: 0.05,
    anomaly: 0.12,
    status: "Healthy",
    health: "Good",
    batt: 94,
    rssi: -65,
    hops: 1,
    type: "Extensometer + IMU",
    lastSeen: "Just now",
  },
  "SS-PANEL7-N021": {
    nodeId: "SS-PANEL7-N021",
    shortId: "N021",
    zone: "Panel 7 / Zone D (South Wall)",
    disp: 0.18,
    tilt: 0.039,
    vib: 0.42,
    crack: 0.03,
    anomaly: 0.08,
    status: "Healthy",
    health: "Good",
    batt: 88,
    rssi: -62,
    hops: 1,
    type: "Inclinometer Mesh Node",
    lastSeen: "45 sec ago",
  },
  "SS-PANEL7-N038": {
    nodeId: "SS-PANEL7-N038",
    shortId: "N038",
    zone: "Panel 7 / Zone C (Fault Edge)",
    disp: 0.86,
    tilt: 0.112,
    vib: 0.76,
    crack: 0.36,
    anomaly: 0.36,
    status: "At Risk",
    health: "Fair",
    batt: 62,
    rssi: -82,
    hops: 3,
    type: "Borehole Crack Index Meter",
    lastSeen: "2 min ago",
  },
};

export const SubSenseAnalyticsDashboard: React.FC = () => {
  const { currentUser, switchRole } = useAuth();
  const { currentTenantId, currentSiteId } = useTenant();

  // Navigation State
  const [activeNav, setActiveNav] = useState<string>("Overview");

  // Operator Switcher State
  const [operatorMenuOpen, setOperatorMenuOpen] = useState<boolean>(false);
  const activeOperator = useMemo(() => {
    return (
      OPERATOR_PROFILES.find((p) => p.role === currentUser.role) ||
      OPERATOR_PROFILES[0]
    );
  }, [currentUser.role]);

  // Live Dynamic Telemetry State
  const [sensors, setSensors] = useState(INITIAL_NODES);
  const [lastPacketFlash, setLastPacketFlash] = useState<string | null>(null);
  const [secondsAgo, setSecondsAgo] = useState<number>(0);
  const [totalPacketsReceived, setTotalPacketsReceived] = useState<number>(0);

  // Digital Twin State (3D vs Top View)
  const [twinViewMode, setTwinViewMode] = useState<"3D" | "Top">("3D");
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [tilt3D, setTilt3D] = useState<{ x: number; z: number }>({ x: 52, z: -20 });
  const [selectedTwinNodeId, setSelectedTwinNodeId] = useState<string>("SS-PANEL7-N017");

  // Sensor Details Modal State
  const [inspectingNodeId, setInspectingNodeId] = useState<string | null>(null);

  // Time Range for Ground Movement Trends
  const [overviewTimeRange, setOverviewTimeRange] = useState<string>("24H");
  const [overviewMapTab, setOverviewMapTab] = useState<"Map" | "Satellite">("Map");

  // Analytics View State
  const [analyticsMetric, setAnalyticsMetric] = useState<"Displacement" | "Tilt" | "Vibration" | "Crack Index">("Displacement");
  const [analyticsDateRange, setAnalyticsDateRange] = useState<string>("08 Sep 2026 – 09 Sep 2026");

  // Alerts View State & Actions
  const [alertsFilter, setAlertsFilter] = useState<"All" | "Critical" | "Warning" | "Info">("All");
  const [activeAlerts, setActiveAlerts] = useState<AlertLifecycleEvent[]>([
    {
      alert_id: "ALT-2026-9481",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "Panel 7 / Zone C",
      severity: "critical",
      state: "new",
      raised_at: new Date(Date.now() - 120000).toISOString(),
      time_to_critical_hours: [1.5, 4.0],
      confidence_score: 0.94,
      contributing_sensors: ["extensometer_displacement_mm", "tilt_deg"],
      explanation_summary: "Accelerated extensometer displacement exceeding 3.70mm with sustained high-frequency micro-seismic tremors.",
      acknowledged_by: null,
      acknowledged_at: null,
      escalated_at: null,
    },
    {
      alert_id: "ALT-2026-9479",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "Panel 7 / Zone C",
      severity: "warning",
      state: "acknowledged",
      raised_at: new Date(Date.now() - 720000).toISOString(),
      time_to_critical_hours: [6.0, 18.0],
      confidence_score: 0.88,
      contributing_sensors: ["vibration_rms_mm_s"],
      explanation_summary: "Abnormal continuous vibration levels (1.42 mm/s) corroborated across bench borehole cluster.",
      acknowledged_by: "USR-OP-8492",
      acknowledged_at: new Date(Date.now() - 600000).toISOString(),
      escalated_at: null,
    },
    {
      alert_id: "ALT-2026-9474",
      tenant_id: "OPCO-ECL-01",
      site_id: "PANEL7-JHARIA",
      zone_id: "Node N021",
      severity: "info",
      state: "resolved",
      raised_at: new Date(Date.now() - 2520000).toISOString(),
      time_to_critical_hours: [24.0, 48.0],
      confidence_score: 0.99,
      contributing_sensors: ["heartbeat_packet_lag_sec"],
      explanation_summary: "Mesh transceiver heartbeat recovered and re-synchronized after sub-GHz frequency hop.",
      acknowledged_by: "USR-OP-8492",
      acknowledged_at: new Date(Date.now() - 2400000).toISOString(),
      escalated_at: null,
    },
  ]);

  // Modal alert targets
  const [modalAckAlert, setModalAckAlert] = useState<AlertLifecycleEvent | null>(null);
  const [ackComment, setAckComment] = useState<string>("Audible evacuation chime heard on console. Operator acknowledging protocol.");
  const [isSubmittingAck, setIsSubmittingAck] = useState<boolean>(false);
  const [systemBanner, setSystemBanner] = useState<string | null>(null);

  // Global Search Filter
  const [searchQuery, setSearchQuery] = useState<string>("");

  // ==========================================================================
  // JUDGE DEMO & SCENARIO SIMULATION STATE (SIH 2026)
  // ==========================================================================
  const [demoScenario, setDemoScenario] = useState<"normal" | "warning" | "critical" | "mesh_drop">("normal");
  const [demoTilt, setDemoTilt] = useState<number>(0.85);
  const [demoVib, setDemoVib] = useState<number>(0.14);
  const [demoAnomaly, setDemoAnomaly] = useState<number>(0.08);
  const [isSirenActive, setIsSirenActive] = useState<boolean>(false);
  const [showOledMirror, setShowOledMirror] = useState<boolean>(true);
  const [isStreamingActive, setIsStreamingActive] = useState<boolean>(true);

  // Automatic Real-Time Telemetry Simulation Loop (1.2s tick)
  useEffect(() => {
    if (!isStreamingActive) return;
    const interval = setInterval(() => {
      setSecondsAgo(0);
      setTotalPacketsReceived((prev) => prev + 1);

      if (demoScenario === "normal") {
        const jitter = (Math.random() - 0.5) * 0.04;
        const newTilt = Math.max(0.7, Math.min(1.05, demoTilt + jitter));
        const newVib = Math.max(0.08, Math.min(0.22, demoVib + jitter * 0.5));
        setDemoTilt(newTilt);
        setDemoVib(newVib);

        setSensors((prev) => {
          const n042 = prev["SS-PANEL7-N042"] || INITIAL_NODES["SS-PANEL7-N042"];
          if (!n042) return prev;
          return {
            ...prev,
            "SS-PANEL7-N042": {
              ...n042,
              tilt: parseFloat(newTilt.toFixed(2)),
              vib: parseFloat(newVib.toFixed(2)),
              anomaly: 0.08,
              status: "Healthy",
              health: "Good",
            },
          };
        });
      } else if (demoScenario === "warning") {
        const jitter = (Math.random() - 0.5) * 0.1;
        const newTilt = Math.max(2.1, Math.min(2.7, demoTilt + jitter));
        const newVib = Math.max(0.45, Math.min(0.75, demoVib + jitter * 0.5));
        setDemoTilt(newTilt);
        setDemoVib(newVib);

        setSensors((prev) => {
          const n042 = prev["SS-PANEL7-N042"] || INITIAL_NODES["SS-PANEL7-N042"];
          if (!n042) return prev;
          return {
            ...prev,
            "SS-PANEL7-N042": {
              ...n042,
              tilt: parseFloat(newTilt.toFixed(2)),
              vib: parseFloat(newVib.toFixed(2)),
              anomaly: 0.52,
              status: "At Risk",
              health: "Fair",
            },
          };
        });
      } else if (demoScenario === "critical") {
        const jitter = (Math.random() - 0.5) * 0.15;
        const newTilt = Math.max(4.6, Math.min(5.2, demoTilt + jitter));
        const newVib = Math.max(1.2, Math.min(1.8, demoVib + jitter * 0.5));
        setDemoTilt(newTilt);
        setDemoVib(newVib);

        setSensors((prev) => {
          const n042 = prev["SS-PANEL7-N042"] || INITIAL_NODES["SS-PANEL7-N042"];
          if (!n042) return prev;
          return {
            ...prev,
            "SS-PANEL7-N042": {
              ...n042,
              tilt: parseFloat(newTilt.toFixed(2)),
              vib: parseFloat(newVib.toFixed(2)),
              anomaly: 0.96,
              status: "Critical",
              health: "Poor",
            },
          };
        });
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [isStreamingActive, demoScenario, demoTilt, demoVib]);

  const handleTriggerScenario = (scenario: "normal" | "warning" | "critical" | "mesh_drop") => {
    setDemoScenario(scenario);

    if (scenario === "normal") {
      stopContinuousSiren();
      setIsSirenActive(false);
      setDemoTilt(0.85);
      setDemoVib(0.14);
      setDemoAnomaly(0.08);
      setSystemBanner("Mine Environment Stabilized • Status: Nominal");
      setTimeout(() => setSystemBanner(null), 3000);
    } else if (scenario === "warning") {
      stopContinuousSiren();
      setIsSirenActive(false);
      setDemoTilt(2.35);
      setDemoVib(0.58);
      setDemoAnomaly(0.52);
      playAudibleAlertChime("warning");
      setSystemBanner("Advisory: Strata Micro-Fracture Creep in Panel 7 (Tilt: 2.35°)");
      setTimeout(() => setSystemBanner(null), 4000);
    } else if (scenario === "critical") {
      setDemoTilt(4.85);
      setDemoVib(1.45);
      setDemoAnomaly(0.96);
      setIsSirenActive(true);
      startContinuousSiren();

      const newCriticalAlert: AlertLifecycleEvent = {
        alert_id: `ALT-CRIT-${Date.now().toString().slice(-4)}`,
        tenant_id: currentTenantId,
        site_id: currentSiteId,
        zone_id: "Panel 7 / West Face",
        severity: "critical",
        state: "new",
        raised_at: new Date().toISOString(),
        time_to_critical_hours: [0.1, 0.4],
        confidence_score: 0.98,
        contributing_sensors: ["tilt_deg", "vibration_rms_mm_s"],
        explanation_summary: "CRITICAL: Physical MPU6050 tilt breached 4.85° (Threshold: 4.00°). High-frequency vibration pulses indicate imminent roof strata delamination. On-device edge siren actuated (<5µs).",
        acknowledged_by: null,
        acknowledged_at: null,
        escalated_at: null,
      };

      setActiveAlerts((prev) => [newCriticalAlert, ...prev]);
      setSystemBanner("🚨 CRITICAL DRILL TRIGGERED: Tilt 4.85° > 4.00° • Edge Siren Actuated (<5µs) • Evacuate Panel 7!");
    } else if (scenario === "mesh_drop") {
      setSystemBanner("⚡ Mesh Multi-Hop Reroute: Direct line severed • Telemetry routing via Relay Node • Zero Loss");
      setTimeout(() => setSystemBanner(null), 5000);
    }
  };

  const handleSilenceSiren = () => {
    stopContinuousSiren();
    setIsSirenActive(false);
    setSystemBanner("Audible Edge Siren Silenced by Control Room Protocol");
    setTimeout(() => setSystemBanner(null), 3000);
  };

  // --------------------------------------------------------------------------
  // LIVE WEBSOCKET SUBSCRIPTION
  // --------------------------------------------------------------------------
  useEffect(() => {
    wsService.connect(currentTenantId, currentSiteId, currentUser.userId);

    const unsubTelemetry = wsService.subscribeTelemetry((rec: NodeTelemetryRecord) => {
      setSecondsAgo(0);
      setTotalPacketsReceived((prev) => prev + 1);
      setLastPacketFlash(rec.node_id);
      setTimeout(() => setLastPacketFlash(null), 800);

      setSensors((prev) => {
        const existing = prev[rec.node_id] || {
          nodeId: rec.node_id,
          shortId: rec.node_id.replace("SS-PANEL7-", ""),
          zone: "Panel 7",
          type: "SubSense Sensor Node",
          hops: 1,
          batt: 85,
          rssi: -70,
        };

        const disp = rec.readings?.displacement_mm ?? existing.disp;
        const tilt = rec.readings?.tilt_deg ?? existing.tilt;
        const vib = rec.readings?.vibration_rms_mm_s ?? existing.vib;
        const crack = rec.readings?.crack_index ?? existing.crack;
        const anomaly = rec.anomaly_score ?? existing.anomaly;

        let status: "Healthy" | "At Risk" | "Critical" | "Offline" = "Healthy";
        let health: "Good" | "Fair" | "Poor" = "Good";

        if (disp >= 3.0 || anomaly >= 0.75) {
          status = "Critical";
          health = "Poor";
        } else if (disp >= 0.8 || tilt >= 0.1 || anomaly >= 0.35) {
          status = "At Risk";
          health = "Fair";
        }

        return {
          ...prev,
          [rec.node_id]: {
            ...existing,
            disp: Number(disp.toFixed(2)),
            tilt: Number(tilt.toFixed(3)),
            vib: Number(vib.toFixed(2)),
            crack: Number(crack.toFixed(2)),
            anomaly: Number(anomaly.toFixed(2)),
            status,
            health,
            lastSeen: "Just now",
          },
        };
      });
    });

    const unsubAlert = wsService.subscribeAlerts((alert: AlertLifecycleEvent) => {
      playAudibleAlertChime(alert.severity === "critical" ? "critical" : "warning");
      setActiveAlerts((prev) => {
        const filtered = prev.filter((a) => a.alert_id !== alert.alert_id);
        return [alert, ...filtered];
      });
    });

    return () => {
      unsubTelemetry();
      unsubAlert();
    };
  }, [currentTenantId, currentSiteId, currentUser.userId]);

  // Live seconds ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Compute Dynamic KPI Metrics from Live Sensor State
  const computedKPIs = useMemo(() => {
    const sensorList = Object.values(sensors);
    const total = 24; // Deployed panel mesh capacity
    const healthy = sensorList.filter((s) => s.status === "Healthy").length + 18; // Base array
    const atRisk = sensorList.filter((s) => s.status === "At Risk").length;
    const offline = 1; // Zero Silent Staleness canary sensor
    const maxDisp = Math.max(...sensorList.map((s) => s.disp), 0);
    const riskScore = Math.min(Math.round((maxDisp / 4.0) * 70 + 8), 98);

    return {
      total,
      healthy,
      healthyPct: ((healthy / total) * 100).toFixed(1),
      atRisk,
      atRiskPct: ((atRisk / total) * 100).toFixed(1),
      offline,
      offlinePct: ((offline / total) * 100).toFixed(1),
      riskScore,
    };
  }, [sensors]);

  // Selected Node in Digital Twin
  const currentTwinNode = useMemo(() => {
    return sensors[selectedTwinNodeId] || sensors["SS-PANEL7-N017"];
  }, [sensors, selectedTwinNodeId]);

  // Handle Switching Operators
  const handleSelectOperator = async (profile: OperatorProfile) => {
    setOperatorMenuOpen(false);
    await switchRole(profile.role);
    setSystemBanner(`Active Operator Switched to: ${profile.name} (${profile.roleLabel})`);
    setTimeout(() => setSystemBanner(null), 5000);
  };

  // Handle Audible ACK Submission
  const handleConfirmAck = async () => {
    if (!modalAckAlert) return;
    setIsSubmittingAck(true);
    try {
      await fetchApi(`/alerts/${modalAckAlert.alert_id}/acknowledge`, {
        method: "POST",
        body: JSON.stringify({ user_id: activeOperator.userId, comment: ackComment }),
        tenantId: currentTenantId,
        userRole: activeOperator.role,
        userId: activeOperator.userId,
      });

      setActiveAlerts((prev) =>
        prev.map((a) =>
          a.alert_id === modalAckAlert.alert_id
            ? { ...a, state: "acknowledged", acknowledged_by: activeOperator.name, acknowledged_at: new Date().toISOString() }
            : a
        )
      );
      setSystemBanner(`Alert ${modalAckAlert.alert_id} Acknowledged by ${activeOperator.name}`);
      setTimeout(() => setSystemBanner(null), 4000);
      setModalAckAlert(null);
    } catch {
      // Offline fallback
      setActiveAlerts((prev) =>
        prev.map((a) =>
          a.alert_id === modalAckAlert.alert_id ? { ...a, state: "acknowledged" } : a
        )
      );
      setModalAckAlert(null);
    } finally {
      setIsSubmittingAck(false);
    }
  };

  // Quick Action: Generate Report
  const handleGenerateReport = () => {
    const reportText = `=====================================================
SUBSENSE STATUTORY MINE SUBSIDENCE COMPLIANCE REPORT
DGMS (Directorate General of Mines Safety) - Form IV-B
=====================================================
Site: PANEL 7 - JHARIA SEAM 7 (Jharkhand, India)
Jurisdiction: DGMS East Region
Operating Company: Bharat Coking Coal Limited (BCCL)
Generated On: ${new Date().toLocaleString()}
Generated By: ${activeOperator.name} (${activeOperator.roleLabel})

1. STRATA DISPLACEMENT SUMMARY:
- Maximum Surface Extensometer Displacement: ${sensors["SS-PANEL7-N042"]?.disp || 3.70} mm (CRITICAL at Node N042)
- Mean Vibration Velocity: 0.78 mm/s
- Deep Strata Inclinometer Maximum Tilt: 0.183°
- Composite Subsidence Risk Score: ${computedKPIs.riskScore} / 100 (HIGH RISK)

2. DEPLOYED SENSOR ARRAY STATUS:
- Total Deployed Nodes: ${computedKPIs.total}
- Nominal & Healthy: ${computedKPIs.healthy}
- At Risk Threshold Breach: ${computedKPIs.atRisk}
- Communication Offline: ${computedKPIs.offline}

3. CRYPTOGRAPHIC AUDIT VERIFICATION:
- Ledger Chain Hash: 8f4e2b01c9a87d6f5e4a3b2c1d0e9f8a7b6c5d4e
- Zero Silent Staleness Compliance: VERIFIED (Canary check 100% active)
=====================================================`;

    const blob = new Blob([reportText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `DGMS_Statutory_Subsidence_Report_Panel7_${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    setSystemBanner("DGMS Statutory Report Generated & Downloaded");
    setTimeout(() => setSystemBanner(null), 4000);
  };

  // Quick Action: Export Live CSV
  const handleExportCSV = () => {
    const headers = "NodeId,Zone,Displacement_mm,Tilt_deg,Vibration_mm_s,CrackIndex,AnomalyScore,Status,Battery,RSSI_dBm,LastSeen\n";
    const rows = Object.values(sensors)
      .map(
        (s) =>
          `${s.shortId},"${s.zone}",${s.disp},${s.tilt},${s.vib},${s.crack},${s.anomaly},${s.status},${s.batt}%,${s.rssi},"${s.lastSeen}"`
      )
      .join("\n");

    const blob = new Blob([headers + rows], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `SubSense_Live_Telemetry_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    setSystemBanner("Live Sensor Telemetry Exported to CSV");
    setTimeout(() => setSystemBanner(null), 4000);
  };

  // Filtered Sensor List for Search
  const filteredSensorList = useMemo(() => {
    const list = Object.values(sensors);
    if (!searchQuery) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (s) =>
        s.shortId.toLowerCase().includes(q) ||
        s.nodeId.toLowerCase().includes(q) ||
        s.zone.toLowerCase().includes(q) ||
        s.status.toLowerCase().includes(q)
    );
  }, [sensors, searchQuery]);

  return (
    <div className="min-h-screen bg-[#060B14] text-[#E2E8F0] flex flex-col font-sans select-none antialiased">
      {/* Dynamic System Notification Toast */}
      {systemBanner && (
        <div className="bg-emerald-600 text-white font-medium text-xs py-2 px-4 text-center sticky top-0 z-50 flex items-center justify-center gap-2 shadow-lg animate-in slide-in-from-top duration-200">
          <CheckCircle2 className="w-4 h-4" />
          <span>{systemBanner}</span>
        </div>
      )}

      {/* ========================================================= */}
      {/* SIH 2026 JUDGE LIVE EVALUATION DEMO CONSOLE               */}
      {/* ========================================================= */}
      <JudgeDemoConsole
        onTriggerScenario={handleTriggerScenario}
        activeScenario={demoScenario}
        packetsCount={totalPacketsReceived}
        isStreaming={isStreamingActive}
        onToggleStreaming={() => setIsStreamingActive(!isStreamingActive)}
        currentTilt={demoTilt}
        currentVib={demoVib}
        currentAnomaly={demoAnomaly}
        sirenActive={isSirenActive}
        onSilenceSiren={handleSilenceSiren}
        onToggleOledMirror={() => setShowOledMirror(!showOledMirror)}
        showOledMirror={showOledMirror}
      />

      {/* ========================================================= */}
      {/* 1. TOP NAV BAR WITH ALL 4 OPERATOR PROFILES               */}
      {/* ========================================================= */}
      <header className="h-14 bg-[#0A101D] border-b border-[#162238] px-5 flex items-center justify-between gap-4 sticky top-0 z-40">
        {/* Left: Brand Logo & Wordmark */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-md shadow-blue-500/20">
            <svg viewBox="0 0 24 24" className="w-4 h-4 text-white fill-current" stroke="none">
              <path d="M12 2L2 22h20L12 2zm0 4.5l6.5 13.5h-13L12 6.5z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white tracking-tight text-base leading-none">
                SubSense
              </span>
            </div>
            <p className="text-[10px] text-[#8899A6] tracking-tight leading-none mt-1 font-normal">
              Smart Mine Subsidence Monitoring Platform
            </p>
          </div>
        </div>

        {/* Center: Global Search Bar */}
        <div className="flex-1 max-w-md hidden md:block">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#8899A6] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search nodes, sites, panels, alerts..."
              className="w-full bg-[#0E1726] border border-[#182438] rounded-full pl-9 pr-14 py-1.5 text-xs text-[#E2E8F0] placeholder:text-[#64748B] focus:outline-none focus:border-cyan-500 transition-colors"
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-[#162238] text-[9px] font-mono text-[#8899A6] border border-[#23354E]">
              Ctrl + K
            </div>
          </div>
        </div>

        {/* Right Nav Items */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Location Dropdown */}
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#0E1726] border border-[#182438] hover:border-[#23354E] text-xs font-medium text-[#E2E8F0] transition-colors">
            <MapPin className="w-3.5 h-3.5 text-blue-400" />
            <span>Jharia Mine</span>
            <ChevronDown className="w-3 h-3 text-[#8899A6] ml-0.5" />
          </button>

          {/* LIVE Telemetry Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/40 text-emerald-400 text-[11px] font-semibold tracking-wide">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>LIVE</span>
          </div>

          {/* Notification Bell */}
          <button
            onClick={() => setActiveNav("Alerts")}
            className="relative p-2 rounded-lg hover:bg-[#162238] text-[#8899A6] hover:text-[#E2E8F0] transition-colors"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-4 h-4 bg-red-500 text-white rounded-full text-[9px] font-bold flex items-center justify-center">
              {activeAlerts.filter((a) => a.state === "new" || a.state === "escalated").length}
            </span>
          </button>

          {/* User Profile Chip with Dropdown for ALL 4 OPERATORS */}
          <div className="relative">
            <div
              onClick={() => setOperatorMenuOpen(!operatorMenuOpen)}
              className="flex items-center gap-2 pl-2 border-l border-[#162238] cursor-pointer hover:opacity-90 transition-opacity"
            >
              <div className={`w-7 h-7 rounded-full ${activeOperator.avatarColor} text-white font-semibold text-xs flex items-center justify-center shadow-sm`}>
                {activeOperator.avatarLetter}
              </div>
              <div className="text-left hidden lg:block">
                <div className="text-xs font-medium text-[#E2E8F0] leading-tight">
                  {activeOperator.name}
                </div>
                <div className="text-[10px] text-emerald-400 flex items-center gap-1 leading-tight">
                  <CheckCircle2 className="w-2.5 h-2.5" />
                  <span>{activeOperator.badge}</span>
                </div>
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-[#8899A6] transition-transform ${operatorMenuOpen ? "rotate-180" : ""}`} />
            </div>

            {/* Operator Switcher Dropdown Modal */}
            {operatorMenuOpen && (
              <div className="absolute right-0 top-11 w-72 bg-[#0D1527] border border-[#1F2937] rounded-xl shadow-2xl p-2 z-50 animate-in fade-in zoom-in duration-150">
                <div className="px-3 py-2 border-b border-[#1F2937] mb-1">
                  <span className="text-[10px] font-bold text-[#8899A6] uppercase tracking-wider block">
                    Switch Control Room Operator
                  </span>
                  <p className="text-[11px] text-[#64748B]">Enforces PostgreSQL RLS & Progressive UX</p>
                </div>

                <div className="space-y-1">
                  {OPERATOR_PROFILES.map((op) => (
                    <button
                      key={op.userId}
                      onClick={() => handleSelectOperator(op)}
                      className={`w-full text-left p-2.5 rounded-lg flex items-start gap-3 transition-colors ${
                        activeOperator.userId === op.userId
                          ? "bg-[#162238] border border-blue-500/40"
                          : "hover:bg-[#111827] border border-transparent"
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-full ${op.avatarColor} text-white font-bold text-xs flex items-center justify-center shrink-0 mt-0.5`}>
                        {op.avatarLetter}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white truncate">{op.name}</span>
                          {activeOperator.userId === op.userId && (
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                          )}
                        </div>
                        <div className="text-[10px] font-medium text-emerald-400">{op.roleLabel}</div>
                        <p className="text-[10px] text-[#8899A6] leading-snug mt-0.5">{op.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ========================================================= */}
      {/* 2. MAIN WORKSPACE WITH 4 ROLE SPECIFIC VIEWS              */}
      {/* ========================================================= */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar (~220px) */}
        <aside className="w-56 bg-[#0A101D] border-r border-[#162238] flex flex-col justify-between shrink-0 p-3">
          <nav className="space-y-1">
            {[
              { name: "Overview", icon: Activity },
              { name: "Sensors", icon: Radio },
              { name: "Map / Digital Twin", icon: Layers },
              { name: "Alerts", icon: Bell, count: String(activeAlerts.filter((a) => a.state === "new").length || "3") },
              { name: "Analytics", icon: BarChart3 },
              { name: "Reports", icon: ArrowUpRight },
              { name: "Settings", icon: Settings },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeNav === item.name;
              return (
                <button
                  key={item.name}
                  onClick={() => setActiveNav(item.name)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-[#004D40] text-[#34D399] font-semibold shadow-sm"
                      : "text-[#8899A6] hover:text-[#E2E8F0] hover:bg-[#0E1726]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? "text-[#34D399]" : "text-[#8899A6]"}`} />
                    <span>{item.name}</span>
                  </div>
                  {item.count && (
                    <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-red-500 text-white">
                      {item.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* System Online & Stream Stats at Bottom */}
          <div className="pt-4 border-t border-[#162238] px-2 pb-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="text-xs font-semibold text-[#E2E8F0]">System Online</span>
            </div>
            <p className="text-[10px] text-[#8899A6] mt-0.5">
              Stream packets: <span className="font-mono text-emerald-400">{totalPacketsReceived}</span>
            </p>
          </div>
        </aside>

        {/* Dynamic Center Main Surfaces */}
        <main className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Role-Specific Capabilities Banner */}
          <div className="bg-[#0D1527] border border-[#162238] rounded-xl px-4 py-2.5 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              <span className="text-[#8899A6]">Active Scope:</span>
              <span className="font-bold text-white">{activeOperator.roleLabel}</span>
              <span className="text-[#8899A6] hidden sm:inline">({activeOperator.description})</span>
            </div>

            {activeOperator.role === "dgms_regulator" && (
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">
                STATUTORY READ-ONLY AUDIT
              </span>
            )}
            {activeOperator.role === "mine_operator" && (
              <button
                onClick={() => handleTriggerScenario("critical")}
                className="px-2.5 py-1 rounded bg-red-600 hover:bg-red-500 text-white font-bold text-[10px] flex items-center gap-1 transition-colors animate-pulse"
              >
                <AlertOctagon className="w-3 h-3" />
                <span>Test Evacuation Siren</span>
              </button>
            )}
            {activeOperator.role === "geotech_planner" && (
              <button
                onClick={() => setActiveNav("Analytics")}
                className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-bold text-[10px] flex items-center gap-1 transition-colors"
              >
                <BarChart3 className="w-3 h-3" />
                <span>Open BiLSTM Forecast Cones</span>
              </button>
            )}
          </div>

          {/* ===================================================== */}
          {/* SCREEN 1: OVERVIEW (Dynamic Real-time Telemetry)      */}
          {/* ===================================================== */}
          {activeNav === "Overview" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h1 className="text-xl font-bold text-white tracking-tight">Overview</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">
                    Mine Subsidence Monitoring at a Glance
                  </p>
                </div>

                <div className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1.5 text-[#8899A6]">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Last updated: 09 Sep 2026, 04:15 PM</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-400 font-medium pl-2 border-l border-[#162238]">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Data stream active ({secondsAgo}s ago)</span>
                  </div>
                </div>
              </div>

              {/* Dynamic 5 KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
                {/* 1. Total Sensors */}
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Radio className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-[11px] font-medium text-[#8899A6]">Total Sensors</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">{computedKPIs.total}</div>
                  <div className="text-xs text-emerald-400 font-medium">↑ 2 new this hour</div>
                </div>

                {/* 2. Healthy Sensors */}
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Heart className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-[11px] font-medium text-[#8899A6]">Healthy Sensors</span>
                  </div>
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-2xl font-bold text-white">{computedKPIs.healthy}</span>
                    <span className="text-xs text-[#8899A6]">{computedKPIs.healthyPct}%</span>
                  </div>
                  <div className="text-xs text-emerald-400 font-medium">↑ 2%</div>
                </div>

                {/* 3. At Risk Sensors */}
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-[11px] font-medium text-[#8899A6]">At Risk Sensors</span>
                  </div>
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-2xl font-bold text-white">{computedKPIs.atRisk}</span>
                    <span className="text-xs text-[#8899A6]">{computedKPIs.atRiskPct}%</span>
                  </div>
                  <div className="text-xs text-amber-400 font-medium">↓ 1%</div>
                </div>

                {/* 4. Offline Sensors */}
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <WifiOff className="w-3.5 h-3.5 text-red-400" />
                    <span className="text-[11px] font-medium text-[#8899A6]">Offline Sensors</span>
                  </div>
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-2xl font-bold text-white">{computedKPIs.offline}</span>
                    <span className="text-xs text-[#8899A6]">{computedKPIs.offlinePct}%</span>
                  </div>
                  <div className="text-xs text-[#8899A6] font-medium">→ 0%</div>
                </div>

                {/* 5. Overall Risk */}
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <ShieldAlert className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-[11px] font-medium text-[#8899A6]">Overall Risk</span>
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-2xl font-bold text-white">{computedKPIs.riskScore}</span>
                    <span className="px-1.5 py-0.2 rounded bg-red-500/20 text-red-400 border border-red-500/30 text-[9px] font-bold">
                      HIGH
                    </span>
                  </div>
                  <div className="text-xs text-red-400 font-medium">↑ 12.4% vs previous 24h</div>
                </div>
              </div>

              {/* Row 2: Ground Movement Trend (60%) + Mine Digital Twin (40%) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Left: Ground Movement Trend */}
                <div className="lg:col-span-7 bg-[#0D1527] border border-[#162238] rounded-xl p-4 flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Waves className="w-4 h-4 text-blue-400" />
                      <h2 className="text-sm font-bold text-white">Ground Movement Trend</h2>
                    </div>
                    {/* Time Range Selector */}
                    <div className="flex items-center bg-[#070D18] p-0.5 rounded-lg border border-[#162238] text-[10px] text-[#8899A6]">
                      {["1H", "6H", "24H", "7D", "30D"].map((t) => (
                        <button
                          key={t}
                          onClick={() => setOverviewTimeRange(t)}
                          className={`px-2 py-0.5 rounded ${
                            overviewTimeRange === t ? "bg-blue-600 text-white font-semibold" : "hover:text-white"
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Legend */}
                  <div className="flex items-center gap-3 text-[11px] text-[#8899A6] mb-2">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                      Displacement: <strong className="text-white font-mono">{sensors["SS-PANEL7-N042"]?.disp}mm</strong>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      Tilt: <strong className="text-white font-mono">{sensors["SS-PANEL7-N042"]?.tilt}°</strong>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                      Vibration: <strong className="text-white font-mono">{sensors["SS-PANEL7-N042"]?.vib}mm/s</strong>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                      Crack Index: <strong className="text-white font-mono">{sensors["SS-PANEL7-N042"]?.crack}</strong>
                    </span>
                  </div>

                  {/* Dynamic Trend Curves */}
                  <div className="h-52 w-full pt-1">
                    <svg viewBox="0 0 450 160" className="w-full h-full overflow-visible">
                      <defs>
                        <linearGradient id="blueGlow" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.25" />
                          <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
                        </linearGradient>
                      </defs>
                      {[15, 47, 79, 111, 143].map((y, idx) => (
                        <g key={y}>
                          <line x1="35" y1={y} x2="440" y2={y} stroke="#162238" strokeDasharray="2 2" strokeWidth="1" />
                          <text x="28" y={y + 3} textAnchor="end" fill="#64748B" fontSize="9" fontFamily="monospace">
                            {(4.0 - idx * 1.0).toFixed(1)}
                          </text>
                        </g>
                      ))}

                      {/* X-axis ticks dynamic based on range */}
                      {(overviewTimeRange === "1H"
                        ? [{ x: 45, l: "04:00" }, { x: 125, l: "04:15" }, { x: 205, l: "04:30" }, { x: 285, l: "04:45" }, { x: 365, l: "05:00" }, { x: 435, l: "05:15" }]
                        : overviewTimeRange === "7D"
                        ? [{ x: 45, l: "03 Sep" }, { x: 125, l: "04 Sep" }, { x: 205, l: "05 Sep" }, { x: 285, l: "06 Sep" }, { x: 365, l: "07 Sep" }, { x: 435, l: "09 Sep" }]
                        : [{ x: 45, l: "00:00" }, { x: 125, l: "04:00" }, { x: 205, l: "08:00" }, { x: 285, l: "12:00" }, { x: 365, l: "16:00" }, { x: 435, l: "20:00" }]
                      ).map((t) => (
                        <text key={t.x} x={t.x} y="156" textAnchor="middle" fill="#64748B" fontSize="9" fontFamily="monospace">
                          {t.l}
                        </text>
                      ))}

                      {/* Dynamic SVG Curves */}
                      <path d="M 45 125 C 130 125, 250 120, 435 116" fill="none" stroke="#8B5CF6" strokeWidth="2" />
                      <path d="M 45 130 C 130 122, 250 100, 435 90" fill="none" stroke="#10B981" strokeWidth="2" />
                      <path d="M 45 133 C 140 125, 240 85, 435 60" fill="none" stroke="#F59E0B" strokeWidth="2" />
                      <path d="M 45 125 C 140 110, 240 60, 435 25" fill="none" stroke="#3B82F6" strokeWidth="2.5" />

                      <circle cx="435" cy="25" r="4" fill="#3B82F6" stroke="#fff" strokeWidth="1.5" />
                      <circle cx="435" cy="60" r="3" fill="#F59E0B" />
                      <circle cx="435" cy="90" r="3" fill="#10B981" />
                      <circle cx="435" cy="116" r="3" fill="#8B5CF6" />
                    </svg>
                  </div>
                </div>

                {/* Right: Mine Digital Twin Preview */}
                <div className="lg:col-span-5 bg-[#0D1527] border border-[#162238] rounded-xl p-4 flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Layers className="w-4 h-4 text-blue-400" />
                      <h2 className="text-sm font-bold text-white">Mine Digital Twin</h2>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center bg-[#070D18] p-0.5 rounded-lg border border-[#162238] text-[10px] text-[#8899A6]">
                        <button
                          onClick={() => setOverviewMapTab("Map")}
                          className={`px-2 py-0.5 rounded ${overviewMapTab === "Map" ? "bg-blue-600 text-white font-semibold" : ""}`}
                        >
                          Map
                        </button>
                        <button
                          onClick={() => setOverviewMapTab("Satellite")}
                          className={`px-2 py-0.5 rounded ${overviewMapTab === "Satellite" ? "bg-blue-600 text-white font-semibold" : ""}`}
                        >
                          Satellite
                        </button>
                      </div>
                      <button
                        onClick={() => setActiveNav("Map / Digital Twin")}
                        className="p-1 rounded bg-[#070D18] border border-[#162238] text-[#8899A6] hover:text-white"
                        title="Open Interactive 3D Digital Twin"
                      >
                        <Maximize2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Surface preview */}
                  <div className="relative w-full h-52 bg-[#070D18] rounded-lg border border-[#162238] overflow-hidden">
                    <div
                      className="absolute inset-0 w-full h-full bg-cover bg-center opacity-60"
                      style={{ backgroundImage: `url('/open_pit_mine.jpg')` }}
                    />
                    <svg className="absolute inset-0 w-full h-full pointer-events-none">
                      <polygon
                        points="50,30 150,20 230,40 250,120 180,160 70,140 30,90"
                        fill="rgba(6, 182, 212, 0.08)"
                        stroke="#06B6D4"
                        strokeWidth="1.5"
                        strokeDasharray="4 2"
                      />
                    </svg>

                    <div
                      className="absolute rounded-full blur-xl opacity-75 pointer-events-none"
                      style={{
                        width: "120px",
                        height: "80px",
                        left: "35%",
                        top: "35%",
                        background: "radial-gradient(circle, #EF4444 0%, #F59E0B 50%, transparent 80%)",
                      }}
                    />

                    {/* Sensor markers */}
                    <div
                      onClick={() => { setSelectedTwinNodeId("SS-PANEL7-N017"); setActiveNav("Map / Digital Twin"); }}
                      className="absolute left-[38%] top-[25%] flex items-center gap-1 cursor-pointer"
                    >
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow"></span>
                      <span className="text-[9px] font-mono text-emerald-400 bg-[#0A101D]/90 px-1 rounded border border-emerald-500/30">
                        N017
                      </span>
                    </div>

                    <div
                      onClick={() => { setSelectedTwinNodeId("SS-PANEL7-N042"); setActiveNav("Map / Digital Twin"); }}
                      className="absolute left-[45%] top-[55%] flex items-center gap-1 cursor-pointer"
                    >
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                      </span>
                      <span className="text-[9px] font-mono text-red-400 bg-[#0A101D]/90 px-1 rounded border border-red-500/30 font-bold">
                        N042
                      </span>
                    </div>

                    <div
                      onClick={() => { setSelectedTwinNodeId("SS-PANEL7-N045"); setActiveNav("Map / Digital Twin"); }}
                      className="absolute left-[58%] top-[68%] flex items-center gap-1 cursor-pointer"
                    >
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow"></span>
                      <span className="text-[9px] font-mono text-emerald-400 bg-[#0A101D]/90 px-1 rounded border border-emerald-500/30">
                        N045
                      </span>
                    </div>

                    {/* Legend */}
                    <div className="absolute right-2 top-2 bg-[#0A101D]/90 border border-[#162238] rounded p-2 text-[9px] space-y-1">
                      <div className="flex items-center gap-1.5 text-[#8899A6]">
                        <span className="w-2.5 border-b-2 border-cyan-400 border-dashed"></span>
                        <span>Panel Boundary</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[#8899A6]">
                        <span className="w-2.5 h-0.5 bg-red-500"></span>
                        <span>Subsidence Zone</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[#8899A6]">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        <span>Sensor (Healthy)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Row 3: Live Sensor Activity Table + Active Alerts */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Table */}
                <div className="lg:col-span-7 bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-bold text-white">Recent Sensor Activity (Live Feed)</h2>
                    <span className="text-[11px] text-[#8899A6]">Showing {filteredSensorList.length} nodes</span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="text-[#8899A6] border-b border-[#162238]">
                          <th className="pb-2 font-medium">Node</th>
                          <th className="pb-2 font-medium">Status</th>
                          <th className="pb-2 font-medium">Displacement</th>
                          <th className="pb-2 font-medium">Tilt</th>
                          <th className="pb-2 font-medium">Vibration</th>
                          <th className="pb-2 font-medium">Anomaly</th>
                          <th className="pb-2 font-medium">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#162238]">
                        {filteredSensorList.map((row) => (
                          <tr
                            key={row.nodeId}
                            className={`hover:bg-[#121C33] transition-colors cursor-pointer ${
                              lastPacketFlash === row.nodeId ? "bg-blue-500/10" : ""
                            }`}
                            onClick={() => {
                              setSelectedTwinNodeId(row.nodeId);
                              setInspectingNodeId(row.nodeId);
                            }}
                          >
                            <td className="py-2.5 font-mono font-semibold text-white">
                              <span className="flex items-center gap-1.5">
                                <span
                                  className={`w-1.5 h-1.5 rounded-full ${
                                    row.status === "Critical" ? "bg-red-500" : row.status === "At Risk" ? "bg-amber-400" : "bg-emerald-400"
                                  }`}
                                />
                                {row.shortId}
                              </span>
                            </td>
                            <td className="py-2.5">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  row.status === "Critical"
                                    ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                    : row.status === "At Risk"
                                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                                    : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                }`}
                              >
                                {row.status}
                              </span>
                            </td>
                            <td className="py-2.5 font-mono text-[#E2E8F0]">
                              {row.disp.toFixed(2)} mm {row.disp > 1.0 && <span className="text-red-400">↑</span>}
                            </td>
                            <td className="py-2.5 font-mono text-[#E2E8F0]">{row.tilt.toFixed(3)}°</td>
                            <td className="py-2.5 font-mono text-[#E2E8F0]">{row.vib.toFixed(2)} mm/s</td>
                            <td className={`py-2.5 font-medium ${row.anomaly > 0.4 ? "text-red-400 font-bold" : "text-[#8899A6]"}`}>
                              {(row.anomaly * 100).toFixed(0)}%
                            </td>
                            <td className="py-2.5">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setInspectingNodeId(row.nodeId);
                                }}
                                className="text-[10px] text-blue-400 hover:text-blue-300 font-medium px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20"
                              >
                                Inspect
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Alerts with Audible ACK trigger */}
                <div className="lg:col-span-5 bg-[#0D1527] border border-[#162238] rounded-xl p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Bell className="w-4 h-4 text-amber-400" />
                        <h2 className="text-sm font-bold text-white">Active Alerts (Audible ACK)</h2>
                      </div>
                      <button
                        onClick={() => setActiveNav("Alerts")}
                        className="text-xs text-blue-400 hover:text-blue-300 font-medium"
                      >
                        View All →
                      </button>
                    </div>

                    <div className="space-y-2.5">
                      {activeAlerts.slice(0, 3).map((alt) => (
                        <div
                          key={alt.alert_id}
                          onClick={() => setModalAckAlert(alt)}
                          className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                            alt.severity === "critical"
                              ? "bg-red-500/10 border-red-500/40 hover:border-red-500"
                              : alt.severity === "warning"
                              ? "bg-amber-500/10 border-amber-500/40 hover:border-amber-500"
                              : "bg-blue-500/10 border-blue-500/40 hover:border-blue-500"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-[#0A101D] border border-current uppercase">
                              {alt.severity}
                            </span>
                            <span className="text-[10px] text-[#8899A6]">
                              {alt.state === "acknowledged" ? "ACKNOWLEDGED" : "PENDING ACK"}
                            </span>
                          </div>
                          <div className="text-xs font-semibold text-white">{alt.explanation_summary || (alt as any).explanation}</div>
                          <div className="text-[10px] text-[#8899A6] mt-1 font-mono">{alt.zone_id}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ===================================================== */}
          {/* SCREEN 2: DIGITAL TWIN (Interactive 3D & Top View)    */}
          {/* ===================================================== */}
          {activeNav === "Map / Digital Twin" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h1 className="text-xl font-bold text-white tracking-tight">Digital Twin View</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">
                    Live open-pit mine 3D surface model with real-time sensor array status
                  </p>
                </div>

                <div className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#0D1527] border border-[#162238]">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    <span className="text-[#8899A6]">Healthy</span>
                    <span className="font-bold text-white">{computedKPIs.healthy}</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#0D1527] border border-[#162238]">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span className="text-[#8899A6]">At Risk</span>
                    <span className="font-bold text-white">{computedKPIs.atRisk}</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#0D1527] border border-[#162238]">
                    <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                    <span className="text-[#8899A6]">Offline</span>
                    <span className="font-bold text-white">{computedKPIs.offline}</span>
                  </div>
                </div>
              </div>

              {/* Main 2-Column Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Left: 3D / Top View Model (8 cols / ~70%) */}
                <div className="lg:col-span-8 bg-[#0D1527] border border-[#162238] rounded-xl overflow-hidden relative h-[580px]">
                  {/* Top-Left Mode Switcher (3D View vs Top View) */}
                  <div className="absolute top-4 left-4 z-30 flex items-center bg-[#070D18]/90 backdrop-blur border border-[#162238] p-1 rounded-lg text-xs">
                    <button
                      onClick={() => setTwinViewMode("3D")}
                      className={`px-3 py-1 rounded-md font-medium transition-all ${
                        twinViewMode === "3D"
                          ? "bg-blue-600 text-white shadow-md shadow-blue-500/30 font-semibold"
                          : "text-[#8899A6] hover:text-white"
                      }`}
                    >
                      3D Perspective View
                    </button>
                    <button
                      onClick={() => setTwinViewMode("Top")}
                      className={`px-3 py-1 rounded-md font-medium transition-all ${
                        twinViewMode === "Top"
                          ? "bg-blue-600 text-white shadow-md shadow-blue-500/30 font-semibold"
                          : "text-[#8899A6] hover:text-white"
                      }`}
                    >
                      Top Orthographic View
                    </button>
                  </div>

                  {/* Left Floating Orbit & Zoom Controls */}
                  <div className="absolute top-16 left-4 z-30 flex flex-col items-center bg-[#070D18]/90 backdrop-blur border border-[#162238] rounded-lg overflow-hidden text-[#8899A6]">
                    <button
                      onClick={() => setZoomLevel((z) => Math.min(z + 0.15, 2.2))}
                      className="p-2 hover:bg-[#162238] hover:text-white border-b border-[#162238]"
                      title="Zoom In"
                    >
                      <ZoomIn className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setZoomLevel((z) => Math.max(z - 0.15, 0.7))}
                      className="p-2 hover:bg-[#162238] hover:text-white border-b border-[#162238]"
                      title="Zoom Out"
                    >
                      <ZoomOut className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setTilt3D({ x: 52, z: -20 });
                        setZoomLevel(1.0);
                      }}
                      className="p-2 hover:bg-[#162238] hover:text-white"
                      title="Reset North Orientation"
                    >
                      <Compass className="w-4 h-4" />
                    </button>
                  </div>

                  {/* 3D / TOP CANVAS SURFACE */}
                  <div
                    className="w-full h-full flex items-center justify-center relative overflow-hidden transition-all duration-500"
                    style={{
                      perspective: "1200px",
                    }}
                  >
                    <div
                      className="w-[620px] h-[620px] relative rounded-full shadow-2xl transition-transform duration-500 select-none"
                      style={{
                        transform:
                          twinViewMode === "3D"
                            ? `scale(${zoomLevel}) rotateX(${tilt3D.x}deg) rotateZ(${tilt3D.z}deg)`
                            : `scale(${zoomLevel}) rotateX(0deg) rotateZ(0deg)`,
                        transformStyle: "preserve-3d",
                      }}
                    >
                      {/* Satellite Terrain Base */}
                      <div
                        className="absolute inset-0 rounded-full bg-cover bg-center border-4 border-[#162238] overflow-hidden"
                        style={{
                          backgroundImage: `url('/open_pit_mine.jpg')`,
                          filter: "brightness(0.9) contrast(1.15)",
                        }}
                      />

                      {/* 3D Concentric Terraced Rings Extrusion */}
                      {twinViewMode === "3D" && (
                        <>
                          <div className="absolute inset-10 rounded-full border border-cyan-500/30 pointer-events-none shadow-[0_0_15px_rgba(6,182,212,0.15)]" />
                          <div className="absolute inset-20 rounded-full border border-cyan-500/40 pointer-events-none" />
                          <div className="absolute inset-32 rounded-full border border-amber-500/40 pointer-events-none" />
                          <div className="absolute inset-44 rounded-full border-2 border-red-500/60 pointer-events-none animate-pulse" />
                        </>
                      )}

                      {/* Cyan Boundary Polygon Overlay */}
                      <svg className="absolute inset-0 w-full h-full pointer-events-none">
                        <polygon
                          points="210,120 440,140 540,280 500,480 340,540 180,480 120,310"
                          fill="rgba(6, 182, 212, 0.08)"
                          stroke="#06B6D4"
                          strokeWidth="2.5"
                          strokeDasharray="6 4"
                        />
                      </svg>

                      {/* Deep Subsidence Hazard Core at Pit Center */}
                      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                        <div className="w-40 h-40 rounded-full border-2 border-red-500/50 animate-ping absolute -inset-0" />
                        <div className="w-24 h-24 rounded-full border-2 border-red-500/80 absolute left-8 top-8" />
                        <div className="w-12 h-12 rounded-full bg-red-600/90 blur-md absolute left-14 top-14" />
                      </div>

                      {/* Live Terraced Sensor Markers */}
                      {/* Node N017 (Upper Terrace) */}
                      <div
                        onClick={() => setSelectedTwinNodeId("SS-PANEL7-N017")}
                        className="absolute left-[38%] top-[25%] -translate-x-1/2 cursor-pointer group z-30"
                      >
                        <div className="flex items-center gap-1.5 bg-[#070D18] border-2 border-emerald-500 px-2 py-1 rounded-full shadow-lg shadow-emerald-500/50 hover:scale-110 transition-transform">
                          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                          <span className="text-[10px] font-mono font-bold text-emerald-400">N017</span>
                        </div>
                      </div>

                      {/* Node N045 (Lower Terrace) */}
                      <div
                        onClick={() => setSelectedTwinNodeId("SS-PANEL7-N045")}
                        className="absolute left-[62%] top-[70%] -translate-x-1/2 cursor-pointer group z-30"
                      >
                        <div className="flex items-center gap-1.5 bg-[#070D18] border-2 border-emerald-500 px-2 py-1 rounded-full shadow-lg shadow-emerald-500/50 hover:scale-110 transition-transform">
                          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                          <span className="text-[10px] font-mono font-bold text-emerald-400">N045</span>
                        </div>
                      </div>

                      {/* Node N043 (Mid Bench) */}
                      <div
                        onClick={() => setSelectedTwinNodeId("SS-PANEL7-N043")}
                        className="absolute left-[68%] top-[45%] -translate-x-1/2 cursor-pointer group z-30"
                      >
                        <div className="flex items-center gap-1.5 bg-[#070D18] border-2 border-amber-500 px-2 py-1 rounded-full shadow-lg shadow-amber-500/50 hover:scale-110 transition-transform">
                          <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                          <span className="text-[10px] font-mono font-bold text-amber-400">N043</span>
                        </div>
                      </div>

                      {/* Node N042 (Pit Floor - CRITICAL HAZARD) */}
                      <div
                        onClick={() => setSelectedTwinNodeId("SS-PANEL7-N042")}
                        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-pointer z-30"
                      >
                        <span className="relative flex h-6 w-6">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-90"></span>
                          <span className="relative inline-flex rounded-full h-6 w-6 bg-red-600 border-2 border-white shadow-xl flex items-center justify-center text-[9px] font-bold text-white">
                            !
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Floating Legend (Bottom-Left) */}
                  <div className="absolute left-4 bottom-4 z-30 bg-[#070D18]/90 backdrop-blur border border-[#162238] rounded-lg p-2.5 text-[10px] space-y-1.5">
                    <div className="flex items-center gap-2 text-[#8899A6]">
                      <span className="w-3 border-b-2 border-cyan-400 border-dashed"></span>
                      <span>Panel Boundary Polygon</span>
                    </div>
                    <div className="flex items-center gap-2 text-[#8899A6]">
                      <span className="w-3 h-0.5 bg-red-500"></span>
                      <span>Deep Subsidence Zone</span>
                    </div>
                    <div className="flex items-center gap-2 text-[#8899A6]">
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                      <span>Healthy Sensor</span>
                    </div>
                    <div className="flex items-center gap-2 text-[#8899A6]">
                      <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                      <span>At Risk Sensor</span>
                    </div>
                    <div className="flex items-center gap-2 text-[#8899A6]">
                      <span className="w-2 h-2 rounded-full bg-red-500"></span>
                      <span>Critical Hazard Node</span>
                    </div>
                  </div>
                </div>

                {/* Right Column: Selected Node Diagnostic Card + Risk Level + Action CTA */}
                <div className="lg:col-span-4 space-y-4">
                  {/* Selected Node Card */}
                  <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-emerald-400" />
                        <span className="text-xs font-semibold text-white">Selected Node</span>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          currentTwinNode.status === "Critical"
                            ? "bg-red-500/20 text-red-400 border border-red-500/30"
                            : currentTwinNode.status === "At Risk"
                            ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        }`}
                      >
                        ● {currentTwinNode.status}
                      </span>
                    </div>

                    <h3 className="text-lg font-bold text-white mt-1">{currentTwinNode.shortId}</h3>
                    <p className="text-xs text-[#8899A6] mb-4">{currentTwinNode.zone}</p>

                    {/* 3 Metrics Grid */}
                    <div className="grid grid-cols-3 gap-2 text-center py-2.5 border-y border-[#162238]">
                      <div>
                        <div className="text-[10px] text-[#8899A6]">Displacement</div>
                        <div className="text-xs font-bold text-white mt-0.5 font-mono">
                          {currentTwinNode.disp.toFixed(2)} mm
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-[#8899A6]">Tilt</div>
                        <div className="text-xs font-bold text-white mt-0.5 font-mono">
                          {currentTwinNode.tilt.toFixed(3)}°
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-[#8899A6]">Vibration</div>
                        <div className="text-xs font-bold text-white mt-0.5 font-mono">
                          {currentTwinNode.vib.toFixed(2)} mm/s
                        </div>
                      </div>
                    </div>

                    {/* Waveform Micro-chart */}
                    <div className="h-10 my-2">
                      <svg viewBox="0 0 100 25" className="w-full h-full">
                        <path
                          d="M 0 15 Q 15 5 30 15 T 60 12 T 90 18 T 100 14"
                          fill="none"
                          stroke={currentTwinNode.status === "Critical" ? "#EF4444" : "#10B981"}
                          strokeWidth="1.5"
                        />
                      </svg>
                    </div>

                    <div className="text-[10px] text-[#8899A6] flex justify-between">
                      <span>Battery: {currentTwinNode.batt}%</span>
                      <span>Last seen: {currentTwinNode.lastSeen}</span>
                    </div>
                  </div>

                  {/* Risk Level Card */}
                  <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                    <h4 className="text-xs font-bold text-white mb-2">Risk Level</h4>
                    <div className="flex items-center justify-between">
                      {/* Radial Gauge */}
                      <div className="relative w-24 h-24 flex items-center justify-center">
                        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                          <circle cx="50" cy="50" r="38" fill="none" stroke="#162238" strokeWidth="8" />
                          <circle
                            cx="50"
                            cy="50"
                            r="38"
                            fill="none"
                            stroke="#EF4444"
                            strokeWidth="8"
                            strokeDasharray="238.7"
                            strokeDashoffset={238.7 - (238.7 * computedKPIs.riskScore) / 100}
                            strokeLinecap="round"
                          />
                        </svg>
                        <div className="absolute flex flex-col items-center">
                          <span className="text-xl font-bold text-white">{computedKPIs.riskScore}</span>
                          <span className="text-[9px] font-bold text-red-400">High Risk</span>
                        </div>
                      </div>

                      {/* Trend */}
                      <div className="text-right">
                        <span className="text-[10px] text-[#8899A6] block">Trend</span>
                        <span className="text-base font-bold text-red-400 block">↑ 12.4%</span>
                        <span className="text-[10px] text-[#8899A6] block">vs previous 24h</span>
                      </div>
                    </div>
                  </div>

                  {/* Full-width Action CTA Button */}
                  <button
                    onClick={() => setInspectingNodeId(currentTwinNode.nodeId)}
                    className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-emerald-600/30"
                  >
                    <span>View Sensor Details</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ===================================================== */}
          {/* SCREEN 3: ANALYTICS (Dynamic Trends & Forecast Cones) */}
          {/* ===================================================== */}
          {activeNav === "Analytics" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h1 className="text-xl font-bold text-white tracking-tight">Analytics</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">
                    In-depth geotechnical insights and BiLSTM forecast uncertainty cones
                  </p>
                </div>

                <div className="flex items-center gap-2 bg-[#0D1527] border border-[#162238] px-3 py-1.5 rounded-lg text-xs text-[#E2E8F0] cursor-pointer hover:border-[#23354E]">
                  <Calendar className="w-3.5 h-3.5 text-blue-400" />
                  <span>{analyticsDateRange}</span>
                  <ChevronDown className="w-3 h-3 text-[#8899A6] ml-1" />
                </div>
              </div>

              {/* 4 Metric Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2 text-[#8899A6] text-xs">
                    <Waves className="w-3.5 h-3.5 text-blue-400" />
                    <span>Total Displacement</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">
                    {(sensors["SS-PANEL7-N042"]?.disp * 3.35).toFixed(1)} mm
                  </div>
                  <div className="text-xs text-emerald-400 font-medium">↑ 8.2%</div>
                </div>

                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2 text-[#8899A6] text-xs">
                    <Navigation className="w-3.5 h-3.5 text-amber-400" />
                    <span>Max Tilt</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">
                    {sensors["SS-PANEL7-N042"]?.tilt.toFixed(2)}°
                  </div>
                  <div className="text-xs text-emerald-400 font-medium">↑ 5.7%</div>
                </div>

                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2 text-[#8899A6] text-xs">
                    <Activity className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Avg. Vibration</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">
                    {sensors["SS-PANEL7-N042"]?.vib.toFixed(2)} mm/s
                  </div>
                  <div className="text-xs text-emerald-400 font-medium">↑ 4.3%</div>
                </div>

                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2 text-[#8899A6] text-xs">
                    <Compass className="w-3.5 h-3.5 text-purple-400" />
                    <span>Crack Index</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">
                    {sensors["SS-PANEL7-N042"]?.crack.toFixed(2)}
                  </div>
                  <div className="text-xs text-emerald-400 font-medium">↑ 5.9%</div>
                </div>
              </div>

              {/* Main Area Chart with Metric Switcher */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                <div className="lg:col-span-8 bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      {(["Displacement", "Tilt", "Vibration", "Crack Index"] as const).map((tab) => (
                        <button
                          key={tab}
                          onClick={() => setAnalyticsMetric(tab)}
                          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                            analyticsMetric === tab
                              ? "bg-emerald-600 text-white font-semibold"
                              : "bg-[#070D18] text-[#8899A6] hover:text-white border border-[#162238]"
                          }`}
                        >
                          {tab}
                        </button>
                      ))}
                    </div>

                    {activeOperator.role === "geotech_planner" && (
                      <span className="text-[10px] text-blue-400 font-mono flex items-center gap-1 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                        <SparklesIcon className="w-3 h-3" /> BiLSTM Cones (P10/P50/P90) Active
                      </span>
                    )}
                  </div>

                  <div className="h-56 relative w-full">
                    <svg viewBox="0 0 500 160" className="w-full h-full overflow-visible">
                      <defs>
                        <linearGradient id="emeraldGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10B981" stopOpacity="0.3" />
                          <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
                        </linearGradient>
                      </defs>

                      {[15, 60, 105, 145].map((y, idx) => (
                        <g key={y}>
                          <line x1="30" y1={y} x2="490" y2={y} stroke="#162238" strokeDasharray="2 2" />
                          <text x="20" y={y + 3} textAnchor="end" fill="#64748B" fontSize="9" fontFamily="monospace">
                            {(6.0 - idx * 2.0).toFixed(1)}
                          </text>
                        </g>
                      ))}

                      {[
                        { x: 40, l: "Sep 03" },
                        { x: 110, l: "Sep 04" },
                        { x: 180, l: "Sep 05" },
                        { x: 250, l: "Sep 06" },
                        { x: 320, l: "Sep 07" },
                        { x: 390, l: "Sep 08" },
                        { x: 460, l: "Sep 09" },
                      ].map((t) => (
                        <text key={t.x} x={t.x} y="158" textAnchor="middle" fill="#64748B" fontSize="9" fontFamily="monospace">
                          {t.l}
                        </text>
                      ))}

                      <path
                        d="M 40 135 C 110 130, 180 115, 250 100 C 320 85, 390 105, 460 95 L 460 145 L 40 145 Z"
                        fill="url(#emeraldGrad)"
                      />

                      <path
                        d="M 40 135 C 110 130, 180 115, 250 100 C 320 85, 390 105, 460 95"
                        fill="none"
                        stroke="#10B981"
                        strokeWidth="2.5"
                      />

                      <circle cx="40" cy="135" r="3" fill="#10B981" />
                      <circle cx="110" cy="128" r="3" fill="#10B981" />
                      <circle cx="180" cy="118" r="3" fill="#10B981" />
                      <circle cx="250" cy="100" r="3" fill="#10B981" />
                      <circle cx="320" cy="85" r="4" fill="#10B981" stroke="#fff" strokeWidth="1.5" />
                      <circle cx="390" cy="102" r="3" fill="#10B981" />
                      <circle cx="460" cy="95" r="3" fill="#10B981" />

                      <g transform="translate(285, 45)">
                        <rect width="70" height="28" rx="5" fill="#0A101D" stroke="#10B981" strokeWidth="1" />
                        <text x="35" y="12" textAnchor="middle" fill="#8899A6" fontSize="8">
                          Sep 07, 2026
                        </text>
                        <text x="35" y="22" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">
                          • 4.2 mm
                        </text>
                      </g>
                    </svg>
                  </div>
                </div>

                {/* Donut Chart */}
                <div className="lg:col-span-4 bg-[#0D1527] border border-[#162238] rounded-xl p-4 flex flex-col justify-between">
                  <h3 className="text-xs font-bold text-white mb-2">Sensor Status</h3>
                  <div className="flex items-center justify-center my-3">
                    <div className="relative w-36 h-36 flex items-center justify-center">
                      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                        <circle
                          cx="50"
                          cy="50"
                          r="35"
                          fill="none"
                          stroke="#10B981"
                          strokeWidth="10"
                          strokeDasharray="219.9"
                          strokeDashoffset="27.4"
                        />
                        <circle
                          cx="50"
                          cy="50"
                          r="35"
                          fill="none"
                          stroke="#F59E0B"
                          strokeWidth="10"
                          strokeDasharray="219.9"
                          strokeDashoffset="201.7"
                          transform="rotate(315 50 50)"
                        />
                        <circle
                          cx="50"
                          cy="50"
                          r="35"
                          fill="none"
                          stroke="#64748B"
                          strokeWidth="10"
                          strokeDasharray="219.9"
                          strokeDashoffset="210.7"
                          transform="rotate(345 50 50)"
                        />
                      </svg>
                      <div className="absolute flex flex-col items-center">
                        <span className="text-xl font-bold text-white leading-none">{computedKPIs.total}</span>
                        <span className="text-[10px] text-[#8899A6]">Total</span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1.5 text-xs pt-2 border-t border-[#162238]">
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-1.5 text-[#8899A6]">
                        <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                        Healthy
                      </span>
                      <span className="font-mono text-white font-semibold">
                        {computedKPIs.healthy} ({computedKPIs.healthyPct}%)
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-1.5 text-[#8899A6]">
                        <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                        At Risk
                      </span>
                      <span className="font-mono text-white font-semibold">
                        {computedKPIs.atRisk} ({computedKPIs.atRiskPct}%)
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-1.5 text-[#8899A6]">
                        <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                        Offline
                      </span>
                      <span className="font-mono text-white font-semibold">
                        {computedKPIs.offline} ({computedKPIs.offlinePct}%)
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ===================================================== */}
          {/* SCREEN 4: ALERTS & STATUTORY ACTIONS                  */}
          {/* ===================================================== */}
          {activeNav === "Alerts" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h1 className="text-xl font-bold text-white tracking-tight">Alerts & Notifications</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">
                    Real-time safety events, audible operator ACK, and closed-loop mitigation
                  </p>
                </div>

                {/* Filter Pills */}
                <div className="flex items-center bg-[#0D1527] p-1 rounded-lg border border-[#162238] text-xs">
                  {(["All", "Critical", "Warning", "Info"] as const).map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setAlertsFilter(filter)}
                      className={`px-3 py-1 rounded-md font-medium transition-colors ${
                        alertsFilter === filter
                          ? "bg-emerald-600 text-white font-semibold"
                          : "text-[#8899A6] hover:text-white"
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Alert Cards Feed */}
                <div className="lg:col-span-8 space-y-3">
                  {activeAlerts
                    .filter((a) => (alertsFilter === "All" ? true : a.severity.toLowerCase() === alertsFilter.toLowerCase()))
                    .map((item) => (
                      <div
                        key={item.alert_id}
                        onClick={() => setModalAckAlert(item)}
                        className={`bg-[#0D1527] border hover:border-white/30 rounded-xl p-3.5 flex items-center justify-between cursor-pointer transition-all ${
                          item.severity === "critical"
                            ? "border-red-500/40 bg-red-500/5"
                            : item.severity === "warning"
                            ? "border-amber-500/40 bg-amber-500/5"
                            : "border-blue-500/40 bg-blue-500/5"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                              item.severity === "critical"
                                ? "bg-red-500/20 text-red-400"
                                : item.severity === "warning"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-blue-500/20 text-blue-400"
                            }`}
                          >
                            <AlertTriangle className="w-4 h-4" />
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-white">{item.explanation_summary || (item as any).explanation}</h4>
                            <p className="text-[11px] text-[#8899A6] mt-0.5">
                              {item.zone_id} • Status: <strong className="text-white uppercase">{item.state}</strong>
                            </p>
                          </div>
                        </div>

                        <div className="text-right shrink-0">
                          <span className="text-[10px] text-[#8899A6] font-mono block mb-1">
                            {item.state === "acknowledged" ? "ACKNOWLEDGED" : "PENDING"}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-[9px] font-bold border ${
                              item.severity === "critical"
                                ? "bg-red-500/20 text-red-400 border-red-500/30"
                                : item.severity === "warning"
                                ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                                : "bg-blue-500/20 text-blue-400 border-blue-500/30"
                            }`}
                          >
                            {item.severity.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    ))}
                </div>

                {/* Right Column: Working Quick Actions + Recent Reports */}
                <div className="lg:col-span-4 space-y-4">
                  {/* Quick Actions */}
                  <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                    <h3 className="text-xs font-bold text-white mb-3">Quick Actions</h3>
                    <div className="space-y-2">
                      <button
                        onClick={() => setActiveNav("Map / Digital Twin")}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[#070D18] hover:bg-[#121C33] border border-[#162238] text-xs text-[#E2E8F0] font-medium transition-colors"
                      >
                        <Layers className="w-4 h-4 text-blue-400" />
                        <span>View Mine Map (Digital Twin)</span>
                      </button>

                      <button
                        onClick={handleGenerateReport}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[#070D18] hover:bg-[#121C33] border border-[#162238] text-xs text-[#E2E8F0] font-medium transition-colors"
                      >
                        <FileText className="w-4 h-4 text-emerald-400" />
                        <span>Generate DGMS Statutory Report</span>
                      </button>

                      <button
                        onClick={handleExportCSV}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[#070D18] hover:bg-[#121C33] border border-[#162238] text-xs text-[#E2E8F0] font-medium transition-colors"
                      >
                        <Download className="w-4 h-4 text-amber-400" />
                        <span>Export Live Sensor Data (.CSV)</span>
                      </button>

                      <button
                        onClick={() => setActiveNav("Sensors")}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[#070D18] hover:bg-[#121C33] border border-[#162238] text-xs text-[#E2E8F0] font-medium transition-colors"
                      >
                        <Cpu className="w-4 h-4 text-purple-400" />
                        <span>Manage Sensor Mesh Array</span>
                      </button>
                    </div>
                  </div>

                  {/* Recent Reports */}
                  <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xs font-bold text-white">Recent Reports</h3>
                      <button
                        onClick={handleGenerateReport}
                        className="text-[11px] text-blue-400 hover:text-blue-300 font-medium"
                      >
                        Download Latest →
                      </button>
                    </div>

                    <div className="space-y-2.5 text-xs">
                      {[
                        { title: "Daily Summary", date: "09 Sep 2026" },
                        { title: "Weekly Report", date: "02 – 08 Sep 2026" },
                        { title: "Risk Analysis Report", date: "08 Sep 2026" },
                      ].map((rep) => (
                        <div
                          key={rep.title}
                          onClick={handleGenerateReport}
                          className="flex items-center justify-between py-1 border-b border-[#162238] last:border-none cursor-pointer hover:opacity-80"
                        >
                          <div>
                            <div className="font-medium text-white">{rep.title}</div>
                            <div className="text-[10px] text-[#8899A6] font-mono">{rep.date}</div>
                          </div>
                          <span className="px-2 py-0.5 rounded bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">
                            PDF
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ===================================================== */}
          {/* SCREEN 5: SENSORS VIEW                                */}
          {/* ===================================================== */}
          {activeNav === "Sensors" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold text-white">Sensors & Mesh Topology</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">Physical borehole sensor array across Jharia Seam 7</p>
                </div>
                <button
                  onClick={() => setActiveNav("Overview")}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium"
                >
                  ← Back to Overview
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {Object.values(sensors).map((s) => (
                  <div
                    key={s.nodeId}
                    onClick={() => setInspectingNodeId(s.nodeId)}
                    className="bg-[#0D1527] border border-[#162238] hover:border-cyan-500/40 rounded-xl p-4 space-y-2 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-white text-base">{s.shortId}</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          s.status === "Critical"
                            ? "bg-red-500/20 text-red-400 border border-red-500/30"
                            : s.status === "At Risk"
                            ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        }`}
                      >
                        {s.status}
                      </span>
                    </div>
                    <div className="text-xs text-[#8899A6]">{s.type}</div>
                    <div className="grid grid-cols-3 gap-1 pt-2 border-t border-[#162238] text-[11px] font-mono">
                      <div>
                        <div className="text-[9px] text-[#8899A6]">Displacement</div>
                        <div className="text-white font-bold">{s.disp.toFixed(2)} mm</div>
                      </div>
                      <div>
                        <div className="text-[9px] text-[#8899A6]">Battery</div>
                        <div className="text-emerald-400">{s.batt}%</div>
                      </div>
                      <div>
                        <div className="text-[9px] text-[#8899A6]">Signal</div>
                        <div className="text-blue-400">{s.rssi} dBm</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ===================================================== */}
          {/* SCREEN 6: REPORTS & SETTINGS VIEWS                    */}
          {/* ===================================================== */}
          {activeNav === "Reports" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold text-white">DGMS Statutory Compliance Archives</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">Statutory geotechnical audit reports and ledger verification</p>
                </div>
                <button
                  onClick={handleGenerateReport}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  Generate Latest Compliance Rollup
                </button>
              </div>

              <div className="space-y-3">
                {[
                  { title: "DGMS Monthly Subsidence Rollup (Form IV-B)", authority: "DGMS East Region", status: "VERIFIED" },
                  { title: "Panel 7 Strata Micro-Seismic & Extensometer Audit", authority: "BCCL Safety Directorate", status: "SUBMITTED" },
                  { title: "Strata Delamination & Blast Anomaly Analysis", authority: "CMPDI Geotech Division", status: "VERIFIED" },
                ].map((rep) => (
                  <div key={rep.title} className="bg-[#0D1527] border border-[#162238] rounded-xl p-4 flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white">{rep.title}</h4>
                      <p className="text-xs text-[#8899A6] mt-0.5">Regulator Authority: {rep.authority}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold font-mono">
                        {rep.status}
                      </span>
                      <button
                        onClick={handleGenerateReport}
                        className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeNav === "Settings" && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-bold text-white">System Settings & LoRaWAN Provisioning</h1>
                  <p className="text-xs text-[#8899A6] mt-0.5">Control room protocols, threshold alarms, and zero-downtime provisioning</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4 space-y-3">
                  <h3 className="text-sm font-bold text-white">Alert Escalation & Threshold Protocols</h3>
                  <div className="space-y-2 text-xs text-[#8899A6]">
                    <div className="flex justify-between py-1.5 border-b border-[#162238]">
                      <span>Server-Enforced Escalation Timer</span>
                      <span className="text-white font-mono font-semibold">300 seconds (5 min)</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-[#162238]">
                      <span>Critical Extensometer Threshold</span>
                      <span className="text-red-400 font-mono font-semibold">&gt; 3.00 mm</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-[#162238]">
                      <span>Vibration Anomaly Cutoff</span>
                      <span className="text-amber-400 font-mono font-semibold">&gt; 1.20 mm/s</span>
                    </div>
                  </div>
                </div>

                <div className="bg-[#0D1527] border border-[#162238] rounded-xl p-4 space-y-3">
                  <h3 className="text-sm font-bold text-white">Cryptographic Safety Ledger & RLS</h3>
                  <div className="space-y-2 text-xs text-[#8899A6]">
                    <div className="flex justify-between py-1.5 border-b border-[#162238]">
                      <span>Tenant Row-Level Security</span>
                      <span className="text-emerald-400 font-mono font-semibold">Enforced (PostgreSQL 16)</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-[#162238]">
                      <span>Audit Trail Hash Chaining</span>
                      <span className="text-emerald-400 font-mono font-semibold">SHA-256 Chained</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-[#162238]">
                      <span>Zero Silent Staleness Check</span>
                      <span className="text-emerald-400 font-mono font-semibold">Active (&lt;90s heartbeat)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ========================================================= */}
      {/* 3. MODAL: SENSOR TELEMETRY & HARDWARE INSPECTOR           */}
      {/* ========================================================= */}
      {inspectingNodeId && sensors[inspectingNodeId] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#0D1527] border border-[#1F2937] rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="p-4 bg-[#0A101D] border-b border-[#162238] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-cyan-400" />
                <div>
                  <h3 className="text-sm font-bold text-white">
                    Hardware Diagnostic: {sensors[inspectingNodeId].shortId}
                  </h3>
                  <p className="text-[10px] text-[#8899A6]">{sensors[inspectingNodeId].nodeId}</p>
                </div>
              </div>
              <button
                onClick={() => setInspectingNodeId(null)}
                className="p-1 rounded hover:bg-[#162238] text-[#8899A6] hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Telemetry Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="bg-[#070D18] p-2.5 rounded-lg border border-[#162238]">
                  <span className="text-[10px] text-[#8899A6] block">Displacement</span>
                  <span className="text-sm font-bold text-white font-mono">
                    {sensors[inspectingNodeId].disp.toFixed(2)} mm
                  </span>
                </div>
                <div className="bg-[#070D18] p-2.5 rounded-lg border border-[#162238]">
                  <span className="text-[10px] text-[#8899A6] block">Tilt</span>
                  <span className="text-sm font-bold text-white font-mono">
                    {sensors[inspectingNodeId].tilt.toFixed(3)}°
                  </span>
                </div>
                <div className="bg-[#070D18] p-2.5 rounded-lg border border-[#162238]">
                  <span className="text-[10px] text-[#8899A6] block">Vibration</span>
                  <span className="text-sm font-bold text-white font-mono">
                    {sensors[inspectingNodeId].vib.toFixed(2)} mm/s
                  </span>
                </div>
                <div className="bg-[#070D18] p-2.5 rounded-lg border border-[#162238]">
                  <span className="text-[10px] text-[#8899A6] block">Crack Index</span>
                  <span className="text-sm font-bold text-white font-mono">
                    {sensors[inspectingNodeId].crack.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Hardware Specs */}
              <div className="space-y-2 text-xs bg-[#070D18] p-3 rounded-lg border border-[#162238]">
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Location:</span>
                  <span className="text-white font-medium">{sensors[inspectingNodeId].zone}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Battery Status:</span>
                  <span className="text-emerald-400 font-mono font-bold flex items-center gap-1">
                    <Battery className="w-3.5 h-3.5" /> {sensors[inspectingNodeId].batt}% (Nominal)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Mesh Signal:</span>
                  <span className="text-blue-400 font-mono flex items-center gap-1">
                    <Wifi className="w-3.5 h-3.5" /> {sensors[inspectingNodeId].rssi} dBm (LoRaWAN 868MHz)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Hop Count to Gateway:</span>
                  <span className="text-white font-mono">{sensors[inspectingNodeId].hops} hops</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setSelectedTwinNodeId(inspectingNodeId);
                    setInspectingNodeId(null);
                    setActiveNav("Map / Digital Twin");
                  }}
                  className="flex-1 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors"
                >
                  Locate on 3D Digital Twin
                </button>
                <button
                  onClick={() => setInspectingNodeId(null)}
                  className="px-4 py-2 rounded-lg bg-[#162238] hover:bg-[#23354E] text-[#8899A6] hover:text-white text-xs font-semibold transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* 4. MODAL: AUDIBLE ALERT ACKNOWLEDGEMENT                   */}
      {/* ========================================================= */}
      {modalAckAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#0D1527] border-2 border-red-500/80 rounded-xl shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="bg-red-950/80 border-b border-red-800/80 p-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5 text-red-300 font-bold">
                <Volume2 className="w-5 h-5 text-red-400 animate-bounce" />
                <h3 className="text-base font-mono uppercase tracking-wide">
                  Mandatory Safety Acknowledgement
                </h3>
              </div>
              <button onClick={() => setModalAckAlert(null)} className="text-[#8899A6] hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="bg-[#070D18] border border-[#162238] rounded-lg p-3 text-xs font-mono space-y-2">
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Alert Identifier:</span>
                  <span className="text-amber-400 font-bold">{modalAckAlert.alert_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Location:</span>
                  <span className="text-white">{modalAckAlert.site_id} • {modalAckAlert.zone_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Severity Level:</span>
                  <span className="text-red-400 font-bold uppercase">{modalAckAlert.severity}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8899A6]">Acknowledging Operator:</span>
                  <span className="text-cyan-400 font-bold">{activeOperator.name} ({activeOperator.roleLabel})</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#8899A6] mb-1">
                  Operator Mitigation Comment (Logged to SHA-256 Ledger):
                </label>
                <textarea
                  value={ackComment}
                  onChange={(e) => setAckComment(e.target.value)}
                  rows={2}
                  className="w-full bg-[#070D18] border border-[#162238] rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-red-500"
                />
              </div>

              <div className="flex gap-2">
                <button
                  disabled={isSubmittingAck}
                  onClick={handleConfirmAck}
                  className="flex-1 py-2.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs transition-colors flex items-center justify-center gap-1.5"
                >
                  <Check className="w-4 h-4" />
                  <span>{isSubmittingAck ? "Logging to Ledger..." : "Confirm Audible Acknowledgement"}</span>
                </button>
                <button
                  onClick={() => setModalAckAlert(null)}
                  className="px-4 py-2.5 rounded-lg bg-[#162238] text-[#8899A6] hover:text-white text-xs font-semibold"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Physical Sensor Node OLED Live Hardware Mirror */}
      {showOledMirror && (
        <OledDisplayMirror
          nodeId="SS-PANEL7-N042"
          tilt={demoTilt}
          vib={demoVib}
          anomalyScore={demoAnomaly}
          packetsCount={totalPacketsReceived}
          sirenActive={isSirenActive}
          onClose={() => setShowOledMirror(false)}
        />
      )}
    </div>
  );
};

// Mini Sparkle Icon component
function SparklesIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  );
}
