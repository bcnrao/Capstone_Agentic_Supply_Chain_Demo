"""The shared, typed LangGraph state object.

For Phase 0 the only channel is ``new_signals`` — the batch of freshly ingested
``DisruptionSignal`` records the ingestion node emits and downstream nodes read
(see specs/data-ingestion.md). The POC uses an **overwrite-per-run** reducer:
each run's state holds that run's batch, while local PostgreSQL (Phase 1) is the
durable accumulator. Overwrite is LangGraph's default channel behaviour, so the plain
``list`` annotation is exactly the reducer we want here.
"""

from typing import TypedDict

from agentic_scd.ingestion.schema import DisruptionSignal


class GraphState(TypedDict, total=False):
    """State passed between LangGraph nodes."""

    new_signals: list[DisruptionSignal]
