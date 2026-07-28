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

export { levelColor, severityLevel };

// A shaded country on the map (a "region" the run flagged as impacted).
export interface MapRegion {
  country: string; // must match world-atlas `geo.properties.name`
  severity: number;
  level: RiskLevel;
}

// Soft country fills — lighter than the node markers so a shaded region reads
// as background context, not another point. Keyed by risk level.
const REGION_TINTS: Record<RiskLevel, string> = {
  critical: "#ffa39e",
  high: "#ffbb96",
  medium: "#ffe58f",
  low: "#b7eb8f",
  minimal: "#e8edf3",
};

export function regionTint(level: RiskLevel): string {
  return REGION_TINTS[level];
}

// Maps a network place (city / hub / region label) to the world-atlas country
// name so we can shade the country polygon. Keys are lowercased. Note:
// world-atlas 110m has no Singapore polygon, so a Singapore-only hit won't
// visibly shade — that's an accepted limitation of the base map resolution.
const PLACE_TO_COUNTRY: Record<string, string> = {
  shanghai: "China",
  china: "China",
  mumbai: "India",
  chennai: "India",
  delhi: "India",
  kolkata: "India",
  bangalore: "India",
  india: "India",
  "ho chi minh": "Vietnam",
  vietnam: "Vietnam",
  rotterdam: "Netherlands",
  netherlands: "Netherlands",
  "los angeles": "United States of America",
  dallas: "United States of America",
  "new york": "United States of America",
  usa: "United States of America",
  "north america": "United States of America",
  dubai: "United Arab Emirates",
  colombo: "Sri Lanka",
  singapore: "Singapore",
};

function countryForPlace(label?: string | null, region?: string | null): string | null {
  for (const candidate of [region, label]) {
    if (!candidate) continue;
    const key = candidate.trim().toLowerCase();
    if (PLACE_TO_COUNTRY[key]) return PLACE_TO_COUNTRY[key];
    for (const [place, country] of Object.entries(PLACE_TO_COUNTRY)) {
      if (key.includes(place)) return country;
    }
  }
  return null;
}

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
): { nodes: MapNode[]; arcs: MapArc[]; regions: MapRegion[] } {
  const nodeMap = new Map<string, MapNode>();
  const arcs: MapArc[] = [];
  const maxClassification =
    state?.classifications?.reduce((acc, item) => Math.max(acc, item.severity), 0) ?? 0;
  const defaultSeverity = state ? Math.max(maxClassification, 2) : 1;

  const impactedLanes = new Set<string>();
  const impactedEntities = new Set<string>();

  // Countries the run actually flagged as impacted, keyed by country name and
  // holding the highest severity seen. Only genuinely-impacted places are added
  // (severity >= 2), so unaffected countries stay in the muted base fill.
  const regionMap = new Map<string, MapRegion>();
  const addRegion = (country: string | null, severity: number) => {
    if (!country || severity < 2) return;
    const next = Math.max(regionMap.get(country)?.severity ?? 0, severity);
    regionMap.set(country, { country, severity: next, level: severityLevel(next) });
  };

  for (const impact of state?.impacts ?? []) {
    for (const lane of impact.affected_lanes) impactedLanes.add(lane);
    for (const supplier of impact.affected_suppliers) impactedEntities.add(supplier);
    for (const facility of impact.affected_facilities) impactedEntities.add(facility);
  }

  // Shade both endpoint countries of every impacted lane. We walk the impact's
  // own lane names (not just network topology) so a flagged lane that isn't in
  // the seed network — e.g. a hub lane the impact agent added — still lights its
  // regions.
  for (const laneName of impactedLanes) {
    const [fromLabel, toLabel] = parseLaneEndpoints(laneName);
    addRegion(countryForPlace(fromLabel), defaultSeverity);
    addRegion(countryForPlace(toLabel), defaultSeverity);
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
    addRegion(countryForPlace(risk.hub_port, risk.region), risk.aggregate_severity);
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
    if (impacted) addRegion(countryForPlace(supplier.name, supplier.region), defaultSeverity);
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
    if (impacted) addRegion(countryForPlace(facility.name, facility.region), defaultSeverity);
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

  return { nodes: [...nodeMap.values()], arcs, regions: [...regionMap.values()] };
}
