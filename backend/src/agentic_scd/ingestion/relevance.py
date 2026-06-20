"""Relevance gate — Stage 0 (source targeting) + Stage 1 (keyword lexicon).

A cheap, deterministic funnel that drops obvious noise **before** persistence so the
DB stays free of irrelevant news. Two free stages only (Stage 2 DistilBERT is Phase 3):

- **Stage 0 — source targeting.** Connectors are pre-targeted (supply-chain feeds,
  query-scoped news) and toggled in ``sources.yaml``, so an enabled source passes.
- **Stage 1 — keyword lexicon.** Match normalized title+body against ``lexicon.yaml``;
  zero hits -> drop.

Favors recall: dropping a real disruption is worse than keeping some noise, so the
match is loose and the drop rate is logged. Raw pulls are snapshotted outside the DB,
so an over-aggressive lexicon is recoverable by re-running with looser terms.
"""

import logging
from functools import lru_cache
from pathlib import Path

import yaml

from agentic_scd.ingestion.paths import LEXICON_YAML
from agentic_scd.ingestion.schema import DisruptionSignal

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def load_lexicon(path: str | Path | None = None) -> tuple[str, ...]:
    """Load and cache the lowercased disruption keyword list."""
    lexicon_path = Path(path) if path else LEXICON_YAML
    doc = yaml.safe_load(lexicon_path.read_text(encoding="utf-8")) or {}
    return tuple(str(k).lower() for k in doc.get("keywords", []))


def source_allowed(source: str | None) -> bool:
    """Stage 0: a signal from an enabled, targeted source passes (config-driven).

    Sources are gated by ``enabled`` in ``sources.yaml`` before they ever produce
    signals, so by the time a signal reaches the gate its source is allowed.
    """
    return bool(source)


def passes_lexicon(
    signal: DisruptionSignal, lexicon: tuple[str, ...] | None = None
) -> bool:
    """Stage 1: True if the normalized title+body contains any lexicon keyword."""
    terms = lexicon if lexicon is not None else load_lexicon()
    haystack = f"{signal.title} {signal.raw_text}".lower()
    return any(term in haystack for term in terms)


def is_relevant(
    signal: DisruptionSignal, lexicon: tuple[str, ...] | None = None
) -> bool:
    """Combined Stage 0 + Stage 1 keep/drop decision for one signal."""
    return source_allowed(signal.source) and passes_lexicon(signal, lexicon)


def gate(
    signals: list[DisruptionSignal], lexicon: tuple[str, ...] | None = None
) -> tuple[list[DisruptionSignal], list[DisruptionSignal]]:
    """Split a batch into ``(kept, dropped)`` and log the drop rate + sample rejects."""
    terms = lexicon if lexicon is not None else load_lexicon()
    kept: list[DisruptionSignal] = []
    dropped: list[DisruptionSignal] = []

    for signal in signals:
        if is_relevant(signal, terms):
            kept.append(signal)
        else:
            dropped.append(signal)

    total = len(signals)
    if total:
        rate = len(dropped) / total
        logger.info(
            "relevance gate: kept %d / dropped %d (drop rate %.0f%%)",
            len(kept),
            len(dropped),
            rate * 100,
        )
        for sample in dropped[:3]:
            logger.debug("relevance gate dropped: %s", sample.title)
    return kept, dropped
