from __future__ import annotations

from typing import TYPE_CHECKING

from agentic_scd.agents.sim_engine import run_discrete_event
from agentic_scd.agents.forecast import aggregate_risk
from agentic_scd.agents.schema import Classification, Forecast, ImpactMap, Simulation
from agentic_scd.config import get_settings

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState


def run_simulation(classifications: list[Classification], impacts: list[ImpactMap], forecast: Forecast | None = None, iterations: int | None = None) -> Simulation:
    settings = get_settings()
    n = iterations or settings.simulation_iterations
    risk = aggregate_risk(classifications)
    affected = sum(len(item.affected_entities) for item in impacts)
    if risk <= 0 and affected <= 0:
        return Simulation(stockout_probability=0.0, revenue_impact=0.0, recovery_time_days=0.0, service_level=1.0, expected_shortage_units=0.0, iterations=n, assumptions="No active risk or affected network nodes.", engine="discrete_event_local")
    data = run_discrete_event(classifications, impacts, forecast, n)
    return Simulation(
        stockout_probability=float(data["stockout_probability"]),
        revenue_impact=float(data["revenue_impact"]),
        recovery_time_days=float(data["recovery_time_days"]),
        service_level=float(data["service_level"]),
        expected_shortage_units=float(data["expected_shortage_units"]),
        iterations=int(data["iterations"]),
        assumptions=str(data["assumptions"]),
        revenue_loss_p50=float(data["revenue_loss_p50"]),
        revenue_loss_p90=float(data["revenue_loss_p90"]),
        engine=str(data["engine"]),
    )


def simulate_node(state: "GraphState") -> dict:
    simulation = run_simulation(state.get("classifications", []), state.get("impacts", []), state.get("forecast"))
    return {"simulation": simulation}
