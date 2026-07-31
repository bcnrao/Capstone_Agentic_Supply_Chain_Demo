import type { ImpactMap, PipelineState, SupplyNetwork } from "../types/state";
import { severityLevel, type RiskLevel } from "./mapData";

// One filled square in the executive heatmap: the worst severity seen for a
// given product category in a given region, plus how many signals fed it.
export interface HeatCell {
  category: string;
  region: string;
  severity: number;
  level: RiskLevel;
  signals: number;
}

export interface HeatmapData {
  categories: string[];
  regions: string[];
  cells: Record<string, HeatCell>;
  maxSeverity: number;
}

export function cellKey(category: string, region: string): string {
  return `${category}||${region}`;
}

// Continuous green→gold→orange→red risk ramp keyed on a 0–10 severity score,
// so heatmap cells read as a smooth gradient rather than five discrete bands.
const HEAT_RAMP: Array<[number, [number, number, number]]> = [
  [0, [232, 245, 233]], // pale green — negligible
  [2, [82, 196, 26]], // green
  [4, [250, 173, 20]], // gold
  [6, [250, 84, 28]], // orange
  [8, [207, 19, 34]], // red
  [10, [168, 7, 26]], // deep red — extreme
];

// CSS gradient mirroring HEAT_RAMP, for the legend bar.
export const HEAT_GRADIENT_CSS =
  "linear-gradient(90deg, rgb(232,245,233) 0%, rgb(82,196,26) 20%, " +
  "rgb(250,173,20) 40%, rgb(250,84,28) 60%, rgb(207,19,34) 80%, rgb(168,7,26) 100%)";

export function heatColor(severity: number): string {
  const s = Math.max(0, Math.min(10, severity));
  for (let i = 0; i < HEAT_RAMP.length - 1; i += 1) {
    const [s0, c0] = HEAT_RAMP[i];
    const [s1, c1] = HEAT_RAMP[i + 1];
    if (s <= s1) {
      const t = s1 === s0 ? 0 : (s - s0) / (s1 - s0);
      const r = Math.round(c0[0] + (c1[0] - c0[0]) * t);
      const g = Math.round(c0[1] + (c1[1] - c0[1]) * t);
      const b = Math.round(c0[2] + (c1[2] - c0[2]) * t);
      return `rgb(${r}, ${g}, ${b})`;
    }
  }
  const [r, g, b] = HEAT_RAMP[HEAT_RAMP.length - 1][1];
  return `rgb(${r}, ${g}, ${b})`;
}

const UNASSIGNED = "Unassigned";

// Derive a Product-Category × Region severity grid from a completed pipeline run.
// Product categories come from `impacts`; region and severity are joined back to
// each impact's originating signal_id via the other stages of the same state.
export function buildHeatmap(
  state: PipelineState | undefined,
  network?: SupplyNetwork,
): HeatmapData {
  const empty: HeatmapData = {
    categories: [],
    regions: [],
    cells: {},
    maxSeverity: 0,
  };
  if (!state) return empty;

  // Network entity name -> its region, so an impact can name its own region
  // even when the originating headline carried no place. This is also the more
  // meaningful reading of the panel: the axis is "which of OUR regions is at
  // risk", not "where was the story filed".
  const regionOfEntity = new Map<string, string>();
  for (const entity of [...(network?.suppliers ?? []), ...(network?.facilities ?? [])]) {
    if (entity.region) regionOfEntity.set(entity.name, entity.region);
  }

  // signal_id -> region. The signal's own location wins: it comes from the
  // connector or from normalize.infer_region(), both of which emit the same
  // city-level vocabulary as the network KB. The LLM's extracted_region is free
  // text and often country-level ("India"), which would open a duplicate column
  // beside the city ones — so it is only a fallback.
  const regionOf = new Map<string, string>();
  for (const signal of state.new_signals ?? []) {
    if (signal.location?.region) regionOf.set(signal.signal_id, signal.location.region);
  }
  for (const ea of state.event_analyses ?? []) {
    if (!regionOf.has(ea.signal_id) && ea.extracted_region) {
      regionOf.set(ea.signal_id, ea.extracted_region);
    }
  }
  for (const risk of state.weather_risks ?? []) {
    if (!regionOf.has(risk.signal_id)) {
      const region = risk.region ?? risk.hub_port;
      if (region) regionOf.set(risk.signal_id, region);
    }
  }

  // signal_id -> worst severity across classification / weather / raw signal.
  const severityOf = new Map<string, number>();
  const bump = (id: string, value: number | null | undefined) => {
    if (value == null) return;
    severityOf.set(id, Math.max(severityOf.get(id) ?? 0, value));
  };
  for (const c of state.classifications ?? []) bump(c.signal_id, c.severity);
  for (const risk of state.weather_risks ?? []) bump(risk.signal_id, risk.aggregate_severity);
  for (const signal of state.new_signals ?? []) bump(signal.signal_id, signal.severity);

  const categories = new Set<string>();
  const regions = new Set<string>();
  const cells: Record<string, HeatCell> = {};
  let maxSeverity = 0;

  // Region of the network entities this impact actually touched. Used when the
  // signal itself has no place attached.
  const regionFromImpact = (impact: ImpactMap): string | undefined => {
    for (const name of [...(impact.affected_suppliers ?? []), ...(impact.affected_facilities ?? [])]) {
      const region = regionOfEntity.get(name);
      if (region) return region;
    }
    for (const lane of impact.affected_lanes ?? []) {
      for (const part of lane.split("-")) {
        const region = regionOfEntity.get(part.trim());
        if (region) return region;
        if ([...regionOfEntity.values()].includes(part.trim())) return part.trim();
      }
    }
    return undefined;
  };

  for (const impact of state.impacts ?? []) {
    const region = regionOf.get(impact.signal_id) ?? regionFromImpact(impact) ?? UNASSIGNED;
    const severity = severityOf.get(impact.signal_id) ?? 0;
    for (const raw of impact.product_categories ?? []) {
      const category = raw.trim();
      if (!category) continue;
      categories.add(category);
      regions.add(region);
      const key = cellKey(category, region);
      const existing = cells[key];
      const nextSeverity = Math.max(existing?.severity ?? 0, severity);
      cells[key] = {
        category,
        region,
        severity: nextSeverity,
        level: severityLevel(nextSeverity),
        signals: (existing?.signals ?? 0) + 1,
      };
      maxSeverity = Math.max(maxSeverity, nextSeverity);
    }
  }

  // Regions alphabetical, but keep the catch-all bucket last.
  const sortedRegions = [...regions].sort((a, b) => {
    if (a === UNASSIGNED) return 1;
    if (b === UNASSIGNED) return -1;
    return a.localeCompare(b);
  });

  return {
    categories: [...categories].sort((a, b) => a.localeCompare(b)),
    regions: sortedRegions,
    cells,
    maxSeverity,
  };
}
