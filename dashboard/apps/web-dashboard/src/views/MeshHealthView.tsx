import React, { useState, useEffect } from "react";
import { fetchApi } from "../services/api";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../contexts/AuthContext";
import {
  Network,
  Radio,
  Battery,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  TrendingDown,
} from "lucide-react";

export const MeshHealthView: React.FC = () => {
  const { currentTenantId, currentSiteId } = useTenant();
  const { currentUser } = useAuth();

  const [meshData, setMeshData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadMesh = async () => {
      setIsLoading(true);
      try {
        const res = await fetchApi(`/mesh/health?site_id=${currentSiteId}`, {
          tenantId: currentTenantId,
          userRole: currentUser.role,
          userId: currentUser.userId,
        });
        setMeshData(res);
      } catch (err) {
        console.error("Failed to load mesh health:", err);
      } finally {
        setIsLoading(false);
      }
    };
    loadMesh();
  }, [currentTenantId, currentSiteId]);

  if (isLoading || !meshData) {
    return (
      <div className="p-8 text-center font-mono text-slate-400">
        Loading mesh radio topology and battery regression metrics...
      </div>
    );
  }

  const { network_sla, nodes, links } = meshData;

  return (
    <div className="space-y-6">
      {/* SLA and Infrastructure KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Packet Delivery SLA */}
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl font-mono">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Packet Delivery SLA</span>
            <span className={network_sla.meets_safety_sla ? "text-emerald-400" : "text-amber-400"}>
              Target: &gt;{network_sla.sla_target_pct}%
            </span>
          </div>
          <div className="text-2xl font-bold text-white flex items-baseline gap-2">
            {network_sla.current_packet_delivery_pct}%
            {network_sla.meets_safety_sla ? (
              <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> SLA Compliant
              </span>
            ) : (
              <span className="text-xs text-amber-400 font-semibold flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> SLA Breached
              </span>
            )}
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className={`h-full rounded-full ${
                network_sla.meets_safety_sla ? "bg-emerald-500" : "bg-amber-500"
              }`}
              style={{ width: `${Math.min(100, network_sla.current_packet_delivery_pct)}%` }}
            />
          </div>
        </div>

        {/* KPI 2: Total Nodes */}
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl font-mono">
          <div className="text-xs text-slate-400 mb-1">Total Mesh Elements</div>
          <div className="text-2xl font-bold text-white">{meshData.total_nodes}</div>
          <div className="text-[11px] text-slate-400 mt-1">
            1 Gateway • {meshData.online_nodes} Online • {meshData.stale_nodes} Stale
          </div>
        </div>

        {/* KPI 3: Consecutive Network Uptime */}
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl font-mono">
          <div className="text-xs text-slate-400 mb-1">Continuous Network Uptime</div>
          <div className="text-2xl font-bold text-cyan-400">
            {network_sla.uptime_days_consecutive} days
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Zero gateway restarts since provisioning
          </div>
        </div>

        {/* KPI 4: Gateway EUI */}
        <div className="bg-slate-900/80 border border-slate-800 p-4 rounded-xl font-mono">
          <div className="text-xs text-slate-400 mb-1">Hardware Gateway EUI</div>
          <div className="text-sm font-bold text-amber-400 truncate">{meshData.gateway_eui}</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Protocol: Sub-GHz 868MHz Mesh Broker
          </div>
        </div>
      </div>

      {/* Mesh Radio Topology & Battery Discharge Regression Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-sm font-bold text-slate-200 font-mono uppercase tracking-wide flex items-center gap-2">
            <Network className="w-4 h-4 text-cyan-400" />
            Radio Topology, Hop Count &amp; Battery Discharge Linear Regression
          </h3>
          <span className="text-xs text-slate-400 font-mono hidden sm:inline">
            Predictive maintenance: Time-to-Discharge projection based on daily consumption slope
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                <th className="py-2.5 px-3">Node Label</th>
                <th className="py-2.5 px-3">Role &amp; Parent</th>
                <th className="py-2.5 px-3 text-center">Hops</th>
                <th className="py-2.5 px-3 text-right">RSSI</th>
                <th className="py-2.5 px-3 text-right">Battery %</th>
                <th className="py-2.5 px-3 text-right">Decay / Day</th>
                <th className="py-2.5 px-3 text-right">Time-to-Discharge</th>
                <th className="py-2.5 px-3 text-right">Packet Delivery</th>
                <th className="py-2.5 px-3 text-center">Health Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {nodes.map((n: any) => {
                const isDischargeRisk = n.predicted_days_to_discharge < 30;

                return (
                  <tr key={n.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-bold text-slate-200">{n.label}</div>
                      <div className="text-[10px] text-slate-400">{n.id}</div>
                    </td>

                    <td className="py-3 px-3">
                      <div className="text-slate-300 capitalize">{n.type.replace(/_/g, " ")}</div>
                      <div className="text-[10px] text-slate-500">
                        {n.parentId ? `via ${n.parentId}` : "Root Gateway"}
                      </div>
                    </td>

                    <td className="py-3 px-3 text-center">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-bold">
                        {n.hopCount}
                      </span>
                    </td>

                    <td className="py-3 px-3 text-right font-medium">
                      <span className={n.rssi_dbm < -85 ? "text-red-400" : n.rssi_dbm < -75 ? "text-amber-400" : "text-emerald-400"}>
                        {n.rssi_dbm} dBm
                      </span>
                    </td>

                    <td className="py-3 px-3 text-right font-medium">
                      <div className="flex items-center justify-end gap-1.5">
                        <Battery className={`w-3.5 h-3.5 ${n.battery_pct < 40 ? "text-amber-400" : "text-emerald-400"}`} />
                        <span>{n.battery_pct}%</span>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-right text-slate-400">
                      {n.battery_discharge_rate_pct_day > 0 ? `-${n.battery_discharge_rate_pct_day}%/day` : "Mains"}
                    </td>

                    <td className="py-3 px-3 text-right font-bold">
                      <span
                        className={
                          n.predicted_days_to_discharge < 14
                            ? "text-red-400 animate-pulse"
                            : n.predicted_days_to_discharge < 45
                            ? "text-amber-400"
                            : "text-slate-200"
                        }
                      >
                        {n.predicted_days_to_discharge > 365 ? ">1 Year" : `${n.predicted_days_to_discharge} days`}
                      </span>
                    </td>

                    <td className="py-3 px-3 text-right font-medium">
                      <span className={n.packet_delivery_rate_pct >= 95 ? "text-emerald-400" : "text-amber-400"}>
                        {n.packet_delivery_rate_pct}%
                      </span>
                    </td>

                    <td className="py-3 px-3 text-center">
                      <span
                        className={`inline-block text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                          n.status === "online"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : "bg-amber-950 text-amber-300 border border-amber-800"
                        }`}
                      >
                        {n.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
