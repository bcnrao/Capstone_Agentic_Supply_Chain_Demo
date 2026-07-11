from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from agentic_scd.ingestion.connectors.base import RawItem, SourceType
from agentic_scd.ingestion.weather.core import (
    DAILY,
    WMO,
    parse_daily_series,
    peak_day,
    summarize_hub_forecast,
)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_FORECAST_DAYS = 7

__all__ = ["FORECAST_URL", "DAILY", "WMO", "OpenMeteoConnector"]


class OpenMeteoConnector:
    source_type = SourceType.WEATHER

    def __init__(
        self,
        name: str,
        reliability: float,
        hubs: list[dict[str, Any]],
        fallback_path: Path | None = None,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
    ) -> None:
        self.name = name
        self.reliability = reliability
        self.hubs = list(hubs)
        self.fallback_path = fallback_path
        self.forecast_days = forecast_days

    @staticmethod
    def hub_item(hub: dict[str, Any], response: dict[str, Any]) -> RawItem:
        days = parse_daily_series(hub, response)
        peak = peak_day(days)
        phrase = peak.phrase if peak else "unsettled weather"
        hint = peak.severity_hint if peak else "low"
        place = hub.get("hub_port") or hub.get("region") or "configured hub"
        body = summarize_hub_forecast(hub, days)
        if hint in {"moderate", "severe"}:
            body += " Conditions may disrupt port and shipping operations."
        return RawItem(
            title=f"Weather forecast for {place}: {phrase}",
            body=body,
            published=days[0].date if days else None,
            location={"region": hub.get("region"), "lat": hub.get("lat"), "lon": hub.get("lon"), "hub_port": hub.get("hub_port")},
            payload={"hub": hub, "response": response, "severity_hint": hint, "horizon_days": len(days)},
        )

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        with httpx.Client(timeout=10.0) as client:
            for hub in self.hubs:
                response = client.get(
                    FORECAST_URL,
                    params={"latitude": hub["lat"], "longitude": hub["lon"], "daily": DAILY, "forecast_days": self.forecast_days},
                )
                response.raise_for_status()
                items.append(self.hub_item(hub, response.json()))
        return items

    def fallback(self) -> list[RawItem]:
        if not self.fallback_path or not self.fallback_path.exists():
            return []
        snapshot = json.loads(self.fallback_path.read_text(encoding="utf-8"))
        return [self.hub_item(row["hub"], row["response"]) for row in snapshot]
