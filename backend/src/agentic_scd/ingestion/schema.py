"""The canonical ``DisruptionSignal`` schema shared across all agents.

Phase 0 defines only the **neutral, ingestion-filled** fields. Fields owned by
later phases (``category``/``severity`` in Phase 3, ``affected_entities`` in
Phase 4) are declared now as ``Optional`` and default to ``None`` so the model is
stable across migrations. ``schema_version`` is present from the start for
migration safety. Full field rationale lives in specs/data-ingestion.md.
"""

from datetime import datetime

from pydantic import BaseModel, Field

# Bump when the stored shape of DisruptionSignal changes (migration safety).
# v2 (Phase 1): adds dedup_hash, source_reliability, raw_payload, location,
# severity_hint — the remaining ingestion-filled fields.
SCHEMA_VERSION = 2


class Location(BaseModel):
    """Where a signal applies, when a source provides it (weather has it; news
    often does not). All fields optional — a signal may carry none of them."""

    region: str | None = Field(default=None, description="Free-text region/area.")
    lat: float | None = Field(default=None, description="Latitude (decimal degrees).")
    lon: float | None = Field(default=None, description="Longitude (decimal degrees).")
    hub_port: str | None = Field(
        default=None, description="Named hub/port, e.g. 'Port of Shanghai'."
    )


class DisruptionSignal(BaseModel):
    """One normalized disruption record every connector maps into."""

    # --- Identity & provenance (ingestion) ---------------------------------
    signal_id: str = Field(..., description="UUID or content hash for the signal.")
    dedup_hash: str | None = Field(
        default=None,
        description="sha256 of normalized title+body; set by the dedupe stage.",
    )
    source: str = Field(..., description="Connector name, e.g. 'reuters_rss'.")
    source_type: str = Field(
        ..., description="RSS | WEATHER | FREIGHT_INDEX | DATASET | SYNTHETIC."
    )
    source_reliability: float | None = Field(
        default=None, description="0–1 reliability prior of the source."
    )

    # --- Timing (ingestion) ------------------------------------------------
    fetched_at: datetime = Field(..., description="When the item was fetched (UTC).")
    event_time: datetime | None = Field(
        default=None, description="Published/forecast time of the event (UTC)."
    )

    # --- Content (ingestion) ----------------------------------------------
    title: str = Field(..., description="Normalized headline/title.")
    raw_text: str = Field(default="", description="Normalized body text.")
    url: str | None = Field(default=None, description="Source URL, if any.")

    # --- Location & neutral hints (ingestion, when available) --------------
    location: Location | None = Field(
        default=None, description="Where the signal applies, if the source gives it."
    )
    severity_hint: str | None = Field(
        default=None,
        description="Neutral source hint (e.g. weather 'severe'); not a score.",
    )

    # --- Audit / replay (ingestion) ---------------------------------------
    raw_payload: dict | None = Field(
        default=None, description="Untouched original record, kept for audit/replay."
    )

    # --- Migration safety --------------------------------------------------
    schema_version: int = Field(
        default=SCHEMA_VERSION,
        description="Schema version this record was written with.",
    )

    # --- Filled by later phases (null at ingestion) ------------------------
    category: str | None = Field(
        default=None, description="Disruption category (Phase 3)."
    )
    severity: float | None = Field(
        default=None, description="Severity score (Phase 3)."
    )
    affected_entities: list[str] | None = Field(
        default=None, description="Impacted suppliers/lanes/facilities (Phase 4)."
    )
