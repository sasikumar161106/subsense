import { RiskEvent } from '../models/types';

export const DEFAULT_SPATIAL_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

export type AdjacencyGraph = Record<string, string[]>;

/**
 * Checks if two nodes are adjacent according to the topology graph.
 * If no graph is provided, nodes within the same risk zone are treated as adjacent by default.
 */
export function are_nodes_adjacent(
  nodeA: string,
  nodeB: string,
  graph?: AdjacencyGraph
): boolean {
  if (nodeA === nodeB) return true;
  if (!graph) return true;
  const neighbors = graph[nodeA];
  return neighbors ? neighbors.includes(nodeB) : false;
}

/**
 * Pure function: Determines whether two risk events correlate spatially and temporally
 * within the 5-minute incident window.
 */
export function should_cluster_spatial_events(
  eventA: RiskEvent,
  eventB: RiskEvent,
  windowMs: number = DEFAULT_SPATIAL_WINDOW_MS,
  graph?: AdjacencyGraph
): boolean {
  // Must be same risk zone
  if (eventA.risk_zone_id !== eventB.risk_zone_id) {
    return false;
  }

  // Must be within 5-minute sliding window
  const timeA = eventA.timestamp ? new Date(eventA.timestamp).getTime() : Date.now();
  const timeB = eventB.timestamp ? new Date(eventB.timestamp).getTime() : Date.now();
  if (Math.abs(timeA - timeB) > windowMs) {
    return false;
  }

  // Check node adjacency
  const nodesA = eventA.contributing_nodes || [];
  const nodesB = eventB.contributing_nodes || [];

  if (nodesA.length === 0 || nodesB.length === 0) return true;

  for (const nA of nodesA) {
    for (const nB of nodesB) {
      if (are_nodes_adjacent(nA, nB, graph)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Pure function to cluster a list of RiskEvents into distinct spatial-temporal incidents.
 */
export function cluster_spatial_anomalies(
  events: RiskEvent[],
  windowMs: number = DEFAULT_SPATIAL_WINDOW_MS,
  graph?: AdjacencyGraph
): RiskEvent[][] {
  if (events.length === 0) return [];

  const clusters: RiskEvent[][] = [];

  for (const event of events) {
    let matchedCluster: RiskEvent[] | null = null;

    for (const cluster of clusters) {
      const representative = cluster[0];
      if (should_cluster_spatial_events(representative, event, windowMs, graph)) {
        matchedCluster = cluster;
        break;
      }
    }

    if (matchedCluster) {
      matchedCluster.push(event);
    } else {
      clusters.push([event]);
    }
  }

  return clusters;
}
