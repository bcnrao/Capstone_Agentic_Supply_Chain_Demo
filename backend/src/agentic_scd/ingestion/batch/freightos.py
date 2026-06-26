"""Freightos Baltic Index batch loader.

Parses the committed ``data/seed/freightos_baltic_index.json`` freight-rate snapshot
into ``RawItem``s, runs them through the shared ``normalize`` step into
``FREIGHT_INDEX`` ``DisruptionSignal``s, then through the existing ``ingest_signals``
tail (gate -> dedupe -> persist). Emits freight-rate baselines (Prophet consumes these
in Phase 5); **persists only, no embedding** (the vector store is Phase 4/7).
"""

import json
import logging

from agentic_scd.ingestion.batch.base import BatchSource, LoaderResult
from agentic_scd.ingestion.connectors.base import RawItem, SourceType
from agentic_scd.ingestion.normalize import normalize
from agentic_scd.ingestion.paths import SEED_DIR
from agentic_scd.ingestion.pipeline import ingest_signals
from agentic_scd.ingestion.schema import DisruptionSignal

logger = logging.getLogger(__name__)

SEED_PATH = SEED_DIR / "freightos_baltic_index.json"

# Cached/batch source descriptor — a freight index is a fairly reliable numeric series.
SOURCE = BatchSource(
    name="freightos_baltic_index",
    source_type=SourceType.FREIGHT_INDEX,
    reliability=0.85,
)


def _to_raw_item(row: dict, unit: str) -> RawItem:
    """Map one freight-rate row into a ``RawItem`` (title carries a lexicon keyword)."""
    lane = row.get("lane", row.get("lane_code", "unknown lane"))
    rate = row.get("rate_usd_feu")
    change = row.get("change_pct")
    title = f"Freight rate baseline: {lane} at ${rate:,} ({unit})"
    body = (
        f"Freightos Baltic Index freight rate for {lane} on {row.get('date')}: "
        f"${rate:,} {unit} (week-over-week change {change:+}%). "
        "Shipping cost baseline for logistics forecasting."
    )
    return RawItem(
        title=title,
        body=body,
        published=row.get("date"),
        payload={"kind": "freight_rate", **row},
    )


def build_signals() -> list[DisruptionSignal]:
    """Parse the committed snapshot into normalized ``FREIGHT_INDEX`` signals."""
    doc = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    unit = doc.get("unit", "USD/FEU")
    return [normalize(_to_raw_item(row, unit), SOURCE) for row in doc.get("rows", [])]


def load(conn) -> LoaderResult:  # noqa: ANN001 — psycopg conn | None
    """Load the Freightos snapshot through the shared ingest tail.

    ``conn`` is a live connection or ``None`` (offline: parsed + gated, nothing
    persisted). Idempotent on ``dedup_hash`` — a second run persists no new rows.
    """
    signals = build_signals()
    result = LoaderResult(name=SOURCE.name, loaded=len(signals))
    ingested = ingest_signals(signals, conn)
    result.kept = ingested.kept
    result.dropped = ingested.dropped
    result.persisted = ingested.persisted
    logger.info(
        "freightos loader: loaded=%d kept=%d dropped=%d persisted=%d",
        result.loaded,
        result.kept,
        result.dropped,
        result.persisted,
    )
    return result
