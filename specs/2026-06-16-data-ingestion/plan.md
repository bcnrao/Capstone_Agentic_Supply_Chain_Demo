# Phase 1 — Data Ingestion Layer (core slice) · Plan

Numbered task groups. Each group is independently reviewable; the order respects
dependencies — the schema and DDL come before the stages that fill it, connectors and the
pipeline stages come before the on-demand entrypoint that runs them, and the DB handoff
exists before `ingest_node` reads from it. Scope and decisions in [[requirements]];
success criteria in [[validation]]. Full design context in [[data-ingestion]].

---

## 1. Schema completion & persistence DDL
1.1 Extend `ingestion/schema.py` `DisruptionSignal` with the remaining ingestion-filled
    fields: `dedup_hash`, `source_reliability: float`, `raw_payload: dict`,
    `location` (region / lat / lon / hub-port, nullable), `severity_hint` (optional).
    Bump `SCHEMA_VERSION`. Later-phase fields stay `Optional[...] = None`.
1.2 Add a `signals` DDL: full record columns + `raw_payload` (JSONB) + a `status` column
    (`new` / `processing` / `done`, default `new`) + `created_at`. Index `status` and
    `dedup_hash`.
1.3 Add a `seen_rejected` DDL: `dedup_hash` (PK) + `first_seen_at` (for later TTL).
1.4 Write the DDL as a **plain `.sql` file** plus an **idempotent init helper** in the
    `db` module (`CREATE TABLE IF NOT EXISTS ...`, run over the Phase 0.5 `connect()`
    seam). No ORM; no Alembic.

## 2. Connector pattern & source registry
2.1 `ingestion/connectors/base.py`: the `Connector` protocol/base (`name`,
    `source_type`, `reliability`, `fetch()`, `fallback()`) and a `RawItem` type.
2.2 A **`fetch`-with-fallback wrapper** so any connector failure (network / rate-limit /
    empty) degrades to `fallback()` instead of raising; log which path was taken.
2.3 `ingestion/registry.py` + root `sources.yaml`: enabled connectors, their
    URLs/query terms, reliability priors, and fallback snapshot paths. Sources toggle by
    config, not code.

## 3. Connectors (this slice)
3.1 `connectors/rss.py` — `feedparser` over supply-chain + **query-scoped** Google News
    feeds; `fallback()` replays a cached snapshot file.
3.2 `connectors/open_meteo.py` — `httpx` over a configured list of hubs/ports;
    `fallback()` replays cached weather JSON.
3.3 `connectors/synthetic.py` — deterministic disruption-scenario generator (promotes the
    Phase 0 stub into a real connector; always available as the ultimate fallback).

## 4. Pipeline stages (fetch → normalize → gate → dedupe → persist)
4.1 `ingestion/normalize.py` — map each source's raw format → canonical `DisruptionSignal`:
    dates → UTC ISO, strip HTML / collapse whitespace, stamp provenance
    (`source` / `source_type` / `source_reliability`), keep untouched raw in `raw_payload`.
    Runs **before** gate + dedupe.
4.2 `ingestion/relevance.py` — **Stage 0** source targeting (config-driven) + **Stage 1**
    keyword lexicon gate from a root **`lexicon.yaml`**; zero lexicon hits → drop.
    Recall-favoring; **log the drop rate** and sample rejects.
4.3 `ingestion/dedupe.py` — `dedup_hash = sha256(normalized_title + normalized_body)`;
    skip if hash is in `seen_rejected` or already persisted, else accept.
4.4 `ingestion/store.py` — persist accepted signals to Postgres (`status='new'`), write
    rejected `dedup_hash` → `seen_rejected`, and write **raw pulls to snapshot files
    outside the DB** (the fallback/replay path). Idempotent on `dedup_hash`.

## 5. On-demand collector entrypoint
5.1 An entrypoint (`ingestion/service.py` or a `scripts/` runner, invoked via `uv run`)
    that loads the registry, runs every enabled connector once through
    fetch→normalize→gate→dedupe→persist, and prints a summary (fetched / kept / dropped /
    fallback-used per source).
5.2 Graceful end-to-end: a fully offline run still yields signals (synthetic + any cached
    fallbacks) and never crashes. (APScheduler poller + FastAPI webhook are **Phase 1b**.)

## 6. Graph integration (`ingest_node` + input guardrail)
6.1 `pipeline`/`ingest_node`: replace the stub body in `ingestion/agent.py` —
    `read_new_signals()` selects only `status='new'` rows, marks them `processing`, and
    returns `{"new_signals": [...]}` (overwrite reducer, delta-only).
6.2 Add an **input guardrail** node (`ingestion/guardrails.py` or `pipeline/guardrails.py`):
    revalidate relevance · Pydantic schema · safety → **discard** unsafe/off-topic/malformed
    before downstream nodes.
6.3 Wire `ingest_node → input_guardrail → (downstream)` into `graph/builder.py`; keep the
    end-to-end graph runnable via the existing `__main__` entrypoint.

## 7. Dependencies, quality baseline & tests
7.1 `uv add feedparser httpx pyyaml` (only what this slice needs); keep the offline
    contract.
7.2 `pytest`: unit tests for normalize, relevance keep/drop, exact-hash dedupe, schema
    validation, and the connector **fallback path** — all **offline, no network/DB**.
7.3 DB-touching tests (`store` / `ingest_node` round-trip) **`pytest.skip` cleanly** when
    no DB is reachable, matching the Phase 0.5 pattern — suite stays green fully offline.
7.4 `ruff check` and `ruff format --check` pass on the whole tree.

## 8. Docs & wrap-up
8.1 README section: run the collector on-demand (`uv run ...`), what persists to Postgres
    vs. snapshot files, the Stage 0+1 relevance gate, and how `ingest_node` drains new
    rows; note Phase 1b (scheduler + webhook) is the follow-up.
8.2 Confirm all [[validation]] criteria pass; open a PR from `phase-1-data-ingestion`
    into `main`.
