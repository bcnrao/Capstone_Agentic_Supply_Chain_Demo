from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentic_scd.config import get_settings
from agentic_scd.db import connect, init_db
from agentic_scd.ingestion.sqlutil import commit, dialect, execute, fetchone, placeholders
from agentic_scd.ingestion.store import row_to_signal

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

logger = logging.getLogger(__name__)

# DATASET / FREIGHT_INDEX rows are reference data for the RAG layer, not
# disruption events, so they never enter the agent path.
_PENDING_WHERE = "status = 'new' AND source_type NOT IN ('DATASET', 'FREIGHT_INDEX')"

COUNT_NEW = f"SELECT COUNT(*) FROM signals WHERE {_PENDING_WHERE}"

# Oldest-first so a backlog drains in arrival order across successive runs.
SELECT_NEW = f"SELECT * FROM signals WHERE {_PENDING_WHERE} ORDER BY created_at"


def count_pending(conn) -> int:
    """How many signals are waiting, before any cap is applied."""
    row = fetchone(conn, COUNT_NEW)
    return int(row[0]) if row else 0


def read_new_signals(conn, limit: int | None = None) -> list:
    """Claim up to ``limit`` pending signals; report the full pending depth.

    Every LLM-backed agent runs per signal, so wall-clock time scales linearly
    with how many signals are claimed. A collect returning 30+ items would push
    a run past the client timeout, so the caller caps the batch.

    The cap is a SQL LIMIT rather than a Python slice on purpose: only rows
    actually claimed are flipped to 'processing'. The remainder stay 'new' and
    are picked up by the next run, so nothing is lost and successive runs show
    fresh signals instead of repeating the same batch.

    Returns the claimed signals; call count_pending() first for the depth.
    """
    sql = SELECT_NEW
    if limit is not None and limit > 0:
        sql = f"{sql} LIMIT {int(limit)}"

    rows = execute(conn, sql).fetchall()
    signals = [row_to_signal(row) for row in rows]
    if signals:
        ids = [signal.signal_id for signal in signals]
        style = "sqlite" if dialect(conn) == "sqlite" else "pyformat"
        update = f"UPDATE signals SET status = 'processing' WHERE signal_id IN ({placeholders(len(ids), style)})"
        execute(conn, update, tuple(ids))
        commit(conn)
    return signals


def ingestion_node(state: "GraphState") -> dict:
    if state.get("new_signals"):
        return {}
    if state.get("scenario_names"):
        return {"new_signals": []}

    limit = get_settings().max_signals_per_run
    pending_total = 0
    try:
        init_db()
        with connect() as conn:
            pending_total = count_pending(conn)
            signals = read_new_signals(conn, limit)
    except Exception as exc:
        logger.warning("ingestion node used in-memory fallback: %s", exc)
        signals = []

    deferred = max(0, pending_total - len(signals))
    if deferred:
        logger.info(
            "ingestion node claimed %d of %d pending signals (cap=%d); %d deferred to next run",
            len(signals), pending_total, limit, deferred,
        )
    return {
        "new_signals": signals,
        "signals_pending_total": pending_total,
        "signals_deferred": deferred,
    }
