"""Persistence round-trip (DB-touching). Skips cleanly when no Postgres is reachable.

With the Compose ``postgres`` service up, exercises init_db -> persist -> idempotency
-> seen_rejected. Cleans up its own rows so re-runs stay green.
"""

import uuid
from datetime import UTC, datetime

import pytest

from agentic_scd.db import connect, init_db, ping
from agentic_scd.ingestion.dedupe import assign_hash, is_duplicate
from agentic_scd.ingestion.schema import DisruptionSignal
from agentic_scd.ingestion.store import persist_signal, record_rejected


@pytest.fixture
def conn():
    result = ping()
    if not result.ok:
        pytest.skip(f"no Postgres reachable ({result.detail})")
    assert init_db() is True
    connection = connect()
    yield connection
    connection.close()


def make_signal() -> DisruptionSignal:
    # Unique per run so the test never collides with real or prior-run data.
    marker = uuid.uuid4().hex
    return assign_hash(
        DisruptionSignal(
            signal_id=marker,
            source="test",
            source_type="SYNTHETIC",
            source_reliability=0.5,
            fetched_at=datetime.now(UTC),
            title=f"Port strike test {marker}",
            raw_text="Shipments halted in test.",
            raw_payload={"marker": marker},
        )
    )


def test_persist_is_idempotent_on_dedup_hash(conn) -> None:
    sig = make_signal()
    try:
        assert persist_signal(conn, sig) is True
        conn.commit()
        # Second insert of the same dedup_hash writes no new row.
        assert persist_signal(conn, sig) is False
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM signals WHERE dedup_hash = %s", (sig.dedup_hash,)
            )
            assert cur.fetchone()[0] == 1
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM signals WHERE dedup_hash = %s", (sig.dedup_hash,))
        conn.commit()


def test_record_rejected_marks_duplicate(conn) -> None:
    sig = make_signal()
    try:
        record_rejected(conn, sig.dedup_hash)
        conn.commit()
        assert is_duplicate(sig.dedup_hash, conn) is True
    finally:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM seen_rejected WHERE dedup_hash = %s", (sig.dedup_hash,)
            )
        conn.commit()
