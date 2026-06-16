"""Relevance gate — keeps on-topic, drops zero-hit items (Stage 0 + Stage 1)."""

from datetime import UTC, datetime

from agentic_scd.ingestion.relevance import (
    gate,
    is_relevant,
    load_lexicon,
    passes_lexicon,
)
from agentic_scd.ingestion.schema import DisruptionSignal


def make_signal(title: str, body: str = "") -> DisruptionSignal:
    return DisruptionSignal(
        signal_id="x",
        source="stub",
        source_type="RSS",
        fetched_at=datetime.now(UTC),
        title=title,
        raw_text=body,
    )


def test_lexicon_loads() -> None:
    terms = load_lexicon()
    assert "strike" in terms and "tariff" in terms


def test_keeps_on_topic() -> None:
    sig = make_signal("Port strike halts shipments")
    assert passes_lexicon(sig)
    assert is_relevant(sig)


def test_drops_off_topic() -> None:
    sig = make_signal("Local bakery wins regional dessert award")
    assert not passes_lexicon(sig)
    assert not is_relevant(sig)


def test_gate_splits_and_counts() -> None:
    signals = [
        make_signal("Port strike halts shipments"),
        make_signal("Tariff disrupts supplier logistics"),
        make_signal("Cat video goes viral"),
    ]
    kept, dropped = gate(signals)
    assert len(kept) == 2
    assert len(dropped) == 1
    assert dropped[0].title == "Cat video goes viral"
