"""The shared, typed LangGraph state object.

The ingestion channel ``new_signals`` (Phase 1) carries the batch of freshly ingested
``DisruptionSignal`` records. Phase 2 adds one channel per downstream agent
(``classifications`` … ``recommendation``) so the walking skeleton can flow state from
agent to agent. Every channel uses the overwrite-per-run reducer (LangGraph's default
for a plain annotation): each run's state holds that run's batch, while local PostgreSQL
is the durable accumulator (see specs/data-ingestion.md).
"""

from typing import TypedDict

from agentic_scd.agents.schema import (
    Classification,
    Forecast,
    ImpactMap,
    Recommendation,
    Simulation,
)
from agentic_scd.ingestion.schema import DisruptionSignal


class GraphState(TypedDict, total=False):
    """State passed between LangGraph nodes."""

    # --- Ingestion (Phase 1) ----------------------------------------------
    new_signals: list[DisruptionSignal]

    # --- Downstream agents (Phase 2 stubs; deepened in Phases 3-7) ---------
    classifications: list[Classification]
    impacts: list[ImpactMap]
    forecast: Forecast
    simulation: Simulation
    recommendation: Recommendation
