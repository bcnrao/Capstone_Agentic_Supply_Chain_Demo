"""The shared persistence tail: gate -> dedupe -> persist.

One path used by every trigger — the on-demand/scheduled collector
(``collect.process_connector``) and the FastAPI webhook both hand their normalized
signals here, so accepted rows, the seen-rejected cache, and idempotent dedupe behave
identically no matter how a signal arrived. Stages before this (fetch, normalize) are
source-specific; this stage is not.
"""

from dataclasses import dataclass

from agentic_scd.ingestion.dedupe import assign_hash, is_duplicate
from agentic_scd.ingestion.relevance import gate
from agentic_scd.ingestion.schema import DisruptionSignal
from agentic_scd.ingestion.store import persist_signal, record_rejected


@dataclass
class IngestResult:
    """Counts from running a batch of normalized signals through the tail."""

    kept: int = 0
    dropped: int = 0
    persisted: int = 0

    @property
    def duplicate(self) -> int:
        """Relevant signals skipped as already-seen (kept but not persisted)."""
        return self.kept - self.persisted


def ingest_signals(signals: list[DisruptionSignal], conn) -> IngestResult:  # noqa: ANN001
    """Gate, dedupe, and persist a batch of normalized signals.

    ``conn`` is a live psycopg connection, or ``None`` to run in-memory (no DB): the
    relevance split still happens and is reported, but nothing is persisted — keeping
    the offline contract. Idempotent on ``dedup_hash``; commits once at the end.
    """
    kept, dropped = gate(signals)
    result = IngestResult(kept=len(kept), dropped=len(dropped))

    if conn is None:
        return result  # offline: pipeline ran in-memory, nothing persisted.

    for signal in kept:
        assign_hash(signal)
        if is_duplicate(signal.dedup_hash, conn):
            continue
        if persist_signal(conn, signal):
            result.persisted += 1
    for signal in dropped:
        record_rejected(conn, assign_hash(signal).dedup_hash)
    conn.commit()
    return result
