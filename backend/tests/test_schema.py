"""Schema completion — Phase 1 ingestion fields + SCHEMA_VERSION bump."""

from datetime import UTC, datetime

from agentic_scd.ingestion.schema import SCHEMA_VERSION, DisruptionSignal, Location


def test_schema_version_is_v2() -> None:
    assert SCHEMA_VERSION == 2


def test_new_ingestion_fields_present_and_optional() -> None:
    sig = DisruptionSignal(
        signal_id="x",
        source="stub",
        source_type="RSS",
        fetched_at=datetime.now(UTC),
        title="Port strike",
    )
    # New ingestion-filled fields exist and default to None.
    assert sig.dedup_hash is None
    assert sig.source_reliability is None
    assert sig.raw_payload is None
    assert sig.location is None
    assert sig.severity_hint is None
    assert sig.schema_version == SCHEMA_VERSION
    # Later-phase fields remain null at ingestion.
    assert sig.category is None and sig.severity is None
    assert sig.affected_entities is None


def test_location_nested_model() -> None:
    sig = DisruptionSignal(
        signal_id="x",
        source="stub",
        source_type="WEATHER",
        fetched_at=datetime.now(UTC),
        title="Storm",
        location=Location(
            region="China", lat=31.23, lon=121.47, hub_port="Port of Shanghai"
        ),
        raw_payload={"k": "v"},
    )
    assert isinstance(sig.location, Location)
    assert sig.location.hub_port == "Port of Shanghai"
    # Round-trips through dict (the persistence path uses model_dump).
    assert DisruptionSignal.model_validate(sig.model_dump()).location.lat == 31.23
