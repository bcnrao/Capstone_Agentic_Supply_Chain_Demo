"""Normalize: source ``RawItem`` -> canonical ``DisruptionSignal``.

Maps every source's raw format into the one canonical record so everything downstream
sees identical fields. Light consistency fixes only: strip HTML / collapse whitespace,
parse dates to UTC, stamp provenance from the connector, and keep the untouched
original in ``raw_payload``. Runs **before** the relevance gate and dedupe because both
operate on clean text. Categorization/scoring are later phases — not here.
"""

import re
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from agentic_scd.ingestion.connectors.base import Connector, RawItem
from agentic_scd.ingestion.schema import DisruptionSignal, Location

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Strip HTML tags and collapse whitespace; ``None`` -> empty string."""
    if not value:
        return ""
    return WS_RE.sub(" ", TAG_RE.sub(" ", value)).strip()


def parse_utc(value: str | None) -> datetime | None:
    """Best-effort parse of a source timestamp into a UTC-aware ``datetime``.

    Handles RFC-822 (RSS ``pubDate``) and ISO-8601 (weather/JSON). Returns ``None``
    when the value is missing or unparseable — heterogeneous source dates should not
    crash the pipeline.
    """
    if not value:
        return None
    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def extract_location(raw: RawItem) -> Location | None:
    if not raw.location:
        return None
    loc = Location(
        **{k: raw.location.get(k) for k in ("region", "lat", "lon", "hub_port")}
    )
    # Drop an all-empty location so it doesn't masquerade as real geo.
    if loc.model_dump(exclude_none=True):
        return loc
    return None


def normalize(raw: RawItem, connector: Connector) -> DisruptionSignal:
    """Map one ``RawItem`` from ``connector`` into a canonical ``DisruptionSignal``."""
    return DisruptionSignal(
        signal_id=str(uuid.uuid4()),
        source=connector.name,
        source_type=connector.source_type,
        source_reliability=connector.reliability,
        fetched_at=datetime.now(UTC),
        event_time=parse_utc(raw.published),
        title=clean_text(raw.title),
        raw_text=clean_text(raw.body),
        url=raw.url,
        location=extract_location(raw),
        severity_hint=raw.payload.get("severity_hint") if raw.payload else None,
        raw_payload=raw.payload or None,
    )
