"""Webhook -> persist -> ingest_node round-trip (DB-touching); skips with no DB."""

import uuid

import pytest
from fastapi.testclient import TestClient

from agentic_scd.config import get_settings
from agentic_scd.config.settings import Settings
from agentic_scd.db import connect, ping
from agentic_scd.ingestion.agent import read_new_signals
from agentic_scd.ingestion.service import create_app


@pytest.fixture
def client_db():
    result = ping()
    if not result.ok:
        pytest.skip(f"no Postgres reachable ({result.detail})")
    base = get_settings()
    # Real DB, but no background poller during the test.
    settings = Settings(
        groq_api_key=base.groq_api_key,
        groq_model=base.groq_model,
        use_mock_llm=True,
        database_url=base.database_url,
        ingest_scheduler_enabled=False,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_webhook_persists_and_drains(client_db) -> None:
    marker = uuid.uuid4().hex
    resp = client_db.post(
        "/signals",
        json={"title": f"Port strike test {marker}", "body": "Shipments halted."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["persisted_to_db"] is True
    assert body["kept"] == 1
    assert body["persisted"] == 1

    conn = connect()
    try:
        # Re-POST the identical event -> idempotent (no new row).
        again = client_db.post(
            "/signals",
            json={"title": f"Port strike test {marker}", "body": "Shipments halted."},
        ).json()
        assert again["persisted"] == 0
        assert again["duplicate"] == 1

        signals = read_new_signals(conn)
        assert any(marker in s.title for s in signals)
        assert all(s.source == "supplier_webhook" for s in signals if marker in s.title)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM signals WHERE title LIKE %s", (f"%{marker}%",))
        conn.commit()
        conn.close()
