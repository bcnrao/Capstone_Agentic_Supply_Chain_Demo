"""ingest_node handoff round-trip (DB-touching). Skips cleanly with no Postgres.

Verifies the delta-only contract: read_new_signals returns status='new' rows, flips
them to 'processing', and a second read does not see them again.
"""

import uuid
from datetime import UTC, datetime

import pytest

from agentic_scd.db import connect, init_db, ping
from agentic_scd.ingestion.agent import read_new_signals
from agentic_scd.ingestion.dedupe import assign_hash
from agentic_scd.ingestion.schema import DisruptionSignal
from agentic_scd.ingestion.store import persist_signal


@pytest.fixture
def conn():
    result = ping()
    if not result.ok:
        pytest.skip(f"no Postgres reachable ({result.detail})")
    assert init_db() is True
    connection = connect()
    yield connection
    connection.close()


def test_read_new_signals_is_delta_only(conn) -> None:
    marker = uuid.uuid4().hex
    sig = assign_hash(
        DisruptionSignal(
            signal_id=marker,
            source="test",
            source_type="SYNTHETIC",
            fetched_at=datetime.now(UTC),
            title=f"Tariff disruption test {marker}",
            raw_text="Logistics disrupted in test.",
        )
    )
    try:
        persist_signal(conn, sig)
        conn.commit()

        first = read_new_signals(conn)
        assert any(s.signal_id == marker for s in first)

        # Second drain: the row is now 'processing', so it is not re-read.
        second = read_new_signals(conn)
        assert all(s.signal_id != marker for s in second)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM signals WHERE signal_id = %s", (marker,))
        conn.commit()
