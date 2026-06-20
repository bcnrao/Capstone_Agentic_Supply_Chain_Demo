"""Dedupe — exact SHA-256 over normalized title + body."""

from datetime import UTC, datetime

from agentic_scd.ingestion.dedupe import assign_hash
from agentic_scd.ingestion.schema import DisruptionSignal


def make_signal(title: str, body: str) -> DisruptionSignal:
    return DisruptionSignal(
        signal_id="x",
        source="stub",
        source_type="RSS",
        fetched_at=datetime.now(UTC),
        title=title,
        raw_text=body,
    )


def test_identical_text_same_hash() -> None:
    a = make_signal("Port strike", "Shipments halted")
    b = make_signal("Port strike", "Shipments halted")
    assert assign_hash(a).dedup_hash == assign_hash(b).dedup_hash


def test_differing_text_different_hash() -> None:
    a = make_signal("Port strike", "Shipments halted")
    b = make_signal("Port strike", "Shipments resumed")
    assert assign_hash(a).dedup_hash != assign_hash(b).dedup_hash


def test_assign_hash_populates_field() -> None:
    sig = make_signal("Tariff", "Logistics disrupted")
    assert sig.dedup_hash is None
    returned = assign_hash(sig)
    assert returned is sig  # stamps in place and returns the same signal
    assert sig.dedup_hash is not None and len(sig.dedup_hash) == 64  # sha256 hex
