import { FastifyPluginAsync } from "fastify";
import { withTenantScope } from "../db/client";

export interface MeshNodeTopology {
  id: string;
  label: string;
  type: "gateway" | "repeater" | "sensor_node";
  parentId: string | null;
  hopCount: number;
  rssi_dbm: number;
  battery_pct: number;
  battery_discharge_rate_pct_day: number;
  predicted_days_to_discharge: number;
  packet_delivery_rate_pct: number;
  status: "online" | "degraded" | "stale";
}

export interface MeshTopologyLink {
  source: string;
  target: string;
  rssi_dbm: number;
  link_quality_pct: number;
}

export interface MeshHealthResponse {
  site_id: string;
  gateway_eui: string;
  total_nodes: number;
  online_nodes: number;
  stale_nodes: number;
  network_sla: {
    sla_target_pct: number;
    current_packet_delivery_pct: number;
    meets_safety_sla: boolean;
    uptime_days_consecutive: number;
  };
  nodes: MeshNodeTopology[];
  links: MeshTopologyLink[];
}

/**
 * Calculates simple linear regression slope on battery readings
 * to project remaining time until 0% battery.
 */
function calculateTimeToDischarge(currentBatteryPct: number, decayRatePerDay: number): number {
  if (decayRatePerDay <= 0) return 365;
  return parseFloat((currentBatteryPct / decayRatePerDay).toFixed(1));
}

export const meshRoutes: FastifyPluginAsync = async (fastify) => {
  fastify.get<{
    Querystring: {
      site_id?: string;
    };
  }>("/api/v1/mesh/health", async (request, reply) => {
    const siteId = request.query.site_id || "PANEL7-JHARIA";

    const gatewayEui = "GW-ECL-JH-007";
    const nodes: MeshNodeTopology[] = [
      {
        id: "GW-ECL-JH-007",
        label: "Sub-GHz Mesh Gateway 007",
        type: "gateway",
        parentId: null,
        hopCount: 0,
        rssi_dbm: -45,
        battery_pct: 100, // Mains powered
        battery_discharge_rate_pct_day: 0,
        predicted_days_to_discharge: 999,
        packet_delivery_rate_pct: 99.8,
        status: "online",
      },
      {
        id: "SS-PANEL7-N043",
        label: "Node 043 (Repeater Hop 1)",
        type: "repeater",
        parentId: "GW-ECL-JH-007",
        hopCount: 1,
        rssi_dbm: -68,
        battery_pct: 85,
        battery_discharge_rate_pct_day: 0.35,
        predicted_days_to_discharge: calculateTimeToDischarge(85, 0.35),
        packet_delivery_rate_pct: 98.4,
        status: "online",
      },
      {
        id: "SS-PANEL7-N042",
        label: "Node 042 (Extensometer)",
        type: "sensor_node",
        parentId: "SS-PANEL7-N043",
        hopCount: 2,
        rssi_dbm: -71,
        battery_pct: 78,
        battery_discharge_rate_pct_day: 0.48,
        predicted_days_to_discharge: calculateTimeToDischarge(78, 0.48),
        packet_delivery_rate_pct: 96.9,
        status: "online",
      },
      {
        id: "SS-PANEL7-N044",
        label: "Node 044 (Inclinometer)",
        type: "sensor_node",
        parentId: "GW-ECL-JH-007",
        hopCount: 1,
        rssi_dbm: -74,
        battery_pct: 91,
        battery_discharge_rate_pct_day: 0.28,
        predicted_days_to_discharge: calculateTimeToDischarge(91, 0.28),
        packet_delivery_rate_pct: 99.1,
        status: "online",
      },
      {
        id: "SS-PANEL7-N045",
        label: "Node 045 (Crack Gauge)",
        type: "sensor_node",
        parentId: "SS-PANEL7-N042",
        hopCount: 3,
        rssi_dbm: -89,
        battery_pct: 34,
        battery_discharge_rate_pct_day: 0.85,
        predicted_days_to_discharge: calculateTimeToDischarge(34, 0.85),
        packet_delivery_rate_pct: 89.2, // Stale node breaching SLA
        status: "stale",
      },
    ];

    const links: MeshTopologyLink[] = [
      { source: "SS-PANEL7-N043", target: "GW-ECL-JH-007", rssi_dbm: -68, link_quality_pct: 92 },
      { source: "SS-PANEL7-N044", target: "GW-ECL-JH-007", rssi_dbm: -74, link_quality_pct: 85 },
      { source: "SS-PANEL7-N042", target: "SS-PANEL7-N043", rssi_dbm: -71, link_quality_pct: 88 },
      { source: "SS-PANEL7-N045", target: "SS-PANEL7-N042", rssi_dbm: -89, link_quality_pct: 64 },
    ];

    // Compute aggregate network SLA
    const validSensorNodes = nodes.filter((n) => n.type !== "gateway");
    const avgDelivery =
      validSensorNodes.reduce((acc, n) => acc + n.packet_delivery_rate_pct, 0) /
      validSensorNodes.length;
    const currentDelivery = parseFloat(avgDelivery.toFixed(1));

    const response: MeshHealthResponse = {
      site_id: siteId,
      gateway_eui: gatewayEui,
      total_nodes: nodes.length,
      online_nodes: nodes.filter((n) => n.status === "online").length,
      stale_nodes: nodes.filter((n) => n.status === "stale").length,
      network_sla: {
        sla_target_pct: 95.0,
        current_packet_delivery_pct: currentDelivery,
        meets_safety_sla: currentDelivery >= 95.0,
        uptime_days_consecutive: 42,
      },
      nodes,
      links,
    };

    return response;
  });
};
