"""Simulation stub — tiny deterministic stockout / revenue-impact numbers.

The simplest real thing: derive a stockout probability and a revenue-impact figure from
the aggregate risk and how many entities are affected. Phase 6 replaces this with a
a SimPy discrete-event model + Monte Carlo runs behind the same ``simulate_node``
signature.
"""

from typing import TYPE_CHECKING

from agentic_scd.agents.forecast import aggregate_risk
from agentic_scd.agents.schema import Classification, ImpactMap, Simulation

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

REVENUE_AT_RISK = 250_000.0  # nominal revenue exposure scaled by risk/impact


def run_simulation(
    classifications: list[Classification], impacts: list[ImpactMap]
) -> Simulation:
    """Deterministic stockout probability + revenue impact for the batch."""
    risk = aggregate_risk(classifications)
    affected = sum(len(i.affected_entities) for i in impacts)

    # More risk + affected entities -> higher stockout probability; clamp to [0, 1].
    stockout_probability = round(min(1.0, risk * (0.8 + 0.04 * affected)), 4)
    revenue_impact = round(risk * REVENUE_AT_RISK * (1 + 0.1 * affected), 2)
    assumptions = (
        f"aggregate risk {risk:.2f}, {affected} affected entit"
        f"{'y' if affected == 1 else 'ies'}"
    )
    return Simulation(
        stockout_probability=stockout_probability,
        revenue_impact=revenue_impact,
        assumptions=assumptions,
    )


def simulate_node(state: "GraphState") -> dict:
    """Quantify the impact of this run's disruptions."""
    simulation = run_simulation(
        state.get("classifications", []), state.get("impacts", [])
    )
    return {"simulation": simulation}
