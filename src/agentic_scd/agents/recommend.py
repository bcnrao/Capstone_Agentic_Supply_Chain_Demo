"""Recommendation stub — templated mitigation actions.

The simplest real thing: pick templated actions by the disruption categories present and
frame them with the simulated impact. Phase 7 replaces this with RAG-grounded mitigation
generation (cited precedent) plus the output guardrail, behind the same
``recommend_node`` signature.
"""

from typing import TYPE_CHECKING

from agentic_scd.agents.schema import (
    Classification,
    ImpactMap,
    Recommendation,
    Simulation,
)

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

# Category -> templated mitigation action (deepened/grounded in Phase 7).
ACTION_BY_CATEGORY: dict[str, str] = {
    "labor": "Reroute volume away from the strike-affected port",
    "natural_disaster": "Shift volume to an alternate-region supplier",
    "logistics": "Expedite freight and pre-position safety stock",
    "policy": "Qualify a tariff-exempt alternate supplier",
    "supply": "Raise safety stock and dual-source the affected component",
    "other": "Monitor the situation and review supplier exposure",
}
DEFAULT_ACTION = "Raise safety stock for affected SKUs"


def build_recommendation(
    classifications: list[Classification],
    impacts: list[ImpactMap],
    simulation: Simulation,
) -> Recommendation:
    """Templated actions for the categories present, framed by the simulation."""
    categories = list(
        dict.fromkeys(c.category for c in classifications)
    )  # de-dup, ordered
    actions = [ACTION_BY_CATEGORY.get(c, DEFAULT_ACTION) for c in categories]
    if not actions:
        actions = [DEFAULT_ACTION]

    affected = sum(len(i.affected_entities) for i in impacts)
    summary = (
        f"{len(actions)} action(s) for {len(categories) or 1} category(ies); "
        f"stockout prob {simulation.stockout_probability:.0%}, "
        f"{affected} affected entit{'y' if affected == 1 else 'ies'}"
    )
    return Recommendation(actions=actions, summary=summary)


def recommend_node(state: "GraphState") -> dict:
    """Produce mitigation recommendations for this run."""
    simulation = state.get("simulation") or Simulation(
        stockout_probability=0.0, revenue_impact=0.0
    )
    recommendation = build_recommendation(
        state.get("classifications", []), state.get("impacts", []), simulation
    )
    return {"recommendation": recommendation}
