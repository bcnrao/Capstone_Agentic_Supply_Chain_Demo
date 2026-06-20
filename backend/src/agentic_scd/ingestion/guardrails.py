"""Input guardrail node.

Sits between ``ingestion_node`` and the downstream agents. For each freshly ingested
signal it revalidates relevance, schema, and basic safety, and **discards** anything
unsafe / off-topic / malformed before the classification node ever sees it — defense in
depth against bad rows reaching the pipeline. Valid signals pass through unchanged.
"""

import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from agentic_scd.ingestion.relevance import is_relevant
from agentic_scd.ingestion.schema import DisruptionSignal

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

logger = logging.getLogger(__name__)

# Coarse safety screen: drop signals whose text contains injection-style control
# phrases. A backstop, not a classifier (recall-favoring like the relevance gate).
UNSAFE_MARKERS = ("ignore previous instructions", "<script", "drop table", "rm -rf")


def is_safe(signal: DisruptionSignal) -> bool:
    """True if the signal text shows no obvious unsafe/injection markers."""
    haystack = f"{signal.title} {signal.raw_text}".lower()
    return not any(marker in haystack for marker in UNSAFE_MARKERS)


def validate_signal(signal: DisruptionSignal) -> bool:
    """Keep/discard one signal: schema-valid AND relevant AND safe."""
    try:
        DisruptionSignal.model_validate(signal.model_dump())
    except ValidationError as exc:
        logger.warning(
            "guardrail discarded malformed signal %s: %s", signal.signal_id, exc
        )
        return False
    if not is_relevant(signal):
        logger.info("guardrail discarded off-topic signal: %s", signal.title)
        return False
    if not is_safe(signal):
        logger.warning("guardrail discarded unsafe signal: %s", signal.title)
        return False
    return True


def input_guardrail_node(state: "GraphState") -> dict:
    """Filter ``new_signals`` down to the valid ones (overwrite reducer)."""
    signals = state.get("new_signals", [])
    kept = [s for s in signals if validate_signal(s)]
    discarded = len(signals) - len(kept)
    if discarded:
        logger.info("input guardrail: passed %d, discarded %d", len(kept), discarded)
    return {"new_signals": kept}
