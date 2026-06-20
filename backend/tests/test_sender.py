"""Synthetic sender builds valid webhook events (offline; no server needed)."""

import sys

sys.path.insert(0, "scripts")

import send_synthetic_event  # noqa: E402 — scripts/ runner, imported for unit test

from agentic_scd.ingestion.webhook import WebhookEvent  # noqa: E402


def test_events_are_valid_disruption_payloads() -> None:
    events = send_synthetic_event.events()
    assert len(events) == 3
    assert all(isinstance(e, WebhookEvent) for e in events)
    assert all(e.title for e in events)  # title is required
    text = " ".join(f"{e.title} {e.body}" for e in events).lower()
    assert any(term in text for term in ("strike", "typhoon", "tariff"))


def test_base_url_prefers_argv() -> None:
    assert send_synthetic_event.base_url(["prog", "http://h:9/"]) == "http://h:9"
