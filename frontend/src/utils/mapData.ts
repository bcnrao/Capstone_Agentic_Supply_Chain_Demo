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

  // Per-node severity, not one number for the whole run.
  //
  // Previously every impacted node, lane and region was painted with a single
  // scalar (the max severity across all classifications), so the map showed the
  // same colour on every port regardless of what was actually hit. Here each
  // impact carries the severity of the classification that produced it, and an
  // entity keeps the worst severity of the impacts that touched it.
  const severityBySignal = new Map<string, number>(
    (state?.classifications ?? []).map((item) => [item.signal_id, item.severity]),
  );

  const laneSeverity = new Map<string, number>();
  const entitySeverity = new Map<string, number>();
  const bump = (map: Map<string, number>, key: string, value: number) => {
    map.set(key, Math.max(map.get(key) ?? 0, value));
  };

  for (const impact of state?.impacts ?? []) {
    // Fall back to 2 (the "on the map but not alarming" floor) when an impact
    // has no matching classification, rather than to the run-wide maximum.
    const severity = severityBySignal.get(impact.signal_id) ?? 2;
    for (const lane of impact.affected_lanes ?? []) bump(laneSeverity, lane, severity);
    for (const supplier of impact.affected_suppliers ?? []) bump(entitySeverity, supplier, severity);
    for (const facility of impact.affected_facilities ?? []) bump(entitySeverity, facility, severity);
  }

  // Unimpacted network nodes still render, but muted — they are context, not risk.
  const BASELINE = 1.5;

  // Countries the run flagged as impacted, keyed by country name and holding the
  // highest severity seen. Only genuinely-impacted places are added (severity
  // >= 2), so unaffected countries stay in the muted base fill.
  const regionMap = new Map<string, MapRegion>();
  const addRegion = (country: string | null, severity: number) => {
    if (!country || severity < 2) return;
    const next = Math.max(regionMap.get(country)?.severity ?? 0, severity);
    regionMap.set(country, { country, severity: next, level: severityLevel(next) });
  };

  // Shade both endpoint countries of every impacted lane, each at that lane's own
  // severity. We walk the impacts' lane names (not just network topology) so a
  // flagged lane absent from the seed network still lights its regions.
  for (const [laneName, severity] of laneSeverity) {
    const [fromLabel, toLabel] = parseLaneEndpoints(laneName);
    addRegion(countryForPlace(fromLabel), severity);
    addRegion(countryForPlace(toLabel), severity);
  }

  // Ports that already have a weather marker, so the lane loop below does not
  // stack a second "hub" dot on the same coordinates with a different severity.
  const weatherLabels = new Set<string>();

  for (const risk of state?.weather_risks ?? []) {
    const coords = resolveCoordinates(
      risk.hub_port ?? risk.region ?? "hub",
      risk.region,
      risk.lat,
      risk.lon,
    );
    if (!coords) continue;
    const label = risk.hub_port ?? risk.region ?? "Weather hub";
    weatherLabels.add(label);
    if (risk.region) weatherLabels.add(risk.region);
    upsertNode(
      nodeMap,
      `weather-${risk.signal_id}-${risk.hub_port ?? risk.region}`,
      label,
      coords,
      risk.aggregate_severity,
      "weather",
    );
    addRegion(countryForPlace(risk.hub_port, risk.region), risk.aggregate_severity);
  }

  for (const supplier of network?.suppliers ?? []) {
    const severity = entitySeverity.get(supplier.name);
    const coords = resolveCoordinates(supplier.name, supplier.region);
    if (!coords) continue;
    upsertNode(
      nodeMap,
      `supplier-${supplier.name}`,
      supplier.name,
      coords,
      severity ?? BASELINE,
      "supplier",
    );
    if (severity) addRegion(countryForPlace(supplier.name, supplier.region), severity);
  }

  for (const facility of network?.facilities ?? []) {
    const severity = entitySeverity.get(facility.name);
    const coords = resolveCoordinates(facility.name, facility.region);
    if (!coords) continue;
    upsertNode(
      nodeMap,
      `facility-${facility.name}`,
      facility.name,
      coords,
      severity ?? BASELINE,
      "facility",
    );
    if (severity) addRegion(countryForPlace(facility.name, facility.region), severity);
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

    // Only lanes the impact agent actually flagged are drawn hot. The previous
    // test was `impactedLanes.has(name) || state?.impacts?.length`, and that
    // second operand is a NUMBER — truthy whenever the run produced any impact
    // at all — so every lane in the network lit up on every run.
    const severity = laneSeverity.get(lane.name);
    arcs.push({
      id: lane.name,
      from,
      to,
      severity: severity ?? 1,
      label: lane.name,
    });

    if (!nodeMap.has(`hub-${fromLabel}`) && !weatherLabels.has(fromLabel)) {
      upsertNode(nodeMap, `hub-${fromLabel}`, fromLabel, from, severity ?? 1, "hub");
    }
    if (!nodeMap.has(`hub-${toLabel}`) && !weatherLabels.has(toLabel)) {
      upsertNode(nodeMap, `hub-${toLabel}`, toLabel, to, severity ?? 1, "hub");
    }
  }

  if (nodeMap.size === 0) {
    for (const [hub, coords] of Object.entries(HUB_CENTROIDS)) {
      upsertNode(nodeMap, `fallback-${hub}`, hub, coords, BASELINE, "hub");
    }
  }

  return { nodes: [...nodeMap.values()], arcs, regions: [...regionMap.values()] };
}
