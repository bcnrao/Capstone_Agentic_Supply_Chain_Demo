from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from agentic_scd.ingestion.connectors.base import Connector, SourceType
from agentic_scd.ingestion.connectors.freight import FreightIndexConnector
from agentic_scd.ingestion.connectors.open_meteo import OpenMeteoConnector
from agentic_scd.ingestion.connectors.rss import RssConnector
from agentic_scd.ingestion.connectors.synthetic import SyntheticConnector
from agentic_scd.ingestion.paths import ASSET_DIR, PROJECT_ROOT, sources_yaml_path


def resolve_path(rel: str | None) -> Path | None:
    if not rel:
        return None
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    asset_candidate = ASSET_DIR / candidate
    trimmed_asset = ASSET_DIR / Path(*candidate.parts[1:]) if candidate.parts and candidate.parts[0] == "data" else asset_candidate
    for path in (Path.cwd() / candidate, PROJECT_ROOT / candidate, asset_candidate, trimmed_asset):
        if path.exists():
            return path
    return trimmed_asset


def build_rss(entry: dict[str, Any]) -> RssConnector:
    cfg = entry.get("config", {})
    return RssConnector(entry["name"], entry["reliability"], cfg.get("feeds", []), cfg.get("queries", []), resolve_path(entry.get("fallback_path")))


def build_open_meteo(entry: dict[str, Any]) -> OpenMeteoConnector:
    cfg = entry.get("config", {})
    return OpenMeteoConnector(
        entry["name"],
        entry["reliability"],
        cfg.get("hubs", []),
        resolve_path(entry.get("fallback_path")),
        forecast_days=cfg.get("forecast_days", 7),
    )


def build_synthetic(entry: dict[str, Any]) -> SyntheticConnector:
    cfg = entry.get("config", {})
    return SyntheticConnector(entry["name"], entry["reliability"], cfg.get("count", 3))


def build_freight(entry: dict[str, Any]) -> FreightIndexConnector:
    cfg = entry.get("config", {})
    return FreightIndexConnector(entry["name"], entry["reliability"], cfg.get("url"), resolve_path(entry.get("fallback_path")))


BUILDERS: dict[str, Callable[[dict[str, Any]], Connector]] = {
    SourceType.RSS: build_rss,
    SourceType.WEATHER: build_open_meteo,
    SourceType.SYNTHETIC: build_synthetic,
}


def load_registry(path: str | Path | None = None) -> list[Connector]:
    registry_path = Path(path) if path else sources_yaml_path()
    doc = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    connectors: list[Connector] = []
    declared_types = {entry.get("type") for entry in doc.get("sources", [])}
    for entry in doc.get("sources", []):
        if not entry.get("enabled", True):
            continue
        builder = BUILDERS.get(entry["type"]) or (build_freight if entry["type"] == SourceType.FREIGHT_INDEX else None)
        if builder is None:
            raise ValueError(f"unknown source type {entry['type']!r}")
        connectors.append(builder(entry))
    if SourceType.FREIGHT_INDEX not in declared_types and not any(getattr(connector, "source_type", "") == SourceType.FREIGHT_INDEX for connector in connectors):
        connectors.append(
            build_freight(
                {
                    "name": "freight_index",
                    "reliability": 0.85,
                    "config": {},
                    "fallback_path": "data/seed/freightos_baltic_index.json",
                }
            )
        )
    return connectors
