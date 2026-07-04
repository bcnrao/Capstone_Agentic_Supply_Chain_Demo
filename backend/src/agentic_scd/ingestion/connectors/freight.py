from __future__ import annotations

import json
from pathlib import Path

import httpx

from agentic_scd.ingestion.connectors.base import RawItem, SourceType


def lane_region(lane: str) -> str:
    lowered = lane.lower()
    if "north america" in lowered:
        return "North America"
    if "europe" in lowered or "mediterranean" in lowered:
        return "Europe"
    if "asia" in lowered or "china" in lowered:
        return "Asia"
    return "Global"


class FreightIndexConnector:
    source_type = SourceType.FREIGHT_INDEX

    def __init__(self, name: str, reliability: float, url: str | None = None, fallback_path: Path | None = None) -> None:
        self.name = name
        self.reliability = reliability
        self.url = url
        self.fallback_path = fallback_path

    @staticmethod
    def build_item(row: dict, unit: str) -> RawItem:
        lane = row.get("lane", row.get("lane_code", "freight lane"))
        rate = row.get("rate_usd_feu", 0)
        change = float(row.get("change_pct", 0.0))
        if change >= 5:
            hint = "high"
        elif change >= 2:
            hint = "moderate"
        else:
            hint = "low"
        title = f"Freight index update for {lane}"
        body = f"Freight pricing on {lane} is {rate} {unit} with a {change:+.1f}% move. Shipping cost pressure may change disruption exposure and logistics plans."
        return RawItem(
            title=title,
            body=body,
            published=row.get("date"),
            location={"region": lane_region(lane)},
            payload={"kind": "freight_rate", "severity_hint": hint, **row},
        )

    def parse(self, doc: dict) -> list[RawItem]:
        unit = doc.get("unit", "USD/FEU")
        return [self.build_item(row, unit) for row in doc.get("rows", [])]

    def fetch(self) -> list[RawItem]:
        if not self.url:
            return self.fallback()
        response = httpx.get(self.url, timeout=10.0)
        response.raise_for_status()
        return self.parse(response.json())

    def fallback(self) -> list[RawItem]:
        if not self.fallback_path or not self.fallback_path.exists():
            return []
        return self.parse(json.loads(self.fallback_path.read_text(encoding="utf-8")))
