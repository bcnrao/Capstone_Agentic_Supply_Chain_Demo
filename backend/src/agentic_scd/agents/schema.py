from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class EventAnalysis(BaseModel):
    signal_id: str
    event_type: str
    entities: list[str] = Field(default_factory=list)
    extracted_region: str | None = None
    severity_hint: str | None = None
    summary: str = ""
    retrieved_context: list[str] = Field(default_factory=list)


class Classification(BaseModel):
    signal_id: str
    category: str
    risk_score: float = Field(default=0.0, ge=0, le=1)
    severity: float = Field(default=0.0, ge=0, le=10)
    confidence: float = Field(default=0.75, ge=0, le=1)
    risk_level: str = "LOW"
    route: str = "full_path"
    rationale: str = ""

    @model_validator(mode="after")
    def fill_derived_fields(self):
        if not self.severity and self.risk_score:
            self.severity = round(self.risk_score * 10, 2)
        if not self.risk_level or self.risk_level == "LOW":
            if self.severity > 7:
                self.risk_level = "HIGH"
            elif self.severity >= 4:
                self.risk_level = "MEDIUM"
            else:
                self.risk_level = "LOW"
        # Every signal runs the full pipeline; severity only sets risk_level.
        self.route = "full_path"
        return self


class ImpactMap(BaseModel):
    signal_id: str
    affected_entities: list[str] = Field(default_factory=list)
    affected_suppliers: list[str] = Field(default_factory=list)
    affected_lanes: list[str] = Field(default_factory=list)
    affected_facilities: list[str] = Field(default_factory=list)
    product_categories: list[str] = Field(default_factory=list)
    retrieved_context: list[str] = Field(default_factory=list)
    reasoning: str = ""

    @model_validator(mode="after")
    def fill_entities(self):
        merged = list(self.affected_entities)
        merged.extend(self.affected_suppliers)
        merged.extend(self.affected_lanes)
        merged.extend(self.affected_facilities)
        self.affected_entities = list(dict.fromkeys(item for item in merged if item))
        return self


class Forecast(BaseModel):
    dates: list[str] = Field(default_factory=list)
    baseline: list[float] = Field(default_factory=list)
    adjusted: list[float] = Field(default_factory=list)
    demand_deviation_pct: float = 0.0
    inventory_days_left: float = 0.0
    predicted_delay_days: float = 0.0
    mape_estimate: float = 0.0
    note: str = ""
    model_name: str = ""
    freight_pressure_pct: float = 0.0
    retrieved_context: list[str] = Field(default_factory=list)


class HistogramBin(BaseModel):
    bin_start: float
    bin_end: float
    count: int


class SimOverrides(BaseModel):
    """User-supplied what-if overrides for the simulation knobs.

    Every field is optional; a value of ``None`` means "use the value the
    scenario derives on its own". Ranges are enforced server-side because these
    flow straight into SimPy timeouts and numpy draws (an uncapped iteration
    count would hang the request thread).
    """

    risk: float | None = Field(default=None, ge=0, le=1)
    # Supplier lead-time mean (days) — the Supplier-node knob.
    lead_time_mean: float | None = Field(default=None, gt=0, le=120)
    # Port-congestion multiplier on the port-clearance delay — the Port-node knob
    # (1.0 = derived). Preferred over supplier_reliability, which the SimPy model
    # ignores (it only feeds the numpy fallback), so a slider for it would be dead.
    port_delay_factor: float | None = Field(default=None, gt=0, le=10)
    defect_rate: float | None = Field(default=None, ge=0, le=1)
    daily_demand: float | None = Field(default=None, gt=0, le=100_000)
    # Multiplier on the derived opening inventory (1.0 = unchanged). Preferred
    # over a safety-buffer-days knob because the buffer sits under a max() floor
    # dominated by the ~38-day first-shipment ETA, so it barely moves outcomes.
    inventory_multiplier: float | None = Field(default=None, gt=0, le=10)
    iterations: int | None = Field(default=None, ge=1, le=2000)
    # When true, draw a fresh random seed instead of the scenario's deterministic
    # one — surfaces sampling noise rather than isolating a knob's effect.
    reshuffle_seed: bool = False


class SimParams(BaseModel):
    """The resolved knob values a simulation actually ran with — echoed back so
    the what-if UI can anchor its sliders at the scenario's real values."""

    risk: float = 0.0
    supplier_reliability: float = 0.0
    lead_time_mean: float = 0.0
    defect_rate: float = 0.0
    daily_demand: float = 0.0
    opening_inventory: float = 0.0
    iterations: int = 0


class Simulation(BaseModel):
    stockout_probability: float = Field(default=0.0, ge=0, le=1)
    revenue_impact: float = 0.0
    recovery_time_days: float = 0.0
    service_level: float = Field(default=1.0, ge=0, le=1)
    expected_shortage_units: float = 0.0
    iterations: int = 0
    assumptions: str = ""
    revenue_loss_p50: float = 0.0
    revenue_loss_p90: float = 0.0
    engine: str = ""
    retrieved_context: list[str] = Field(default_factory=list)
    # Deterministic "flaw of averages" baseline — the same model run once with
    # every stochastic input fixed at its mean. Contrasted against the Monte
    # Carlo distribution above to show what single-point estimates hide.
    deterministic_stockout: bool = False
    deterministic_revenue_loss: float = 0.0
    deterministic_shortage_units: float = 0.0
    deterministic_service_level: float = 1.0
    deterministic_recovery_days: float = 0.0
    # Per-iteration revenue-loss distribution (empty when no run lost revenue).
    revenue_histogram: list[HistogramBin] = Field(default_factory=list)
    # Resolved knob values this run used — lets the what-if UI anchor its sliders.
    params: SimParams | None = None


class MitigationAction(BaseModel):
    action: str
    urgency: str
    expected_impact: str
    owner: str


class Recommendation(BaseModel):
    actions: list[str] = Field(default_factory=list)
    structured_actions: list[MitigationAction] = Field(default_factory=list)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    generation_mode: str = "deterministic"


class DailyWeatherDay(BaseModel):
    date: str
    weather_code: int
    phrase: str
    wind_kmh_max: float | None = None
    precipitation_mm: float | None = None
    severity_hint: str = "none"  # none | low | moderate | severe


class WeatherRiskAssessment(BaseModel):
    signal_id: str
    hub_port: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    horizon_days: int = 0
    daily_forecasts: list[DailyWeatherDay] = Field(default_factory=list)
    aggregate_severity: float = Field(default=0.0, ge=0, le=10)
    port_disruption_risk: float = Field(default=0.0, ge=0, le=1)
    affected_operations: list[str] = Field(default_factory=list)
    peak_day: str | None = None
    summary: str = ""
    retrieved_context: list[str] = Field(default_factory=list)
