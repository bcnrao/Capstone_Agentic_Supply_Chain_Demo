# Phase 1 — Data Ingestion Layer (core slice) · Requirements

> Roadmap phase: **Phase 1 — Data ingestion layer (foundation)** (see [[roadmap]]).
> Full design: [[data-ingestion]].
> Guidance: [[mission]] (capstone MVP; local-first, no cloud, always demoable, graceful
> degradation), [[tech-stack]] (local PostgreSQL system of record + decoupled handoff;
> local `uv` workflow stays the dev default). Builds directly on
> [[2026-06-16-postgres-dev-services]] (the Postgres compose + `db` connectivity seam).

## Goal

Replace the Phase 0 synthetic ingestion **stub** with a real
**fetch → normalize → relevance-gate → dedupe → persist** pipeline that writes
normalized `DisruptionSignal` rows to Postgres, and a graph `ingest_node` that reads
**only the new rows** into state behind an **input guardrail**. The result is a
runnable, demoable foundation every downstream phase consumes.

## Scope decision for this branch (Phase 1a)

Phase 1 as fully specced in [[data-ingestion]] is large. Per the "phases are
intentionally small" / "always demoable" principles, this branch lands the **core
pipeline slice** and defers the heavier *separate-service* machinery to a **Phase 1b**
follow-up. The split was chosen explicitly (see Decisions).

### In scope (Phase 1a)

1. **Signals table + supporting DDL.** A Postgres `signals` table for accepted
   `DisruptionSignal` records (full fields + `raw_payload` + a `status` flag
   `new → processing → done` for the decoupled handoff), plus a small **seen-rejected**
   cache table keyed by `dedup_hash`. Created via a **plain SQL DDL file** applied by an
   **idempotent init helper** (`CREATE TABLE IF NOT EXISTS`) over the existing raw-psycopg
   `db` seam — **no ORM**.
2. **Canonical schema completion.** Extend the existing `DisruptionSignal`
   (`ingestion/schema.py`) with the remaining ingestion-filled fields it currently lacks:
   `dedup_hash`, `source_reliability`, `raw_payload`, `location`, `severity_hint`.
   Later-phase fields (`category`, `severity`, `affected_entities`) stay `None`.
3. **Connector/adapter pattern + registry.** A `Connector` protocol/base and a
   `sources.yaml` registry (enabled connectors, URLs/query terms, fallback paths) so
   sources are toggled by config, not code. A `registry.py` loads it.
4. **Connectors (this slice):** **RSS** (`feedparser`, query-scoped + supply-chain feeds),
   **Open-Meteo** weather (`httpx` over configured hubs/ports), and a **synthetic
   generator**. Each `fetch()` is wrapped so any failure falls back to `fallback()`
   (cached snapshot / synthetic) — graceful degradation, with the path taken logged.
5. **Pipeline stages:** `normalize.py` (source format → canonical signal; UTC dates,
   HTML-strip/whitespace, provenance stamping, keep raw in `raw_payload`),
   `relevance.py` (**Stage 0** source targeting via config + **Stage 1** keyword lexicon
   from `lexicon.yaml`; favor recall, log drop rate), `dedupe.py` (**exact** SHA-256 hash
   of normalized title+body; check seen-rejected + persisted hashes), `store.py`
   (persist accepted signals to Postgres, write rejected `dedup_hash` to the cache, write
   raw pulls to **snapshot files outside the DB**).
6. **On-demand collector entrypoint.** A `uv run` entrypoint that runs the enabled
   connectors once through the pipeline and persists results. (The **separate APScheduler
   poller service** and **FastAPI webhook** are Phase 1b.)
7. **Graph integration.** Real `ingest_node` reads **only** unprocessed rows
   (`status='new'` → mark `processing`) from Postgres and returns
   `{"new_signals": [...]}` (overwrite reducer). An **input guardrail** node
   (relevance · Pydantic schema · safety → discard) sits between `ingest_node` and the
   downstream graph; wire both into `graph/builder.py`.
