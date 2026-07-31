from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from agentic_scd.ingestion.connectors.base import Connector, RawItem
from agentic_scd.ingestion.schema import DisruptionSignal, Location

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


# Region inference -----------------------------------------------------------
# RSS/news connectors have no location field: a headline carries the place name
# in its text, not in metadata. Without this, every news signal lands in the
# heatmap's "Unassigned" bucket and the only regions shown come from weather
# hubs. We resolve place mentions to the SAME city-level vocabulary the network
# KB and weather hubs use, so heatmap columns merge instead of proliferating
# (a story about Nhava Sheva strengthens the existing Mumbai column rather than
# opening a separate country-level "India" one).
REGION_ALIASES: dict[str, str] = {
    # India
    "mumbai": "Mumbai", "bombay": "Mumbai", "nhava sheva": "Mumbai",
    "jnpt": "Mumbai", "jawaharlal nehru": "Mumbai",
    "chennai": "Chennai", "madras": "Chennai", "ennore": "Chennai",
    "kattupalli": "Chennai",
    "kolkata": "Kolkata", "calcutta": "Kolkata", "haldia": "Kolkata",
    "delhi": "Delhi", "new delhi": "Delhi", "ncr": "Delhi",
    "gurugram": "Delhi", "gurgaon": "Delhi", "noida": "Delhi",
    "bangalore": "Bangalore", "bengaluru": "Bangalore",
    # Rest of network
    "shanghai": "Shanghai", "yangshan": "Shanghai", "ningbo": "Shanghai",
    "rotterdam": "Rotterdam", "antwerp": "Rotterdam",
    "los angeles": "Los Angeles", "long beach": "Los Angeles",
    "new york": "New York", "newark": "New York",
    "ho chi minh": "Ho Chi Minh", "saigon": "Ho Chi Minh",
    "singapore": "Singapore",
    "colombo": "Colombo",
    "dubai": "Dubai", "jebel ali": "Dubai",
}


def infer_region(text: str) -> str | None:
    """Best-effort city-level region from free text.

    Longest alias first so "new delhi" wins over "delhi". Returns None when
    nothing matches — callers keep their existing fallback rather than
    inventing a location.
    """
    lowered = text.lower()
    for alias in sorted(REGION_ALIASES, key=len, reverse=True):
        if alias in lowered:
            return REGION_ALIASES[alias]
    return None


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return WS_RE.sub(" ", TAG_RE.sub(" ", value)).strip()


def parse_utc(value: str | None) -> datetime | None:
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
    values = {key: raw.location.get(key) for key in ("region", "lat", "lon", "hub_port")}
    loc = Location(**values)
    return loc if loc.model_dump(exclude_none=True) else None


def _inferred_location(text: str) -> Location | None:
    region = infer_region(text)
    return Location(region=region) if region else None


def normalize(raw: RawItem, connector: Connector) -> DisruptionSignal:
    payload = dict(raw.payload or {})
    title = clean_text(raw.title)
    body = clean_text(raw.body)
    return DisruptionSignal(
        signal_id=str(uuid.uuid4()),
        source=connector.name,
        source_type=connector.source_type,
        source_reliability=connector.reliability,
        fetched_at=datetime.now(UTC),
        event_time=parse_utc(raw.published),
        title=title or "Untitled supply-chain signal",
        raw_text=body,
        url=raw.url,
        # Connector-supplied location wins; otherwise infer from the headline so
        # news signals carry a region instead of falling through as Unassigned.
        location=extract_location(raw) or _inferred_location(f"{title} {body}"),
        severity_hint=payload.get("severity_hint") or payload.get("severity"),
        raw_payload=payload or None,
    )
