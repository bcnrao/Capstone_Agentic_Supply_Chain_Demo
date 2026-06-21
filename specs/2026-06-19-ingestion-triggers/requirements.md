# Phase 1b — Ingestion Triggers (scheduled poller + webhook) · Requirements

> Roadmap phase: **Phase 1b — Data ingestion: always-on triggers & batch** (see
> [[roadmap]]). Builds directly on **Phase 1a** ([[2026-06-16-data-ingestion]]) and the
> full design in [[data-ingestion]]. Guidance: [[mission]] (capstone MVP; local-first,
> always demoable, graceful degradation; success criterion #1 — ingest "via scheduled,
> webhook, and on-demand triggers") and [[tech-stack]] (ingestion runs as a **separate
> service** — APScheduler poller + **FastAPI webhook** + synthetic sender).

## Goal

Wrap the Phase 1a **on-demand** pipeline in **always-on triggers** so the system
monitors continuously instead of only when invoked. Add a **scheduled poller**
(APScheduler) and a **FastAPI webhook** (supplier push + synthetic sender), running as a
**single ingestion service process**, both writing through the *same*
fetch → normalize → relevance-gate → dedupe → persist path into the *same* Postgres
`signals` handoff that `ingest_node` already drains. The decoupled-handoff DB contract
built in 1a means this branch adds **only trigger plumbing — no rework of the core
pipeline**.

## Scope decision for this branch (triggers only)

Phase 1b as roadmapped also includes batch loaders and retention/TTL. Per the
"phases are intentionally small" / "always demoable" principles, this branch lands the
**always-on triggers** (the headline of 1b) and **defers** the batch loaders and TTL to
a later slice (see Out of scope). Chosen explicitly (see Decisions).

### In scope

1. **Ingestion service** (`ingestion/service.py`) — a single **FastAPI** app exposed as a
   console script `agentic-scd-ingest` (served by **uvicorn**). On startup it runs the
   idempotent `init_db()` and starts an in-process **APScheduler**; on shutdown it stops
   the scheduler cleanly (FastAPI lifespan).
2. **Scheduled poller** — an APScheduler job that runs the existing
   `collect()` (`ingestion/collect.py`) every **N minutes** (configurable), polling the
   enabled `sources.yaml` connectors (RSS + Open-Meteo + synthetic) through the full
   pipeline. Overlap-safe (`max_instances=1`, `coalesce=True`); each cycle logs its
   per-source summary. Toggleable via config.
3. **FastAPI webhook** — a `POST` endpoint that accepts a **supplier push event** (JSON),
   maps it to a `RawItem`, normalizes it with a **webhook source identity**
   (`SourceType.WEBHOOK`, source `supplier_webhook`), and runs it through
   **gate → dedupe → persist**. Returns a JSON summary (kept / dropped / persisted /
   duplicate). **Degrades gracefully** when no DB is reachable (HTTP 200, `persisted=0`).
   No signature auth (HMAC is post-MVP).
4. **Synthetic sender** — a small runner (`scripts/` or module, via `uv run`) that POSTs
   deterministic synthetic supplier events to the webhook, so the push path is demoable
   with no real supplier (reuses the Phase 0/1a synthetic scenarios).
5. **Shared pipeline tail (reuse, not duplication)** — extract the
   gate → dedupe → persist tail that `collect.process_connector` already performs into a
   reusable `ingest_signals(signals, conn)` helper, used by **both** the poller (via
   `collect`) and the webhook, so there is one persistence path.
6. **Config** — `INGEST_POLL_INTERVAL_MINUTES`, `INGEST_SCHEDULER_ENABLED`,
   `INGEST_HOST`/`INGEST_PORT` (and a webhook source reliability prior) documented in
   `.env.example` and read via `config/settings.py`. Sources still toggle via
   `sources.yaml`.
7. **Dependencies** — `fastapi`, `uvicorn`, `apscheduler` (only what this slice needs;
   `httpx` for the sender is already present). Keep the offline-runnable contract.
8. **Quality + tests** — offline `pytest` for the webhook (accept / dedupe-skip /
   off-topic-drop / graceful-no-DB via FastAPI `TestClient`), the scheduled job
   (one tick invokes the pipeline once), the synthetic sender, and the shared
   `ingest_signals` tail. DB-touching round-trips `pytest.skip` cleanly with no DB.
   `ruff` stays clean.
9. **Docs & wrap-up** — README "always-on ingestion service" section: run the service,
   the poll cadence, POST a webhook event / run the synthetic sender, and how the same
   rows drain via `ingest_node`. Open a PR into `main`.

### Out of scope — deferred (later slice / phase)

- **Batch loaders** — cached **Freightos Baltic Index** snapshots and the **Kaggle
  SupplyChainNet** historical seed (Kaggle needs a dataset file / credentials, awkward
  for the fully-offline contract).
- **Retention / TTL** on the `seen_rejected` cache and accepted `signals`; Parquet export.
- **HMAC webhook signature auth** — post-MVP.
- Anything already shipped in **Phase 1a** (connectors, registry, normalize, relevance,
  dedupe, store, `ingest_node`, input guardrail, the on-demand `agentic-scd-collect`) —
  this branch **reuses** it, not rebuilds it.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Branch scope | **Triggers only** (scheduler + webhook + synthetic sender); batch + TTL deferred | Keeps the phase small and demoable; the always-on triggers are the headline of 1b (per [[roadmap]] / [[mission]]). |
| Service shape | **Single FastAPI process** hosting the webhook **and** an in-process APScheduler (`agentic-scd-ingest`) | Simplest local-first run (one command); the decoupled handoff already isolates the pipeline, so one process is enough for the MVP. |
| Scheduler | **APScheduler** in-process, `max_instances=1` + `coalesce` | Per [[tech-stack]]; overlap-safe so a slow cycle never stacks. |
| Poller body | **Reuse `collect()`** unchanged | The on-demand collector already runs the enabled connectors through the full pipeline — the scheduler just calls it on a cadence. |
| Webhook persistence | **Share an `ingest_signals()` tail** with `collect.process_connector` | One persistence path (gate → dedupe → persist), no duplicated logic. |
| Webhook source identity | New **`SourceType.WEBHOOK`**, source `supplier_webhook`, configurable reliability prior | Provenance for pushed events; keeps them on the canonical `DisruptionSignal`. |
| Webhook auth | **None** this slice | HMAC is explicitly post-MVP ([[data-ingestion]]). |
| Validation | **Offline tests + manual smoke** | Matches the Phase 1a green-offline contract; live timing/network stays out of CI. |

## Context & notes

- Phase 1a shipped the reusable pieces this branch wires triggers onto:
  `collect.collect()` / `collect.process_connector`, `normalize.normalize`,
  `relevance.gate`, `dedupe.assign_hash` / `dedupe.is_duplicate`,
  `store.persist_signal` / `store.record_rejected`, `db.init_db` / `db.connect`, and
  `agent.read_new_signals`. The webhook and poller call these, not new copies.
- `ingestion/service.py` was intentionally left free in Phase 1a for exactly this
  FastAPI webhook + service entrypoint (see [[data-ingestion]] suggested structure).
- Everything stays **local** — no cloud, no managed services; the service runs under the
  local `uv` workflow and degrades gracefully with no DB / no network.