8. **Quality + tests.** `pytest` covering normalize, relevance gate (keep/drop),
   exact-hash dedupe, schema validation, and the connector fallback path — all runnable
   **fully offline** (no network, no DB; DB-touching tests `pytest.skip` cleanly when no
   DB, matching the Phase 0.5 pattern). `ruff check` + `ruff format --check` stay clean.
9. **Docs & wrap-up.** README section: how to run the collector on-demand, what gets
   persisted vs. snapshotted, and how `ingest_node` drains new rows. Open a PR into `main`.

### Out of scope — deferred to Phase 1b (next branch)

- **Separate ingestion service** with the **APScheduler/cron scheduled poller** and the
  **FastAPI webhook** endpoint (+ synthetic sender). This slice runs collectors
  **on-demand**; the always-on triggers land in 1b.
- **Batch loaders** — Kaggle SupplyChainNet dataset loader and the cached **Freightos
  Baltic Index** snapshots.
- Retention/TTL enforcement on the seen-rejected cache and accepted signals; Parquet
  analytics export.

### Out of scope — deferred to later phases

- Risk **classification / extraction / scoring** (`category`, `severity`) — **Phase 3**;
  ingestion does coarse keep/drop relevance only, never classification.
- **Impact mapping** (`affected_entities`) and the vector store — **Phase 4**.
- **Stage 2 DistilBERT** binary relevance gate — **Phase 3** (only if Stage 0+1 prove
  too noisy). **Fuzzy** dedupe, `Send` fan-out, IDs-in-state — past the MVP.
- HMAC webhook signature auth — post-MVP.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Branch scope | **Core pipeline slice (Phase 1a)**; scheduler/webhook/batch → **Phase 1b** | Keeps the phase small and gets the end-to-end path green fastest, per [[roadmap]] "phases are intentionally small" + "always demoable". |
| Schema management | **Plain SQL DDL file** + idempotent init helper over raw **psycopg** (no ORM) | Matches the existing `db/client.py` seam from [[2026-06-16-postgres-dev-services]]; lightweight, no new tooling/dep. Alembic/SQLAlchemy deferred unless a real migration need appears. |
| Live-source strategy | **Live RSS + Open-Meteo with cached/synthetic fallback** | Proves graceful degradation now and matches the [[mission]] hybrid (live + cached + synthetic) data strategy. |
| Collector triggers | **On-demand entrypoint** this slice; **separate service** (scheduler + webhook) in 1b | Pairs with the core-slice scope; the decoupled-handoff DB contract is built now so 1b only adds trigger plumbing, not rework. |
| Dedupe | **Exact SHA-256** over normalized title+body | Per [[data-ingestion]] locked decision; catches re-fetches + verbatim syndication. Fuzzy dedupe deferred. |
| Relevance gate | **Stage 0 (source targeting) + Stage 1 (keyword lexicon)**, recall-favoring | Per [[data-ingestion]]; cheap, deterministic, keeps the DB free of irrelevant news without dropping real disruptions. |
| Handoff contract | Collectors **write** accepted rows; `ingest_node` **reads** new rows via a `status` flag | The decoupled handoff so a busy pipeline never blocks ingestion (per [[tech-stack]] / [[data-ingestion]]). |
| State reducer | **Overwrite-per-run** `new_signals` | Per [[data-ingestion]]; Postgres is the durable accumulator, state holds this run's batch. |

## Context & notes

- Phase 0 already ships stubs this phase fills in **behind the same signatures**:
  `ingestion/agent.py` (`ingestion_node`), `ingestion/schema.py` (`DisruptionSignal`),
  `graph/state.py` (`new_signals` channel), `graph/builder.py`.
- The Postgres compose, `.env` `POSTGRES_*` / `DATABASE_URL`, and the `db` connectivity
  helper (`connect` / `ping`) already exist from Phase 0.5 — this phase **uses** them and
  adds DDL + read/write helpers; it does not re-derive connection config.
- New runtime deps expected this slice: `feedparser`, `httpx`, `PyYAML` (registry/lexicon
  loading). Add via `uv add`; keep the offline-runnable contract.
- Raw pulls are retained as **snapshot files outside the DB** so an over-aggressive
  lexicon is recoverable by re-running with looser terms (per [[data-ingestion]]).
- Everything stays **local** — no cloud, no managed services (per [[mission]]).
