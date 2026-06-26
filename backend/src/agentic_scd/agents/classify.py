"""Classify stub — rule/keyword disruption category + risk score, per signal.

The simplest real thing: match the normalized text against a small category lexicon,
pick the best-matching category, and derive a bounded risk score from keyword hits
and the source reliability. Phase 3 replaces this with Groq classification/extraction
plus a fine-tuned DistilBERT risk score behind the same ``classify_node`` signature.
"""

from typing import TYPE_CHECKING

from agentic_scd.agents.schema import Classification
from agentic_scd.ingestion.schema import DisruptionSignal

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

# Coarse disruption categories -> indicative keywords (deepened in Phase 3).
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "labor": ("strike", "walkout", "union", "halt"),
    "natural_disaster": (
        "typhoon",
        "hurricane",
        "earthquake",
        "flood",
        "storm",
        "wildfire",
        "gale",
    ),
    "logistics": (
        "port",
        "congestion",
        "shipping",
        "freight",
        "blockade",
        "delay",
        "backlog",
    ),
    "policy": ("tariff", "embargo", "sanction", "ban"),
    "supply": ("shortage", "recall", "shutdown", "closure", "outage", "disrupt"),
}
DEFAULT_CATEGORY = "other"


def classify_signal(signal: DisruptionSignal) -> Classification:
    """Best-matching category + a bounded risk score for one signal."""
    text = f"{signal.title} {signal.raw_text}".lower()
    hits = {
        category: sum(term in text for term in terms)
        for category, terms in CATEGORY_KEYWORDS.items()
    }
    best = max(hits, key=lambda c: hits[c])
    total_hits = hits[best]
    if total_hits == 0:
        best = DEFAULT_CATEGORY

    reliability = (
        signal.source_reliability if signal.source_reliability is not None else 0.5
    )
    # More keyword hits + a more reliable source -> higher risk; clamp to [0, 1].
    raw = (0.3 + 0.15 * total_hits) * (0.5 + 0.5 * reliability)
    risk_score = round(min(1.0, raw), 4)

    rationale = (
        f"{total_hits} '{best}' keyword hit(s)"
        if total_hits
        else "no category keywords"
    )
    return Classification(
        signal_id=signal.signal_id,
        category=best,
        risk_score=risk_score,
        rationale=rationale,
    )


def classify_node(state: "GraphState") -> dict:
    """Classify every signal in this run's batch."""
    signals = state.get("new_signals", [])
    return {"classifications": [classify_signal(s) for s in signals]}
