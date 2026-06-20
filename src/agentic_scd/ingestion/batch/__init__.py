"""Phase 1c batch loaders — seed historical data into the ``signals`` table.

Each loader reads a **committed** snapshot under ``data/seed/`` and feeds it through the
existing ``normalize -> ingest_signals`` tail (gate -> dedupe -> persist), idempotent on
``dedup_hash``. ``load_batch`` runs the enabled loaders once and tallies the run,
mirroring ``collect``'s ``CollectSummary`` shape. Run via the ``agentic-scd-batch`` CLI.
"""

import logging
from dataclasses import dataclass, field

from agentic_scd.config import Settings, get_settings
from agentic_scd.ingestion.batch import freightos, kaggle
from agentic_scd.ingestion.batch.base import BatchSource, LoaderResult

logger = logging.getLogger(__name__)

# The loaders run, in order, when batch loading is enabled.
LOADERS = (freightos.load, kaggle.load)


@dataclass
class BatchSummary:
    """Outcome of a batch run across all enabled loaders."""

    db_persisted: bool = False
    enabled: bool = True
    results: list[LoaderResult] = field(default_factory=list)

    @property
    def totals(self) -> LoaderResult:
        agg = LoaderResult(name="TOTAL")
        for r in self.results:
            agg.loaded += r.loaded
            agg.kept += r.kept
            agg.dropped += r.dropped
            agg.persisted += r.persisted
        return agg


def load_batch(conn, settings: Settings | None = None) -> BatchSummary:  # noqa: ANN001
    """Run the enabled batch loaders once and return the run summary.

    ``conn`` is a live psycopg connection or ``None`` (offline: snapshots still parse
    and gate, nothing persists). A disabled ``batch_enabled`` is a clean no-op.
    """
    settings = settings or get_settings()
    summary = BatchSummary(
        db_persisted=conn is not None, enabled=settings.batch_enabled
    )
    if not settings.batch_enabled:
        logger.info("batch loaders disabled (BATCH_ENABLED=false) — skipping")
        return summary
    for loader in LOADERS:
        summary.results.append(loader(conn))
    return summary
