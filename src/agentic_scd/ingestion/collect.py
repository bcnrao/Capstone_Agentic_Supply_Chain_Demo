"""On-demand collector entrypoint (console script ``agentic-scd-collect``).

Runs every enabled connector once through the full pipeline —
fetch -> snapshot -> normalize -> relevance gate -> dedupe -> persist — and prints a
per-source summary (fetched / kept / dropped / persisted / fallback). Graceful
end-to-end: a fully offline run (no network, no DB) still yields signals from the
synthetic connector and cached fallbacks and never crashes. The scheduled poller and
FastAPI webhook are Phase 1b.
"""

import logging
from dataclasses import dataclass, field

from agentic_scd.config import Settings, get_settings
from agentic_scd.db import connect, init_db
from agentic_scd.ingestion.connectors.base import Connector, fetch_with_fallback
from agentic_scd.ingestion.dedupe import assign_hash, is_duplicate
from agentic_scd.ingestion.normalize import normalize
from agentic_scd.ingestion.registry import load_registry
from agentic_scd.ingestion.relevance import gate
from agentic_scd.ingestion.store import persist_signal, record_rejected, write_snapshot

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """Per-connector tally for one collection run."""

    name: str
    fetched: int = 0
    kept: int = 0
    dropped: int = 0
    persisted: int = 0
    fallback_used: bool = False


@dataclass
class CollectSummary:
    """Outcome of a collection run across all enabled connectors."""

    db_persisted: bool = False
    results: list[SourceResult] = field(default_factory=list)

    @property
    def totals(self) -> SourceResult:
        agg = SourceResult(name="TOTAL")
        for r in self.results:
            agg.fetched += r.fetched
            agg.kept += r.kept
            agg.dropped += r.dropped
            agg.persisted += r.persisted
        return agg


def process_connector(connector: Connector, conn) -> SourceResult:  # noqa: ANN001
    """Run one connector through the pipeline. ``conn`` is a DB connection or None."""
    result = SourceResult(name=connector.name)

    raw_items, path = fetch_with_fallback(connector)
    result.fetched = len(raw_items)
    result.fallback_used = path == "fallback"
    write_snapshot(connector.name, raw_items)

    signals = [normalize(item, connector) for item in raw_items]
    kept, dropped = gate(signals)
    result.kept = len(kept)
    result.dropped = len(dropped)

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


def collect(settings: Settings | None = None) -> CollectSummary:
    """Run all enabled connectors once and return the run summary."""
    settings = settings or get_settings()
    db_ready = init_db(settings)
    summary = CollectSummary(db_persisted=db_ready)

    conn = None
    try:
        if db_ready:
            conn = connect(settings)
        for connector in load_registry():
            summary.results.append(process_connector(connector, conn))
    finally:
        if conn is not None:
            conn.close()
    return summary


def print_summary(summary: CollectSummary) -> None:
    where = "Postgres" if summary.db_persisted else "no DB (in-memory only)"
    print(f"Collection complete - persistence: {where}")
    header = (
        f"{'source':<20}{'fetched':>9}{'kept':>7}"
        f"{'dropped':>9}{'persisted':>11}{'path':>11}"
    )
    print(header)
    print("-" * len(header))
    for r in summary.results:
        path = "fallback" if r.fallback_used else "live"
        print(
            f"{r.name:<20}{r.fetched:>9}{r.kept:>7}{r.dropped:>9}{r.persisted:>11}{path:>11}"
        )
    t = summary.totals
    print("-" * len(header))
    print(
        f"{'TOTAL':<20}{t.fetched:>9}{t.kept:>7}{t.dropped:>9}{t.persisted:>11}{'':>11}"
    )


def main() -> None:
    """CLI entrypoint: run a collection and print the per-source summary."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    print_summary(collect())


if __name__ == "__main__":
    main()
