"""Load the source registry (``sources.yaml``) into live connector instances.

Sources are toggled by config, not code: ``load_registry`` reads the YAML, skips
disabled entries, and instantiates the connector class for each ``type``. New source
types are registered by adding a builder to ``BUILDERS``.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from agentic_scd.ingestion.connectors.base import Connector, SourceType
from agentic_scd.ingestion.connectors.open_meteo import OpenMeteoConnector
from agentic_scd.ingestion.connectors.rss import RssConnector
from agentic_scd.ingestion.connectors.synthetic import SyntheticConnector
from agentic_scd.ingestion.paths import REPO_ROOT, SOURCES_YAML


def build_rss(entry: dict[str, Any]) -> RssConnector:
    cfg = entry.get("config", {})
    return RssConnector(
        name=entry["name"],
        reliability=entry["reliability"],
        feeds=cfg.get("feeds", []),
        queries=cfg.get("queries", []),
        fallback_path=resolve_path(entry.get("fallback_path")),
    )


def build_open_meteo(entry: dict[str, Any]) -> OpenMeteoConnector:
    cfg = entry.get("config", {})
    return OpenMeteoConnector(
        name=entry["name"],
        reliability=entry["reliability"],
        hubs=cfg.get("hubs", []),
        fallback_path=resolve_path(entry.get("fallback_path")),
    )


def build_synthetic(entry: dict[str, Any]) -> SyntheticConnector:
    cfg = entry.get("config", {})
    return SyntheticConnector(
        name=entry["name"],
        reliability=entry["reliability"],
        count=cfg.get("count", 3),
    )


BUILDERS: dict[str, Callable[[dict[str, Any]], Connector]] = {
    SourceType.RSS: build_rss,
    SourceType.WEATHER: build_open_meteo,
    SourceType.SYNTHETIC: build_synthetic,
}


def resolve_path(rel: str | None) -> Path | None:
    """Resolve a registry path (relative to the repo root) to an absolute path."""
    if not rel:
        return None
    candidate = Path(rel)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def load_registry(path: str | Path | None = None) -> list[Connector]:
    """Return the enabled connectors described by ``sources.yaml``.

    Args:
        path: Override the registry file (defaults to the repo-root ``sources.yaml``).

    Raises:
        ValueError: if an enabled entry names an unknown ``type``.
    """
    registry_path = Path(path) if path else SOURCES_YAML
    doc = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}

    connectors: list[Connector] = []
    for entry in doc.get("sources", []):
        if not entry.get("enabled", True):
            continue
        source_type = entry["type"]
        builder = BUILDERS.get(source_type)
        if builder is None:
            raise ValueError(
                f"unknown source type {source_type!r} for connector "
                f"{entry.get('name')!r} (known: {sorted(BUILDERS)})"
            )
        connectors.append(builder(entry))
    return connectors
