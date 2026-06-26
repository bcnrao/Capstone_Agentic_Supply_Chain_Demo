"""Persist: accepted signals -> Postgres; rejected hashes -> cache; raw -> snapshots.

Splits where each kind of data lives (see specs/data-ingestion.md):
- Accepted ``DisruptionSignal`` records (full row + ``raw_payload``) -> ``signals``
  with ``status='new'``; idempotent on ``dedup_hash`` so re-runs don't duplicate rows.
- Rejected items' ``dedup_hash`` only -> ``seen_rejected`` (skip re-evaluating junk).
- Raw feed pulls -> timestamped JSON **snapshot files outside the DB** (audit + the
  fallback/replay path), gitignored under ``data/snapshots/``.
"""

import json
from datetime import datetime
from pathlib import Path

from psycopg.types.json import Json

from agentic_scd.ingestion.connectors.base import RawItem
from agentic_scd.ingestion.dedupe import assign_hash
from agentic_scd.ingestion.paths import SNAPSHOT_DIR
from agentic_scd.ingestion.schema import DisruptionSignal

INSERT_SIGNAL = """
INSERT INTO signals (
    signal_id, dedup_hash, source, source_type, source_reliability,
    fetched_at, event_time, title, raw_text, url,
    location, severity_hint, schema_version, raw_payload, status
) VALUES (
    %(signal_id)s, %(dedup_hash)s, %(source)s, %(source_type)s, %(source_reliability)s,
    %(fetched_at)s, %(event_time)s, %(title)s, %(raw_text)s, %(url)s,
    %(location)s, %(severity_hint)s, %(schema_version)s, %(raw_payload)s, 'new'
)
ON CONFLICT (dedup_hash) DO NOTHING
"""


def persist_signal(conn, signal: DisruptionSignal) -> bool:  # noqa: ANN001 — psycopg conn
    """Insert an accepted signal (``status='new'``). Idempotent on ``dedup_hash``.

    Ensures ``dedup_hash`` is set, then inserts. Returns True if a row was written,
    False if it already existed (ON CONFLICT DO NOTHING).
    """
    if not signal.dedup_hash:
        assign_hash(signal)
    params = {
        "signal_id": signal.signal_id,
        "dedup_hash": signal.dedup_hash,
        "source": signal.source,
        "source_type": signal.source_type,
        "source_reliability": signal.source_reliability,
        "fetched_at": signal.fetched_at,
        "event_time": signal.event_time,
        "title": signal.title,
        "raw_text": signal.raw_text,
        "url": signal.url,
        "location": Json(signal.location.model_dump()) if signal.location else None,
        "severity_hint": signal.severity_hint,
        "schema_version": signal.schema_version,
        "raw_payload": Json(signal.raw_payload) if signal.raw_payload else None,
    }
    with conn.cursor() as cur:
        cur.execute(INSERT_SIGNAL, params)
        return cur.rowcount > 0


def record_rejected(conn, dedup_hash_value: str) -> None:  # noqa: ANN001 — psycopg conn
    """Store only a rejected item's ``dedup_hash`` so it isn't re-evaluated."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO seen_rejected (dedup_hash) VALUES (%s) "
            "ON CONFLICT (dedup_hash) DO NOTHING",
            (dedup_hash_value,),
        )


def write_snapshot(connector_name: str, raw_items: list[RawItem]) -> Path:
    """Write this run's raw pulls to a timestamped JSON snapshot outside the DB.

    Returns the snapshot path. This is the audit + re-tune-the-filter path; it is
    independent of whether the DB is reachable.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SNAPSHOT_DIR / f"{connector_name}-{stamp}.json"
    payload = [item.model_dump() for item in raw_items]
    path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    return path
