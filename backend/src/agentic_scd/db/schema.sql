-- Phase 1 data-ingestion schema (plain DDL, no ORM/Alembic).
-- Applied idempotently by db.init_db() over the Phase 0.5 connect() seam:
-- every statement is CREATE ... IF NOT EXISTS, so re-running is a no-op.

-- Accepted, normalized DisruptionSignal records — the system of record and the
-- decoupled handoff to the graph (status: new -> processing -> done).
CREATE TABLE IF NOT EXISTS signals (
    signal_id          TEXT PRIMARY KEY,
    dedup_hash         TEXT UNIQUE,
    source             TEXT NOT NULL,
    source_type        TEXT NOT NULL,
    source_reliability DOUBLE PRECISION,
    fetched_at         TIMESTAMPTZ NOT NULL,
    event_time         TIMESTAMPTZ,
    title              TEXT NOT NULL,
    raw_text           TEXT NOT NULL DEFAULT '',
    url                TEXT,
    location           JSONB,
    severity_hint      TEXT,
    schema_version     INTEGER NOT NULL,
    raw_payload        JSONB,
    status             TEXT NOT NULL DEFAULT 'new'
                       CHECK (status IN ('new', 'processing', 'done')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals (status);
CREATE INDEX IF NOT EXISTS idx_signals_dedup_hash ON signals (dedup_hash);

-- Rejected items: store ONLY the dedup_hash so the same junk is not re-evaluated
-- each poll, without keeping its content. first_seen_at supports a later TTL.
CREATE TABLE IF NOT EXISTS seen_rejected (
    dedup_hash    TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
