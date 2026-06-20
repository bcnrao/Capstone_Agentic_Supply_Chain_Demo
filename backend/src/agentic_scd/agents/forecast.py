"""Forecast stub — flat baseline vs a risk-adjusted demand curve.

The simplest real thing: a flat baseline demand series and an adjusted series that bends
down further out under disruption risk, so the forecast visibly responds to active
risk. Phase 5 replaces this with a Prophet baseline + risk-adjusted forecast behind the
same ``forecast_node`` signature.
"""

from typing import TYPE_CHECKING

from agentic_scd.agents.schema import Classification, Forecast

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

HORIZON = 8  # forecast steps (e.g. weeks)
BASELINE_DEMAND = 100.0


def aggregate_risk(classifications: list[Classification]) -> float:
    """Mean risk score across the batch (0.0 when there is nothing classified)."""
    if not classifications:
        return 0.0
    return sum(c.risk_score for c in classifications) / len(classifications)


def build_forecast(classifications: list[Classification]) -> Forecast:
    """Baseline vs risk-adjusted demand for the current batch's aggregate risk."""
    risk = aggregate_risk(classifications)
    baseline = [BASELINE_DEMAND] * HORIZON
    # The dip deepens over the horizon, scaled by aggregate risk.
    adjusted = [
        round(BASELINE_DEMAND * (1 - risk * (step + 1) / HORIZON), 2)
        for step in range(HORIZON)
    ]
    note = f"adjusted by aggregate risk {risk:.2f} over {HORIZON} steps"
    return Forecast(baseline=baseline, adjusted=adjusted, note=note)


def forecast_node(state: "GraphState") -> dict:
    """Produce the risk-adjusted demand forecast for this run."""
    return {"forecast": build_forecast(state.get("classifications", []))}
