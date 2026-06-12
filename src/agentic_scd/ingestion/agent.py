"""The ingestion LangGraph node.

Phase 0 ships a **stub**: it emits a single synthetic ``DisruptionSignal`` so the
graph's emit/merge mechanism is exercised end-to-end (the node returns a partial
state update that LangGraph merges into the ``new_signals`` channel). Phase 1
replaces the body with the real fetch -> normalize -> gate -> dedupe -> persist ->
emit pipeline (see specs/data-ingestion.md) behind this same node signature.
"""

import uuid
from datetime import UTC, datetime

from agentic_scd.graph.state import GraphState
from agentic_scd.ingestion.schema import DisruptionSignal


def synthetic_signal() -> DisruptionSignal:
    """A deterministic-shape placeholder signal proving the channel works."""
    now = datetime.now(UTC)
    return DisruptionSignal(
        signal_id=str(uuid.uuid4()),
        source="synthetic_stub",
        source_type="SYNTHETIC",
        fetched_at=now,
        event_time=now,
        title="Placeholder disruption signal (Phase 0 stub)",
        raw_text=(
            "Scaffolding stub signal emitted by the ingestion node to prove the "
            "LangGraph emit/merge mechanism. Replaced by real connectors in Phase 1."
        ),
        url=None,
    )


def ingestion_node(state: GraphState) -> dict:
    """Emit this run's batch of new signals as a partial state update.

    Returns a dict (not the whole state) so LangGraph merges it into the
    ``new_signals`` channel via that channel's reducer.
    """
    return {"new_signals": [synthetic_signal()]}
