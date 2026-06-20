"""The ingestion LangGraph node.

Collectors run **outside** the graph and persist accepted signals to Postgres (see
``ingestion/collect.py``). This node is the read side of the decoupled handoff:
``ingestion_node`` drains only the **new** rows (``status='new'`` -> ``processing``)
and emits them as a partial state update LangGraph merges into the ``new_signals``
channel. Delta-only — a second run with no new rows yields an empty batch.

Graceful offline contract: with no DB configured/reachable the node returns an empty
batch instead of crashing, so the existing ``__main__`` graph run still works.
"""

import logging
from typing import TYPE_CHECKING

import psycopg

from agentic_scd.db import DatabaseNotConfiguredError, connect, init_db
from agentic_scd.ingestion.schema import DisruptionSignal, Location

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

logger = logging.getLogger(__name__)

SELECT_NEW = """
SELECT signal_id, dedup_hash, source, source_type, source_reliability,
       fetched_at, event_time, title, raw_text, url,
       location, severity_hint, schema_version, raw_payload
FROM signals
WHERE status = 'new'
ORDER BY created_at
"""

COLUMNS = (
    "signal_id",
    "dedup_hash",
    "source",
    "source_type",
    "source_reliability",
    "fetched_at",
    "event_time",
    "title",
    "raw_text",
    "url",
    "location",
    "severity_hint",
    "schema_version",
    "raw_payload",
)


def row_to_signal(row: tuple) -> DisruptionSignal:
    data = dict(zip(COLUMNS, row, strict=True))
    location = data.pop("location")
    data["location"] = Location(**location) if location else None
    return DisruptionSignal(**data)


def read_new_signals(conn) -> list[DisruptionSignal]:  # noqa: ANN001 — psycopg conn
    """Select ``status='new'`` rows, mark them ``processing``, return them.

    Single transaction: the rows are claimed (status flipped) as they are read, so a
    later run never reprocesses them (delta-only handoff).
    """
    with conn.cursor() as cur:
        cur.execute(SELECT_NEW)
        rows = cur.fetchall()
        signals = [row_to_signal(row) for row in rows]
        if signals:
            cur.execute(
                "UPDATE signals SET status = 'processing' WHERE signal_id = ANY(%s)",
                ([s.signal_id for s in signals],),
            )
    conn.commit()
    return signals


def ingestion_node(state: "GraphState") -> dict:
    """Emit this run's batch of new signals as a partial state update.

    Returns ``{"new_signals": [...]}`` (overwrite reducer). Degrades to an empty batch
    when no DB is configured/reachable so the graph stays offline-runnable.
    """
    try:
        # Idempotently ensure the schema exists so the graph runs standalone on a
        # fresh DB (before the collector has ever run); a no-op once created.
        init_db()
        with connect() as conn:
            signals = read_new_signals(conn)
    except (DatabaseNotConfiguredError, psycopg.OperationalError) as exc:
        logger.warning(
            "ingestion_node: no DB available (%s); emitting empty batch", exc
        )
        return {"new_signals": []}
    return {"new_signals": signals}
