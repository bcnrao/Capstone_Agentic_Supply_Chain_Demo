import type { PipelineState, SupplyNetwork } from "../types/state";
import {
  HUB_CENTROIDS,
  parseLaneEndpoints,
  resolveCoordinates,
  type LonLat,
} from "../data/regionCentroids";

export type RiskLevel = "critical" | "high" | "medium" | "low" | "minimal";

export interface MapNode {
  id: string;
  label: string;
  coordinates: LonLat;
  severity: number;
  level: RiskLevel;
  kind: string;
}

export interface MapArc {
  id: string;
  from: LonLat;
  to: LonLat;
  severity: number;
  label: string;
}

function severityLevel(severity: number): RiskLevel {
  if (severity >= 8) return "critical";
  if (severity >= 6) return "high";
  if (severity >= 4) return "medium";
  if (severity >= 2) return "low";
  return "minimal";
}

function levelColor(level: RiskLevel): string {
  switch (level) {
    case "critical":
      return "#cf1322";
    case "high":
      return "#fa541c";
    case "medium":
      return "#faad14";
    case "low":
      return "#52c41a";
    default:
      return "#91caff";
  }
}

export { levelColor };

function upsertNode(
  nodes: Map<string, MapNode>,
  id: string,
  label: string,
  coordinates: LonLat,
  severity: number,
  kind: string,
) {
  const existing = nodes.get(id);
  const nextSeverity = Math.max(existing?.severity ?? 0, severity);
  nodes.set(id, {
    id,
    label,
    coordinates,
    severity: nextSeverity,
    level: severityLevel(nextSeverity),
    kind,
  });
}

export function buildMapData(
  state: PipelineState | undefined,
  network: SupplyNetwork | undefined,
): { nodes: MapNode[]; arcs: MapArc[] } {
  const nodeMap = new Map<string, MapNode>();
  const arcs: MapArc[] = [];
  const maxClassification =
    state?.classifications?.reduce((acc, item) => Math.max(acc, item.severity), 0) ?? 0;
  const defaultSeverity = state ? Math.max(maxClassification, 2) : 1;

  const impactedLanes = new Set<string>();
  const impactedEntities = new Set<string>();

  for (const impact of state?.impacts ?? []) {
    for (const lane of impact.affected_lanes) impactedLanes.add(lane);
    for (const supplier of impact.affected_suppliers) impactedEntities.add(supplier);
    for (const facility of impact.affected_facilities) impactedEntities.add(facility);
  }

  for (const risk of state?.weather_risks ?? []) {
    const coords = resolveCoordinates(
      risk.hub_port ?? risk.region ?? "hub",
      risk.region,
      risk.lat,
      risk.lon,
    );
    if (!coords) continue;
    upsertNode(
      nodeMap,
      `weather-${risk.signal_id}-${risk.hub_port ?? risk.region}`,
      risk.hub_port ?? risk.region ?? "Weather hub",
      coords,
      risk.aggregate_severity,
      "weather",
    );
  }

  for (const supplier of network?.suppliers ?? []) {
    const impacted = impactedEntities.has(supplier.name);
    const coords = resolveCoordinates(supplier.name, supplier.region);
    if (!coords) continue;
    upsertNode(
      nodeMap,
      `supplier-${supplier.name}`,
      supplier.name,
      coords,
      impacted ? defaultSeverity : 1.5,
      "supplier",
    );
  }

  for (const facility of network?.facilities ?? []) {
    const impacted = impactedEntities.has(facility.name);
    const coords = resolveCoordinates(facility.name, facility.region);
    if (!coords) continue;
    upsertNode(
      nodeMap,
      `facility-${facility.name}`,
      facility.name,
      coords,
      impacted ? defaultSeverity : 1.5,
      "facility",
    );
  }

  const lanes = network?.lanes ?? [];
  for (const lane of lanes) {
    const [fromLabel, toLabel] = parseLaneEndpoints(lane.name);
    const from =
      HUB_CENTROIDS[fromLabel] ??
      resolveCoordinates(fromLabel) ??
      resolveCoordinates(fromLabel, fromLabel);
    const to =
      HUB_CENTROIDS[toLabel] ??
      resolveCoordinates(toLabel) ??
      resolveCoordinates(toLabel, toLabel);
    if (!from || !to) continue;

    const impacted = impactedLanes.has(lane.name) || state?.impacts?.length;
    arcs.push({
      id: lane.name,
      from,
      to,
      severity: impacted ? defaultSeverity : 1,
      label: lane.name,
    });

    if (!nodeMap.has(`hub-${fromLabel}`)) {
      upsertNode(nodeMap, `hub-${fromLabel}`, fromLabel, from, impacted ? defaultSeverity : 1, "hub");
    }
    if (!nodeMap.has(`hub-${toLabel}`)) {
      upsertNode(nodeMap, `hub-${toLabel}`, toLabel, to, impacted ? defaultSeverity : 1, "hub");
    }
  }

  if (nodeMap.size === 0) {
    for (const [hub, coords] of Object.entries(HUB_CENTROIDS)) {
      upsertNode(nodeMap, `fallback-${hub}`, hub, coords, 1.5, "hub");
    }
  }

  return { nodes: [...nodeMap.values()], arcs };
}
