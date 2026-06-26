"""Open-Meteo weather connector.

Pulls a daily forecast for each configured hub/port via ``httpx`` (no API key) and
turns disruptive conditions into ``RawItem``s carrying structured ``location``. On
failure the wrapper calls ``fallback``, which replays a cached forecast snapshot
committed under ``data/fallback/``.

Each item's text names the weather condition so the keyword relevance gate keeps the
genuinely disruptive forecasts (storm/gale/flood) and drops calm ones.
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from agentic_scd.ingestion.connectors.base import RawItem, SourceType

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY = "weather_code,wind_speed_10m_max,precipitation_sum"

# WMO weather codes mapped to (condition phrase, severity_hint). Phrases use words in
# the disruption lexicon so severe weather passes the relevance gate.
WMO: dict[int, tuple[str, str]] = {
    0: ("clear sky", "none"),
    1: ("mainly clear", "none"),
    2: ("partly cloudy", "none"),
    3: ("overcast", "none"),
    45: ("fog", "low"),
    51: ("light drizzle", "low"),
    61: ("rain", "low"),
    63: ("heavy rain causing flood risk", "moderate"),
    65: ("heavy rain and flooding disruption", "severe"),
    71: ("snowfall", "moderate"),
    75: ("heavy snow storm", "severe"),
    80: ("rain showers", "low"),
    82: ("violent storm with flooding", "severe"),
    95: ("thunderstorm", "severe"),
    99: ("severe thunderstorm with gale-force wind", "severe"),
}


class OpenMeteoConnector:
    """Daily weather forecast over a configured list of hubs/ports."""

    source_type = SourceType.WEATHER

    def __init__(
        self,
        name: str,
        reliability: float,
        hubs: list[dict[str, Any]],
        fallback_path: Path | None = None,
    ) -> None:
        self.name = name
        self.reliability = reliability
        self.hubs = list(hubs)
        self.fallback_path = fallback_path

    @staticmethod
    def hub_item(hub: dict[str, Any], response: dict[str, Any]) -> RawItem:
        daily = response.get("daily", {})
        code = (daily.get("weather_code") or [0])[0]
        wind = (daily.get("wind_speed_10m_max") or [None])[0]
        precip = (daily.get("precipitation_sum") or [None])[0]
        phrase, hint = WMO.get(int(code), ("unsettled weather", "low"))

        place = hub.get("hub_port") or hub.get("region") or "configured location"
        title = f"Weather forecast for {place}: {phrase}"
        body = (
            f"Forecast {phrase} at {place} "
            f"(max wind {wind} km/h, precipitation {precip} mm). "
            f"Severe conditions may disrupt port and shipping operations."
        )
        return RawItem(
            title=title,
            body=body,
            url=None,
            published=daily.get("time", [None])[0] if daily.get("time") else None,
            location={
                "region": hub.get("region"),
                "lat": hub.get("lat"),
                "lon": hub.get("lon"),
                "hub_port": hub.get("hub_port"),
            },
            payload={"hub": hub, "response": response, "severity_hint": hint},
        )

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        with httpx.Client(timeout=10.0) as client:
            for hub in self.hubs:
                resp = client.get(
                    FORECAST_URL,
                    params={
                        "latitude": hub["lat"],
                        "longitude": hub["lon"],
                        "daily": DAILY,
                        "forecast_days": 1,
                    },
                )
                resp.raise_for_status()
                items.append(self.hub_item(hub, resp.json()))
        return items

    def fallback(self) -> list[RawItem]:
        if not self.fallback_path or not self.fallback_path.exists():
            return []
        snapshot = json.loads(self.fallback_path.read_text(encoding="utf-8"))
        return [self.hub_item(row["hub"], row["response"]) for row in snapshot]
