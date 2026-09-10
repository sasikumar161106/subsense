import React, { useState, useEffect } from "react";
import { NodeTelemetryRecord } from "@subsense/shared";
import { LiveSensorTable } from "../components/LiveSensorTable";
import { Layer5MapStub } from "../components/Layer5MapStub";
import { wsService } from "../services/socket";
import { fetchApi } from "../services/api";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";
import { Activity, Wifi, RefreshCw, Layers, BellRing } from "lucide-react";

interface SensorItem {
  node: {
    id: string;
    zone_id: string;
    node_type: string;
    hardware_version?: string;
  };
  latest_telemetry: NodeTelemetryRecord;
}

export const OperatorCockpit: React.FC<{ onTriggerSiren: () => void }> = ({ onTriggerSiren }) => {
  const { currentTenantId, currentSiteId } = useTenant();
  const { currentUser } = useAuth();

  const [sensors, setSensors] = useState<SensorItem[]>([]);
  const [telemetryMap, setTelemetryMap] = useState<Map<string, NodeTelemetryRecord>>(new Map());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("SS-PANEL7-N042");
  const [isWsConnected, setIsWsConnected] = useState<boolean>(true);
  const [lastHeartbeat, setLastHeartbeat] = useState<string>(new Date().toLocaleTimeString());

  // Load initial sensor nodes and telemetry via REST
  const loadSensors = async () => {
    try {
      const res = await fetchApi(`/tenants/${currentTenantId}/sites/${currentSiteId}/sensors`, {
        tenantId: currentTenantId,
        userRole: currentUser.role,
        userId: currentUser.userId,
      });

      if (res.sensors) {
        setSensors(res.sensors);
        const map = new Map<string, NodeTelemetryRecord>();
        res.sensors.forEach((s: any) => {
          map.set(s.node.id, s.latest_telemetry);
        });
        setTelemetryMap(map);
        setLastHeartbeat(new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.warn("REST load error, relying on real-time stream:", err);
    }
  };

  useEffect(() => {
    loadSensors();
    // 5-second polling fallback on constrained links as specified in NFR
    const pollInterval = setInterval(loadSensors, 5000);
    return () => clearInterval(pollInterval);
  }, [currentTenantId, currentSiteId]);

  // Connect to WebSocket stream
  useEffect(() => {
    wsService.connect(currentTenantId, currentSiteId, currentUser.userId);

    const unsubscribe = wsService.subscribeTelemetry((record: NodeTelemetryRecord) => {
      setIsWsConnected(true);
      setLastHeartbeat(new Date().toLocaleTimeString());

      setTelemetryMap((prev) => {
        const next = new Map(prev);
        next.set(record.node_id, record);
        return next;
      });

      setSensors((prev) =>
        prev.map((item) =>
          item.node.id === record.node_id
            ? { ...item, latest_telemetry: record }
            : item
        )
      );
    });

    return () => {
      unsubscribe();
    };
  }, [currentTenantId, currentSiteId, currentUser.userId]);

  return (
    <div className="space-y-6">
      {/* Cockpit Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800 text-xs font-mono">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-emerald-400">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            <span className="font-bold">
              {isWsConnected ? "WebSocket Stream Live (100Hz Mesh Broker)" : "5s Polling Fallback Active"}
            </span>
          </div>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">Last Telemetry Frame: {lastHeartbeat}</span>
          <span className="text-slate-600">|</span>
          <span className="text-cyan-400">Active Panel: {currentSiteId}</span>
        </div>

        <div className="flex items-center gap-2">
          {currentUser.role === "mine_operator" && (
            <button
              id="btn-evacuation-siren"
              onClick={onTriggerSiren}
              className="px-3 py-1.5 rounded-lg bg-red-700 hover:bg-red-600 text-white font-bold flex items-center gap-1.5 border border-red-500 shadow-md shadow-red-950 transition-colors"
            >
              <BellRing className="w-3.5 h-3.5 animate-bounce" />
              Trigger Physical Siren
            </button>
          )}
          <button
            onClick={loadSensors}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
            title="Force refresh"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Grid: Live Sensor Grid & Layer 5 Synced Map */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left Column: Live Sensor Status Table */}
        <div className="xl:col-span-7 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 font-mono uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Live Sensor Mesh Telemetry (Contract 14.1)
            </h2>
            <span className="text-[11px] text-slate-400 font-mono">
              {sensors.length} Nodes Deployed
            </span>
          </div>

          <LiveSensorTable
            sensors={sensors}
            selectedNodeId={selectedNodeId}
            onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
          />
        </div>

        {/* Right Column: Layer 5 Map with Bidirectional Sync */}
        <div className="xl:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 font-mono uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber-400" />
              Layer 5 GIS & Digital Twin Synchronization
            </h2>
            <span className="text-[11px] text-cyan-400 font-mono">
              Selected: {selectedNodeId || "None"}
            </span>
          </div>

          <Layer5MapStub
            selectedNodeId={selectedNodeId}
            onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
            telemetryMap={telemetryMap}
            className="h-[430px]"
          />
        </div>
      </div>
    </div>
  );
};
