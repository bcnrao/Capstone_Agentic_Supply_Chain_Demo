"""Shared pieces for the Phase 1c batch loaders.

Batch loaders read a **committed** seed snapshot (``data/seed/``) and feed it through
the *existing* ``normalize -> ingest_signals`` tail — the same path the live Phase 1a/1b
triggers use — so seeded rows dedupe and persist identically. The only batch-specific
bit is the source descriptor: a cached/synthetic stand-in for a live ``Connector`` that
carries just the provenance fields ``normalize`` reads (``name`` / ``source_type`` /
``reliability``). No network, no live ``fetch``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchSource:
    """A cached/batch source descriptor passed to ``normalize``.

    Duck-types the ``Connector`` provenance fields ``normalize`` reads; it has no
    ``fetch``/``fallback`` because batch loaders parse a committed snapshot instead of
    pulling live.
    """

    name: str
    source_type: str
    reliability: float


@dataclass
class LoaderResult:
    """Per-loader tally for one batch run (mirrors ``collect.SourceResult``)."""

    name: str
    loaded: int = 0
    kept: int = 0
    dropped: int = 0
    persisted: int = 0
