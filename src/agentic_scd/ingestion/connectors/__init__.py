"""Source connectors (the adapter pattern).

Every source — live or cached — implements the one ``Connector`` interface from
``base`` so the pipeline treats them uniformly and new sources are drop-in. The
concrete connectors for this slice are RSS, Open-Meteo weather, and a synthetic
generator (see specs/data-ingestion.md).
"""

from agentic_scd.ingestion.connectors.base import (
    Connector,
    RawItem,
    SourceType,
    fetch_with_fallback,
)

__all__ = ["Connector", "RawItem", "SourceType", "fetch_with_fallback"]
