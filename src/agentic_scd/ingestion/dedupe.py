"""Dedupe — exact SHA-256 over normalized title + body.

The same event recurs (re-polled feeds, cross-outlet syndication, demo re-runs);
without dedupe one event inflates into many "disruptions". MVP uses **exact** hash
dedupe (catches re-fetches + verbatim syndication); fuzzy dedupe is deferred. Hashing
the *normalized* text is why normalize must run first.

``assign_hash`` computes the hash and stamps it on the signal (offline, no DB);
``is_duplicate`` takes a live connection to check the ``seen_rejected`` cache and
already-persisted ``signals``.
"""

import hashlib

from agentic_scd.ingestion.schema import DisruptionSignal


def assign_hash(signal: DisruptionSignal) -> DisruptionSignal:
    """Stamp ``signal.dedup_hash`` with ``sha256(normalized title + body)``.

    Sets the hash in place and returns the same signal for chaining. Hashing the
    *normalized* text is why normalize must run before dedupe.
    """
    signal.dedup_hash = hashlib.sha256(
        f"{signal.title}{signal.raw_text}".encode()
    ).hexdigest()
    return signal


def is_duplicate(dedup_hash_value: str, conn) -> bool:  # noqa: ANN001 — psycopg conn
    """True if the hash is already in ``seen_rejected`` or persisted in ``signals``."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM seen_rejected WHERE dedup_hash = %s "
            "UNION ALL SELECT 1 FROM signals WHERE dedup_hash = %s LIMIT 1",
            (dedup_hash_value, dedup_hash_value),
        )
        return cur.fetchone() is not None
