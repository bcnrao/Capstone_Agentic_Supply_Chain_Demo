"""Ingestion layer.

Phase 0 ships only the shared ``DisruptionSignal`` schema and a stub LangGraph
node. Phase 1 fills in connectors, normalization, the relevance gate, dedupe and
SQLite persistence (see specs/data-ingestion.md).
"""

from agentic_scd.ingestion.schema import (
    SCHEMA_VERSION,
    DisruptionSignal,
    Location,
)
