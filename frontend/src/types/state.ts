// TypeScript mirror of the backend GraphState / serialize_state contract
// (backend/src/agentic_scd/graph/state.py + agents/schema.py). Fields are
// optional because the pipeline populates them stage by stage.

export interface Location {
  region?: string | null;
  lat?: number | null;
  lon?: number | null;
  hub_port?: string | null;
}

export interface DisruptionSignal {
  signal_id: string;
  source: string;
  source_type: string;
  source_reliability?: number | null;
  fetched_at: string;
  event_time?: string | null;
  title: string;
  raw_text?: string;
  url?: string | null;
  location?: Location | null;
  severity_hint?: string | null;
  category?: string | null;
  severity?: number | null;
  affected_entities?: string[] | null;
}

export interface EventAnalysis {
  signal_id: string;
  event_type: string;
  entities: string[];
  extracted_region?: string | null;
  severity_hint?: string | null;
  summary: string;
}

export interface Classification {
  signal_id: string;
  category: string;
  risk_score: number;
  severity: number;
  confidence: number;
  risk_level: string;
  route: string;
  rationale: string;
}

export interface ImpactMap {
  signal_id: string;
  affected_entities: string[];
  affected_suppliers: string[];
  affected_lanes: string[];
  affected_facilities: string[];
  product_categories: string[];
  retrieved_context: string[];
  reasoning: string;
}

export interface Forecast {
  dates: string[];
  baseline: number[];
  adjusted: number[];
  demand_deviation_pct: number;
  inventory_days_left: number;
  predicted_delay_days: number;
  mape_estimate: number;
  note: string;
  model_name: string;
  freight_pressure_pct: number;
}

export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
}

// Resolved knob values a simulation ran with — anchors the what-if sliders.
export interface SimParams {
  risk: number;
  supplier_reliability: number;
  lead_time_mean: number;
  defect_rate: number;
  daily_demand: number;
  opening_inventory: number;
  iterations: number;
}

// What-if knob overrides. Omitted / null fields keep the scenario's derived value.
export interface SimOverrides {
  risk?: number | null;
  lead_time_mean?: number | null;
  port_delay_factor?: number | null;
  defect_rate?: number | null;
  daily_demand?: number | null;
  inventory_multiplier?: number | null;
  iterations?: number | null;
  reshuffle_seed?: boolean;
}

export interface Simulation {
  stockout_probability: number;
  revenue_impact: number;
  recovery_time_days: number;
  service_level: number;
  expected_shortage_units: number;
  iterations: number;
  assumptions: string;
  revenue_loss_p50: number;
  revenue_loss_p90: number;
  engine: string;
  // Deterministic "flaw of averages" baseline — same model, mean inputs.
  deterministic_stockout: boolean;
  deterministic_revenue_loss: number;
  deterministic_shortage_units: number;
  deterministic_service_level: number;
  deterministic_recovery_days: number;
  // Per-iteration revenue-loss distribution (empty when no run lost revenue).
  revenue_histogram: HistogramBin[];
  // Resolved knob values this run used (null on legacy / no-impact runs).
  params?: SimParams | null;
}

// Body of POST /simulate/what-if — the current run's already-computed inputs
// plus the knob overrides to re-simulate with.
export interface WhatIfRequest {
  classifications: Classification[];
  impacts: ImpactMap[];
  forecast?: Forecast | null;
  overrides: SimOverrides;
}

export interface MitigationAction {
  action: string;
  urgency: string;
  expected_impact: string;
  owner: string;
  // Why this action was chosen (playbook + forecast/simulation drivers).
  // Empty on legacy runs — the UI derives a fallback from forecast/simulation.
  rationale?: string;
}

export interface Recommendation {
  actions: string[];
  structured_actions: MitigationAction[];
  summary: string;
  evidence: string[];
  generation_mode: string;
}

export interface DailyWeatherDay {
  date: string;
  weather_code: number;
  phrase: string;
  wind_kmh_max?: number | null;
  precipitation_mm?: number | null;
  severity_hint: string;
}

export interface WeatherRiskAssessment {
  signal_id: string;
  hub_port?: string | null;
  region?: string | null;
  lat?: number | null;
  lon?: number | null;
  horizon_days: number;
  daily_forecasts: DailyWeatherDay[];
  aggregate_severity: number;
  port_disruption_risk: number;
  affected_operations: string[];
  peak_day?: string | null;
  summary: string;
}

export interface PipelineState {
  new_signals?: DisruptionSignal[];
  event_analyses?: EventAnalysis[];
  weather_risks?: WeatherRiskAssessment[];
  classifications?: Classification[];
  impacts?: ImpactMap[];
  impact_summary?: string;
  forecast?: Forecast | null;
  simulation?: Simulation | null;
  recommendation?: Recommendation | null;
  route?: string;
  scenario_name?: string;
  run_id?: string;
}

export interface RecentRun {
  run_id: string;
  created_at?: string;
  scenario_name?: string | null;
  route?: string;
  max_severity?: number;
  payload?: unknown;
}

export interface CollectTotals {
  fetched: number;
  kept: number;
  dropped: number;
  persisted: number;
}

export interface CollectResult {
  db_persisted: boolean;
  sources: Array<Record<string, unknown>>;
  totals: CollectTotals;
}

export interface HealthResponse {
  status: string;
  database: string;
  database_mode: string;
  llm_mode: string;
  data_dir: string;
  retrieval_mode: string;
  retriever_stats: Record<string, number | string>;
}

export interface ConfigField {
  name: string;
  label: string;
  section: string;
  kind: string;
  secret: boolean;
  value: string | boolean | number;
}

export interface ConfigRuntime {
  config_file: string;
  storage_mode: string;
  storage_detail: string;
  database_url: string;
  llm_mode: string;
  retrieval_mode: string;
  retriever_stats: Record<string, number | string>;
  data_dir: string;
}

export interface ConfigSnapshot {
  fields: ConfigField[];
  runtime: ConfigRuntime;
}

export interface NetworkEntity {
  name: string;
  region: string;
  [key: string]: unknown;
}

export interface NetworkLane {
  name: string;
  mode: string;
  days: number;
  cost_index: number;
}

export interface SupplyNetwork {
  suppliers: NetworkEntity[];
  facilities: NetworkEntity[];
  lanes: NetworkLane[];
}
