"""On-demand batch + retention entrypoint (console script ``agentic-scd-batch``).

Seeds historical data from the committed ``data/seed/`` snapshots into the ``signals``
table and prunes stale rows — the Phase 1c counterpart to the Phase 1a
``agentic-scd-collect``. One-shot, prints a concise summary. Graceful end-to-end: a
fully offline run (no network, no DB) still parses the snapshots and prints a summary
(nothing persisted, retention a no-op) and never crashes.

Flags select what runs (default: both):
  --load    run the batch loaders only
  --retain  run retention only
"""

import argparse
import logging

import psycopg

from agentic_scd.config import Settings, get_settings
from agentic_scd.db import DatabaseNotConfiguredError, connect, init_db
from agentic_scd.ingestion.batch import BatchSummary, load_batch
from agentic_scd.ingestion.retention import RetentionSummary, run_retention

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agentic-scd-batch",
        description="Seed historical data and prune stale rows (Phase 1c).",
    )
    parser.add_argument(
        "--load", action="store_true", help="run the batch loaders only"
    )
    parser.add_argument(
        "--retain", action="store_true", help="run retention/TTL pruning only"
    )
    return parser.parse_args(argv)


def open_connection(settings: Settings):  # noqa: ANN201 — psycopg conn | None
    """Open a DB connection, or return ``None`` when none is reachable (graceful)."""
    try:
        return connect(settings)
    except (DatabaseNotConfiguredError, psycopg.OperationalError) as exc:
        logger.warning("batch: no DB available (%s)", exc)
        return None


def run(
    settings: Settings | None = None, *, do_load: bool = True, do_retain: bool = True
) -> tuple[BatchSummary | None, RetentionSummary | None]:
    """Run the loaders and/or retention once over a (possibly absent) DB connection."""
    settings = settings or get_settings()
    db_ready = init_db(settings)
    conn = open_connection(settings) if db_ready else None

    batch_summary: BatchSummary | None = None
    retention_summary: RetentionSummary | None = None
    try:
        if do_load:
            batch_summary = load_batch(conn, settings)
        if do_retain:
            retention_summary = run_retention(conn, settings)
    finally:
        if conn is not None:
            conn.close()
    return batch_summary, retention_summary


def print_summary(
    batch: BatchSummary | None, retention: RetentionSummary | None
) -> None:
    db_persisted = bool(batch and batch.db_persisted) or bool(
        retention and retention.ran
    )
    where = "Postgres" if db_persisted else "no DB (offline)"
    path = "live" if db_persisted else "offline"
    print(f"Batch run complete - persistence: {where}")

    if batch is not None:
        header = (
            f"{'source':<24}{'loaded':>8}{'kept':>7}"
            f"{'dropped':>9}{'persisted':>11}{'path':>9}"
        )
        print(header)
        print("-" * len(header))
        if batch.enabled:
            for r in batch.results:
                print(
                    f"{r.name:<24}{r.loaded:>8}{r.kept:>7}"
                    f"{r.dropped:>9}{r.persisted:>11}{path:>9}"
                )
            t = batch.totals
            print("-" * len(header))
            print(
                f"{'TOTAL':<24}{t.loaded:>8}{t.kept:>7}"
                f"{t.dropped:>9}{t.persisted:>11}{'':>9}"
            )
        else:
            print("(batch loaders disabled)")

    if retention is not None:
        if retention.ran:
            print(
                f"Retention: pruned {retention.rejected_pruned} seen_rejected, "
                f"{retention.signals_pruned} done signals"
            )
        else:
            print("Retention: skipped (no DB or disabled)")


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint: seed + prune and print the summary."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    # Neither flag given -> do both (the common "seed + retain" run).
    do_load = args.load or not (args.load or args.retain)
    do_retain = args.retain or not (args.load or args.retain)
    batch, retention = run(do_load=do_load, do_retain=do_retain)
    print_summary(batch, retention)


if __name__ == "__main__":
    main()
