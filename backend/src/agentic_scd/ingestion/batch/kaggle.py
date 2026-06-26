"""Kaggle SupplyChainNet batch loader.

Parses the committed ``data/seed/kaggle_supplychainnet.json`` extract into ``RawItem``s
and runs them through the shared ``normalize -> ingest_signals`` tail as ``DATASET``
``DisruptionSignal``s. Two record kinds land:

- ``demand`` — historical demand-baseline time-series (Prophet reads these in Phase 5).
- ``disruption`` — historical KB-history text records.

Both are **persisted only** here (Postgres + snapshot files); the embed-and-index step
belongs to Phase 4/7, which read what 1c persists (see specs vector-DB boundary).
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

SEED_PATH = SEED_DIR / "kaggle_supplychainnet.json"

# Cached/batch source descriptor — historical dataset, moderately reliable.
SOURCE = BatchSource(
    name="kaggle_supplychainnet",
    source_type=SourceType.DATASET,
    reliability=0.7,
)


def _demand_raw_item(rec: dict) -> RawItem:
    region = rec.get("region", "unknown region")
    category = rec.get("product_category", "goods")
    units = rec.get("demand_units")
    title = f"Demand baseline: {category} in {region} ({units:,} units)"
    body = rec.get("description", "") or (
        f"Historical supply chain demand baseline for {category} in {region}."
    )
    return RawItem(
        title=title,
        body=body,
        published=rec.get("date"),
        payload={"kind": "demand", **rec},
    )


def _disruption_raw_item(rec: dict) -> RawItem:
    region = rec.get("region", "unknown region")
    dtype = rec.get("disruption_type", "disruption")
    title = f"Historical disruption: {dtype} in {region}"
    body = rec.get("description", "") or f"{dtype} affecting the {region} supply chain."
    return RawItem(
        title=title,
        body=body,
        published=rec.get("date"),
        payload={"kind": "disruption", **rec},
    )


def _to_raw_item(rec: dict) -> RawItem:
    """Map one record into a ``RawItem`` by its ``kind`` (demand vs disruption)."""
    if rec.get("kind") == "demand":
        return _demand_raw_item(rec)
    return _disruption_raw_item(rec)


def build_signals() -> list[DisruptionSignal]:
    """Parse the committed extract into normalized ``DATASET`` signals (no DB)."""
    doc = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return [normalize(_to_raw_item(rec), SOURCE) for rec in doc.get("records", [])]


def load(conn) -> LoaderResult:  # noqa: ANN001 — psycopg conn | None
    """Load the SupplyChainNet extract through the shared ingest tail.

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
        "kaggle loader: loaded=%d kept=%d dropped=%d persisted=%d",
        result.loaded,
        result.kept,
        result.dropped,
        result.persisted,
    )
    return result
