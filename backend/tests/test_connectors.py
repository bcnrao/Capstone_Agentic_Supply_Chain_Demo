"""Connectors & graceful degradation — fetch failure falls back to fallback().

Fully offline: forces fetch() to raise and asserts the wrapper uses fallback(); the
synthetic connector always yields; RSS/Open-Meteo fallbacks replay the committed
snapshots under data/fallback/.
"""

from agentic_scd.ingestion.connectors.base import RawItem, fetch_with_fallback
from agentic_scd.ingestion.connectors.open_meteo import OpenMeteoConnector
from agentic_scd.ingestion.connectors.rss import RssConnector
from agentic_scd.ingestion.connectors.synthetic import SyntheticConnector
from agentic_scd.ingestion.paths import FALLBACK_DIR


class BoomConnector:
    name = "boom"
    source_type = "RSS"
    reliability = 0.5

    def fetch(self) -> list[RawItem]:
        raise RuntimeError("network down")

    def fallback(self) -> list[RawItem]:
        return [RawItem(title="cached", body="cached body")]


def test_fetch_failure_falls_back() -> None:
    items, path = fetch_with_fallback(BoomConnector())
    assert path == "fallback"
    assert items and items[0].title == "cached"


def test_empty_fetch_falls_back() -> None:
    class Empty(BoomConnector):
        def fetch(self) -> list[RawItem]:
            return []

    items, path = fetch_with_fallback(Empty())
    assert path == "fallback"
    assert len(items) == 1


def test_synthetic_always_yields() -> None:
    conn = SyntheticConnector(name="synthetic", reliability=0.5, count=3)
    items, path = fetch_with_fallback(conn)
    assert path == "live"
    assert len(items) == 3
    assert all(
        "strike" in i.body or "tariff" in i.body or "typhoon" in i.body for i in items
    )


def test_rss_fallback_replays_snapshot() -> None:
    conn = RssConnector(
        name="rss",
        reliability=0.7,
        feeds=[],
        queries=[],
        fallback_path=FALLBACK_DIR / "rss_supplychain.xml",
    )
    items = conn.fallback()
    assert len(items) == 6  # 5 disruption (incl. 2 India/Asia) + 1 off-topic control
    assert any("Port strike" in i.title for i in items)
    assert any("Nhava Sheva" in i.title for i in items)


def test_open_meteo_fallback_replays_snapshot() -> None:
    conn = OpenMeteoConnector(
        name="open_meteo",
        reliability=0.9,
        hubs=[],
        fallback_path=FALLBACK_DIR / "open_meteo_hubs.json",
    )
    items = conn.fallback()
    assert len(items) == 11  # sea/coastal ports across the network KB
    assert items[0].location is not None
    assert items[0].location["hub_port"] == "Port of Shanghai"
