"""Typed result models the downstream agent stubs attach to graph state.

One small Pydantic model per stage, carried on its own ``GraphState`` channel
(overwrite-per-run). Phases 3-7 fill these with real values without changing the shape:
the skeleton fixes the contract now so each later phase deepens one agent in isolation.
"""

from pydantic import BaseModel, Field


class Classification(BaseModel):
    """Per-signal category + risk score (Phase 3 deepens with DistilBERT)."""

    signal_id: str = Field(..., description="The classified signal.")
    category: str = Field(..., description="Coarse disruption category, e.g. 'labor'.")
    risk_score: float = Field(..., description="Risk score in [0, 1].")
    rationale: str = Field(default="", description="Short why (keyword hits, source).")


class ImpactMap(BaseModel):
    """Per-signal affected network parts (Phase 4 replaces with RAG over the KB)."""

    signal_id: str = Field(..., description="The signal this impact is for.")
    affected_entities: list[str] = Field(
        default_factory=list,
        description="Suppliers / lanes / facilities the event touches.",
    )


class Forecast(BaseModel):
    """Baseline vs risk-adjusted demand (Phase 5 replaces with Prophet)."""

    baseline: list[float] = Field(default_factory=list, description="Baseline demand.")
    adjusted: list[float] = Field(
        default_factory=list, description="Risk-adjusted demand."
    )
    note: str = Field(default="", description="How the adjustment was derived.")


class Simulation(BaseModel):
    """Quantified impact (Phase 6 replaces with SimPy + Monte Carlo)."""

    stockout_probability: float = Field(
        ..., description="Stockout probability in [0, 1]."
    )
    revenue_impact: float = Field(
        ..., description="Estimated revenue impact (currency)."
    )
    assumptions: str = Field(
        default="", description="Key assumptions behind the numbers."
    )


class Recommendation(BaseModel):
    """Mitigation actions (Phase 7 replaces with RAG-grounded generation)."""

    actions: list[str] = Field(
        default_factory=list, description="Recommended mitigation actions."
    )
    summary: str = Field(default="", description="One-line framing of the plan.")
