# Phase 1 — Data Ingestion Layer (core slice) · Validation

How to know the implementation succeeded and the branch can merge. Maps to the task
groups in [[plan]] and the scope in [[requirements]]. The roadmap "Done when" for
Phase 1 is the north star; this slice satisfies it for the **on-demand** path (the
scheduled poller + webhook arrive in Phase 1b — see [[requirements]]).

> **Roadmap "Done when" (Phase 1):** the ingestion service yields normalized,
> relevance-filtered, deduped signals persisted to Postgres and read into state — from
> scheduled, webhook, batch, and synthetic sources, with fallback and the input guardrail
> working. *This slice covers the **on-demand / live-poll / synthetic** sources + fallback
> + guardrail; scheduled, webhook, and batch sources are validated in Phase 1b.*

## Acceptance criteria

### A. Pipeline correctness (offline, deterministic)
- [ ] `normalize` turns a raw RSS item and a raw Open-Meteo payload into valid
      `DisruptionSignal` objects: dates are UTC, HTML/whitespace cleaned, provenance
      (`source` / `source_type` / `source_reliability`) stamped, original kept in
      `raw_payload`.
- [ ] **Relevance gate** keeps a clearly on-topic item (e.g. "port strike halts
      shipments") and drops a clearly off-topic one (zero lexicon hits) — Stage 0 + Stage 1
      only.
- [ ] **Dedupe** is exact-hash: two items with identical normalized title+body produce the
      same `dedup_hash` and the second is skipped; a differing item is not skipped.
- [ ] The gate **favors recall** and the run **logs a drop rate** / kept-vs-dropped counts.

### B. Connectors & graceful degradation
- [ ] RSS, Open-Meteo, and synthetic connectors implement the `Connector` interface and
      are listed/toggled via `sources.yaml`.
- [ ] Forcing a connector `fetch()` failure (no network / bad URL) **falls back** to
      `fallback()` (cached/synthetic) instead of raising; the path taken (live vs
      fallback) is logged.
- [ ] A **fully offline** on-demand run still yields signals and **never crashes**.

### C. Persistence & decoupled handoff
- [ ] The `signals` and `seen_rejected` tables are created by the **idempotent init
      helper** (re-running it is a no-op; no ORM/Alembic introduced).
- [ ] Accepted signals persist to Postgres with `status='new'` and full fields +
      `raw_payload`; rejected items store **only** their `dedup_hash` in `seen_rejected`.
- [ ] Raw pulls are written to **snapshot files outside the DB**.
- [ ] Re-running the collector does **not** create duplicate rows for the same
      `dedup_hash` (idempotent persist).

### D. Graph integration
- [ ] `ingest_node` reads **only** `status='new'` rows, marks them `processing`, and emits
      `{"new_signals": [...]}` — a second invocation with no new rows yields an empty
      batch (delta-only, no reprocessing).
- [ ] The **input guardrail** node discards unsafe/off-topic/schema-invalid signals before
      downstream nodes; valid signals pass through.
- [ ] `graph/builder.py` wires `ingest_node → input_guardrail → downstream`, and the
      existing `__main__` entrypoint runs the graph end-to-end with **real** ingested
      signals replacing the Phase 0 stub.

### E. Quality gates
- [ ] `uv run pytest` passes **with no DB and no network** (DB-touching tests
      `pytest.skip` cleanly; pipeline/connector/guardrail tests run offline).
- [ ] With Postgres up (`docker compose up -d postgres`), the DB-touching tests run and a
      collect → persist → `ingest_node` round-trip is green.
- [ ] `uv run ruff check` and `uv run ruff format --check` are clean across the tree.
- [ ] New runtime deps (`feedparser`, `httpx`, `pyyaml`) are in `pyproject.toml` /
      `uv.lock`; nothing cloud/managed added.

## Manual smoke test

```bash
docker compose up -d postgres            # Phase 0.5 DB
uv run <collector-entrypoint>            # fetch -> normalize -> gate -> dedupe -> persist
#   expect: per-source summary (fetched / kept / dropped / fallback-used), rows in `signals`
uv run agentic-scd                       # run the graph: ingest_node drains new rows ->
#   expect: input guardrail passes valid signals; end-to-end run prints real signals
uv run <collector-entrypoint>            # run again
#   expect: no duplicate rows (exact-hash dedupe); ingest_node sees only genuinely new rows
```

Offline check (no Docker, no network):

```bash
uv run <collector-entrypoint>            # expect: synthetic + cached fallbacks, no crash
uv run pytest                            # expect: green; DB tests skipped
```

## Definition of done
- [ ] All acceptance criteria (A–E) checked.
- [ ] [[plan]] task groups 1–8 complete; scope matches [[requirements]] (no Phase 1b
      scheduler/webhook/batch crept in).
- [ ] README updated; PR opened from `phase-1-data-ingestion` into `main` and green in CI.
