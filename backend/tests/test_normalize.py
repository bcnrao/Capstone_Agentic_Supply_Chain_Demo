"""Normalize stage — RSS item and Open-Meteo payload -> valid DisruptionSignal.

Fully offline: builds RawItems directly (no network, no DB).
"""

from datetime import UTC

from agentic_scd.ingestion.connectors.base import RawItem, SourceType
from agentic_scd.ingestion.normalize import clean_text, normalize, parse_utc
from agentic_scd.ingestion.schema import DisruptionSignal


class StubConnector:
    name = "stub_rss"
    source_type = SourceType.RSS
    reliability = 0.7

    def fetch(self):  # pragma: no cover - unused here
        return []

    def fallback(self):  # pragma: no cover - unused here
        return []


def test_clean_text_strips_html_and_whitespace() -> None:
    assert clean_text("<p>Port   strike\n\nhalts</p>") == "Port strike halts"
    assert clean_text(None) == ""


def test_parse_utc_handles_rfc822_and_iso() -> None:
    rfc = parse_utc("Mon, 09 Jun 2026 08:00:00 GMT")
    iso = parse_utc("2026-06-10")
    assert rfc is not None and rfc.tzinfo == UTC
    assert iso is not None and iso.tzinfo == UTC
    assert parse_utc(None) is None
    assert parse_utc("not a date") is None


def test_normalize_rss_item() -> None:
    raw = RawItem(
        title="<b>Port strike</b> halts shipments",
        body="<p>A   labor strike has stopped operations.</p>",
        url="https://example.com/a",
        published="Mon, 09 Jun 2026 08:00:00 GMT",
        payload={"foo": "bar"},
    )
    signal = normalize(raw, StubConnector())
    assert isinstance(signal, DisruptionSignal)
    assert signal.title == "Port strike halts shipments"
    assert signal.raw_text == "A labor strike has stopped operations."
    assert signal.source == "stub_rss"
    assert signal.source_type == "RSS"
    assert signal.source_reliability == 0.7
    assert signal.event_time is not None and signal.event_time.tzinfo == UTC
    assert signal.fetched_at.tzinfo == UTC
    assert signal.raw_payload == {"foo": "bar"}  # original kept untouched


def test_normalize_weather_payload_keeps_location_and_hint() -> None:
    raw = RawItem(
        title="Weather forecast for Port of Shanghai: severe thunderstorm",
        body="Forecast severe thunderstorm at Port of Shanghai.",
        location={
            "region": "China",
            "lat": 31.23,
            "lon": 121.47,
            "hub_port": "Port of Shanghai",
        },
        payload={"severity_hint": "severe"},
    )
    conn = StubConnector()
    conn.source_type = SourceType.WEATHER
    signal = normalize(raw, conn)
    assert signal.location is not None
    assert signal.location.hub_port == "Port of Shanghai"
    assert signal.location.lat == 31.23
    assert signal.severity_hint == "severe"
