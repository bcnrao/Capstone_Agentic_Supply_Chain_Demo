"""RSS connector.

Pulls supply-chain feeds plus query-scoped Google News feeds (Stage 0 source
targeting) via ``feedparser``. Live ``fetch`` parses each configured feed URL; on
failure the ``fetch_with_fallback`` wrapper calls ``fallback``, which replays a cached
feed snapshot committed under ``data/fallback/`` so an offline run still yields items.
"""

import logging
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import httpx

from agentic_scd.ingestion.connectors.base import RawItem, SourceType

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)
# Bound every live feed read so a slow/unreachable feed degrades to fallback instead
# of blocking forever (feedparser.parse(url) has no socket timeout of its own).
FETCH_TIMEOUT = 8.0


class RssConnector:
    """Supply-chain + query-scoped Google News RSS feeds."""

    source_type = SourceType.RSS

    def __init__(
        self,
        name: str,
        reliability: float,
        feeds: list[str],
        queries: list[str],
        fallback_path: Path | None = None,
    ) -> None:
        self.name = name
        self.reliability = reliability
        self.feeds = list(feeds)
        self.queries = list(queries)
        self.fallback_path = fallback_path

    def feed_urls(self) -> list[str]:
        urls = list(self.feeds)
        urls += [GOOGLE_NEWS_RSS.format(query=quote_plus(q)) for q in self.queries]
        return urls

    @staticmethod
    def entries_to_items(parsed: feedparser.FeedParserDict) -> list[RawItem]:
        items: list[RawItem] = []
        for entry in parsed.get("entries", []):
            items.append(
                RawItem(
                    title=entry.get("title", ""),
                    body=entry.get("summary", "") or entry.get("description", ""),
                    url=entry.get("link"),
                    published=entry.get("published") or entry.get("updated"),
                    payload=dict(entry),
                )
            )
        return items

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
            for url in self.feed_urls():
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    # Slow/unreachable feed — let other feeds contribute; the wrapper
                    # falls back only if *nothing* was collected across all feeds.
                    logger.warning(
                        "rss %s: fetch failed for %s (%s)", self.name, url, exc
                    )
                    continue
                parsed = feedparser.parse(resp.content)
                if parsed.get("bozo") and not parsed.get("entries"):
                    logger.warning("rss %s: feed parse issue for %s", self.name, url)
                    continue
                items.extend(self.entries_to_items(parsed))
        return items

    def fallback(self) -> list[RawItem]:
        if not self.fallback_path or not self.fallback_path.exists():
            return []
        parsed = feedparser.parse(self.fallback_path.read_bytes())
        return self.entries_to_items(parsed)
