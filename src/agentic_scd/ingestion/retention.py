"""Retention / TTL housekeeping for the ingestion tables (Phase 1c).

Prunes two kinds of stale rows the live pipeline no longer needs, using the
``first_seen_at`` / ``created_at`` columns the Phase 1 schema already carries:

- ``seen_rejected`` rows older than ``retention_rejected_ttl_days`` — old junk hashes
  the dedupe cache can forget.
- **Terminal** ``signals`` (``status='done'``) past ``retention_signals_ttl_days``.

It **never** touches ``new`` / ``processing`` signals — those are the pipeline's working
set. Run on demand (alongside seeding) via the ``agentic-scd-batch`` CLI; a clean no-op
when no DB is reachable or retention is disabled.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Delete seen_rejected hashes older than the TTL (interval built from an int day count).
PRUNE_REJECTED_SQL = (
    "DELETE FROM seen_rejected WHERE first_seen_at < now() - make_interval(days => %s)"
)

# Delete ONLY terminal (done) signals past the TTL — never new/processing rows.
PRUNE_SIGNALS_SQL = (
    "DELETE FROM signals "
    "WHERE status = 'done' AND created_at < now() - make_interval(days => %s)"
)


@dataclass
class RetentionSummary:
    """Outcome of a retention pass."""

    ran: bool = False
    rejected_pruned: int = 0
    signals_pruned: int = 0


def prune_seen_rejected(conn, ttl_days: int) -> int:  # noqa: ANN001 — psycopg conn
    """Delete ``seen_rejected`` rows older than ``ttl_days``; return rows removed."""
    with conn.cursor() as cur:
        cur.execute(PRUNE_REJECTED_SQL, (ttl_days,))
        return cur.rowcount


def prune_signals(conn, ttl_days: int) -> int:  # noqa: ANN001 — psycopg conn
    """Delete stale **done** signals older than ``ttl_days``; return rows removed.

    Scoped to ``status='done'`` so rows the pipeline still needs (``new`` /
    ``processing``) are never deleted.
    """
    with conn.cursor() as cur:
        cur.execute(PRUNE_SIGNALS_SQL, (ttl_days,))
        return cur.rowcount


def run_retention(conn, settings) -> RetentionSummary:  # noqa: ANN001 — conn | None
    """Prune both caches once and return the counts.

    A clean no-op (``ran=False``, zero counts, never raises) when ``conn`` is ``None``
    or retention is disabled — keeping the offline / off-by-safe contract.
    """
    if conn is None or not settings.retention_enabled:
        if conn is None:
            logger.info("retention: no DB — skipping (no-op)")
        else:
            logger.info("retention disabled (RETENTION_ENABLED=false) — skipping")
        return RetentionSummary(ran=False)

    rejected = prune_seen_rejected(conn, settings.retention_rejected_ttl_days)
    signals = prune_signals(conn, settings.retention_signals_ttl_days)
    conn.commit()
    logger.info(
        "retention: pruned %d seen_rejected, %d done signals", rejected, signals
    )
    return RetentionSummary(ran=True, rejected_pruned=rejected, signals_pruned=signals)
