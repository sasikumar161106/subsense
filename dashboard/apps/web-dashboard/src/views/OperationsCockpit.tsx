import React, { useState, useEffect } from "react";
import { NodeTelemetryRecord } from "@subsense/shared";
import { LiveSensorTable } from "../components/LiveSensorTable";
import { Layer5MapStub } from "../components/Layer5MapStub";
import { SensorSummaryKpis } from "../components/SensorSummaryKpis";
import { wsService } from "../services/socket";
import { fetchApi } from "../services/api";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";

export const OperationsCockpit: React.FC = () => {
  const { currentTenantId, currentSiteId } = useTenant();
  const { currentUser } = useAuth();

  const [sensors, setSensors] = useState<any[]>([]);
  const [telemetryMap, setTelemetryMap] = useState<Map<string, NodeTelemetryRecord>>(new Map());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("SS-PANEL7-N042");

  // Load sensors via REST
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
      }
    } catch (err) {
      console.warn("REST load error, using stream:", err);
    }
  };

  useEffect(() => {
    loadSensors();
    const interval = setInterval(loadSensors, 5000);
    return () => clearInterval(interval);
  }, [currentTenantId, currentSiteId]);

  // Connect to WebSocket stream
  useEffect(() => {
    wsService.connect(currentTenantId, currentSiteId, currentUser.userId);

    const unsub = wsService.subscribeTelemetry((record: NodeTelemetryRecord) => {
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

    return unsub;
  }, [currentTenantId, currentSiteId, currentUser.userId]);

  const totalCount = sensors.length;
  const offlineCount = sensors.filter(
    (s) => s.latest_telemetry?.is_stale || s.node.status !== "online"
  ).length;
  const atRiskCount = sensors.filter(
    (s) => !s.latest_telemetry?.is_stale && (s.latest_telemetry?.anomaly_score || 0) > 0.35
  ).length;
  const healthyCount = Math.max(0, totalCount - offlineCount - atRiskCount);

  return (
    <div className="space-y-4">
      {/* Two-Column Industrial Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
        {/* Left Column (58-62% on Desktop): Live Sensor Telemetry Card */}
        <div className="lg:col-span-7 xl:col-span-7 flex flex-col space-y-4">
          <LiveSensorTable
            sensors={sensors}
            selectedNodeId={selectedNodeId}
            onSelectNode={(id) => setSelectedNodeId(id)}
            className="flex-1"
          />

          {/* Under Sensor Table: 4 Compact KPI Cards */}
          <SensorSummaryKpis
            totalNodes={totalCount}
            healthyNodes={healthyCount}
            atRiskNodes={atRiskCount}
            offlineNodes={offlineCount}
          />
        </div>

        {/* Right Column (38-42% on Desktop): GIS & Digital Twin Card */}
        <div className="lg:col-span-5 xl:col-span-5 flex flex-col">
          <Layer5MapStub
            selectedNodeId={selectedNodeId}
            onSelectNode={(id) => setSelectedNodeId(id)}
            telemetryMap={telemetryMap}
            className="flex-1 min-h-[460px]"
          />
        </div>
      </div>
    </div>
  );
};
