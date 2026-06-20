"""Webhook endpoint — accept / drop / graceful-no-DB, offline (FastAPI TestClient).

Uses settings with ``database_url=None`` so ``open_connection`` returns None instantly
(no DB, no 5s connect timeout) and the scheduler disabled so no background thread runs.
"""

import pytest
from fastapi.testclient import TestClient

from agentic_scd.config.settings import Settings
from agentic_scd.ingestion.service import create_app
from agentic_scd.ingestion.webhook import WebhookEvent, webhook_source


def offline_settings() -> Settings:
    return Settings(
        groq_api_key=None,
        groq_model="unused",
        use_mock_llm=True,
        database_url=None,
        ingest_scheduler_enabled=False,
    )


@pytest.fixture
def client():
    with TestClient(create_app(offline_settings())) as c:
        yield c


def test_health_offline(client) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["scheduler_running"] is False  # disabled in test settings
    assert body["db_reachable"] is False  # no DB configured


def test_webhook_accepts_on_topic_event(client) -> None:
    resp = client.post(
        "/signals",
        json={"title": "Port strike halts shipments", "body": "Operations stopped."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kept"] == 1
    assert body["dropped"] == 0
    assert body["persisted"] == 0  # graceful: no DB
    assert body["persisted_to_db"] is False


def test_webhook_drops_off_topic_event(client) -> None:
    resp = client.post(
        "/signals",
        json={"title": "Local bakery wins dessert award", "body": "Sweet news."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kept"] == 0
    assert body["dropped"] == 1


def test_webhook_requires_title(client) -> None:
    # title is required by the WebhookEvent model -> 422 validation error.
    assert client.post("/signals", json={"body": "no title"}).status_code == 422


def test_event_maps_to_raw_item_and_provenance() -> None:
    event = WebhookEvent(title="Port closure", body="Closed", payload={"k": "v"})
    raw = event.to_raw_item()
    assert raw.title == "Port closure"
    assert raw.payload["k"] == "v"
    assert "webhook_event" in raw.payload  # original kept for audit
    source = webhook_source(offline_settings())
    assert source.name == "supplier_webhook"
    assert source.source_type == "WEBHOOK"
    assert source.reliability == 0.6
