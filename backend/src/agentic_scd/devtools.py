"""Developer helpers for the Phase 2.5 interactive notebooks.

Small conveniences so the notebooks under ``notebooks/`` can build a representative
``GraphState`` and check DB availability without copy-pasting fixtures. This module is
**not** imported by the runtime pipeline — it exists purely for the dev notebooks
(see specs/2026-06-20-dev-notebooks). It reuses the same synthetic-connector +
normalize path the seed node uses, so the records are shaped exactly like real
ingested signals.
"""

from agentic_scd.db import ping
from agentic_scd.db.client import PingResult
from agentic_scd.ingestion.connectors.synthetic import SyntheticConnector
from agentic_scd.ingestion.normalize import normalize
from agentic_scd.ingestion.schema import DisruptionSignal


def sample_signals(
    count: int = 2, *, reliability: float = 0.6
) -> list[DisruptionSignal]:
    """Return ``count`` normalized synthetic ``DisruptionSignal`` records.

    Ideal for driving a single agent node in isolation, fully offline and with no DB —
    the records carry the same fields a real ingested signal would.
    """
    connector = SyntheticConnector(
        name="notebook_sample", reliability=reliability, count=count
    )
    return [normalize(item, connector) for item in connector.fetch()]


def sample_state(count: int = 2, *, reliability: float = 0.6) -> dict:
    """A minimal ``GraphState`` carrying a batch of sample signals (``new_signals``)."""
    return {"new_signals": sample_signals(count, reliability=reliability)}


def db_status() -> PingResult:
    """Connectivity check for a notebook's 'ensure the DB is up' snippet.

    Thin pass-through to :func:`agentic_scd.db.ping`: returns a falsey ``PingResult``
    with a human-readable ``detail`` when the DB is not configured/reachable (never
    raises), so a notebook can decide to use the live DB or fall back to sample state.
    """
    return ping()
