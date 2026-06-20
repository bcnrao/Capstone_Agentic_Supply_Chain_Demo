# Phase 1c — Batch loaders & retention · Requirements

> Roadmap phase: **Phase 1c — Data ingestion: batch loaders & retention** (see [[roadmap]]).
> Closes out the ingestion layer (Phases 1a/1b). Guidance: [[mission]] (capstone MVP;
> **local-first**, **always demoable**, graceful degradation), [[tech-stack]] (Postgres is
> the system of record + decoupled handoff; cached/synthetic data strategy; Prophet
> consumes historical baselines in Phase 5), and [[data-ingestion]] (the normalize → gate
> → dedupe → persist tail these loaders reuse).

## Goal

Add the remaining ingestion **sources and housekeeping** deferred from 1b, on the same
Postgres handoff so 1c only adds **batch + retention plumbing** — no rework of the live
pipeline. A one-shot batch run seeds historical data into the `signals` table; a
retention pass prunes stale rows. The live scheduled poller and webhook (1b) are
untouched and keep running.

```
cached snapshots (committed) → load → normalize → dedupe → persist (signals)   [seed]
seen_rejected + old signals  → TTL prune                                       [retain]
```

## Scope decision (confirmed)

- **Sources in scope:** **Freightos Baltic Index** cached snapshots + **Kaggle
  SupplyChainNet** historical seed. Both land in **Postgres** (the `signals` table) as the
  system of record.
- **Retention:** TTL pruning of the **`seen_rejected`** cache and **stale accepted
  signals**, using the `first_seen_at` / `created_at` columns the Phase 1 schema already
  carries ("supports a later TTL").
- **Run mechanism:** a new **on-demand CLI** — `agentic-scd-batch` — mirroring the Phase 1a
  `agentic-scd-collect` style (one-shot, prints a summary). **Not** wired into the
  APScheduler poller; retention is run on demand alongside seeding.
- **Data handling:** **small, trimmed cached snapshots are committed** into the repo so a
  batch run works **fully offline** with no Kaggle/Freightos download — matching the
  local-first / always-demoable contract.

### Vector-DB boundary (explicit)

Phase 1c is still the **ingestion layer**: it **persists** historical/KB-history data to
**Postgres (+ snapshot files)** and **does not embed anything**. The vector store (Chroma)
is **not** stood up here — it is introduced **once** in **Phase 4** (impact-mapping KB) and
**reused** in **Phase 7** (mitigation playbooks), per [[roadmap]] and [[tech-stack]]. The
"KB history" the roadmap mentions is **landed now, vectorized later**:

- **Baselines** (Kaggle demand series, Freightos freight rates) are numeric **time-series**
  → Postgres (+ optional files); consumed by **Prophet forecasting (Phase 5)**. A vector
  store is the wrong tool for them.
- **KB-history records** (historical disruption text) are corpus-shaped but are only
  **persisted** in 1c; the **embed-and-index** step belongs to **Phase 4/7**, which read
  from what 1c persists. Postgres stays the source of truth; the Chroma index is a
  **derived, rebuildable** artifact.

### In scope

1. **Committed seed data** (`data/seed/`): small trimmed **Freightos Baltic Index** snapshot
   and **Kaggle SupplyChainNet** extract, plus a new `SEED_DIR` in `ingestion/paths.py`
   (committed, like `FALLBACK_DIR`; distinct from the gitignored `snapshots/`).
2. **Two batch loaders** (`ingestion/batch/`), each reading a committed snapshot →
   `normalize` → the shared **dedupe → persist** tail (`ingest_signals` / `persist_signal`),
   **idempotent on `dedup_hash`** so re-runs don't duplicate rows:
   - **Freightos loader** — freight-rate snapshot rows → `DisruptionSignal`s with a
     **batch/cached** `source_type`.
   - **Kaggle SupplyChainNet loader** — historical disruption/demand rows → `DisruptionSignal`s
     (demand baselines + persisted KB-history records).
3. **Retention / TTL** (`ingestion/retention.py`): prune `seen_rejected` rows older than a
   configurable TTL and stale accepted `signals` (e.g. `status='done'` past a TTL), via
   `created_at` / `first_seen_at`. Configurable, off-by-safe (no-op with no DB), and it
   **never touches `new`/`processing` rows** the pipeline still needs.
4. **On-demand CLI** (`agentic-scd-batch`): run the loaders and/or retention once and print a
   concise summary (per-source loaded/kept/persisted; rows pruned). Graceful fully offline.
5. **Config**: TTL windows + enable flags on `Settings` (env-driven, sensible defaults),
   matching the existing `INGEST_*` settings style.
6. **Tests (offline)**: per-loader (snapshot → expected normalized/persisted signals;
   idempotent re-run), retention (prunes only the intended rows; preserves live rows), and a
   CLI summary smoke — all with **no DB and no network** (DB-touching paths skip cleanly).
7. **Docs & wrap-up**: README "Batch loaders & retention (Phase 1c)" section; PR into `main`.

### Out of scope — deferred

- **Parquet export** — the roadmap's *optional* item; not selected for this branch (revisit
  if analytics need it). Snapshot/JSON persistence already exists.
- **Embedding / vector indexing** of the KB-history corpus → **Phase 4** (KB) and **Phase 7**
  (playbooks); Chroma is stood up there, not here.
- **Prophet baseline modelling / risk-adjusted forecasting** → **Phase 5** (1c only lands the
  historical data Prophet later reads).
- **Scheduling** the batch/retention jobs inside the poller — kept **on-demand** this slice.
- Any change to the live 1b triggers (poller/webhook) beyond reading the same tables.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target store | **Postgres `signals` table** (+ committed snapshot files) — **no vector DB** | Roadmap "Done when" names the `signals` table; Chroma is a derived index stood up once in Phase 4 and reused in Phase 7. Ingestion persists; later phases index. |
| Run mechanism | **On-demand `agentic-scd-batch` CLI** (not scheduled) | Mirrors Phase 1a `agentic-scd-collect`; simplest, reproducible seeding; keeps batch decoupled from the always-on poller. |
| Data handling | **Commit small trimmed snapshots** under `data/seed/` | Local-first / always-demoable: a batch run works fully offline with no Kaggle/Freightos download. |
| Reuse | Loaders feed the **existing** `normalize → ingest_signals` tail, idempotent on `dedup_hash` | No rework of the core pipeline; re-runs are safe; matches [[data-ingestion]]. |
| Retention | TTL via existing `created_at` / `first_seen_at`; prune `seen_rejected` + `done` signals only | The schema already added those columns "for a later TTL"; never prune rows the pipeline still needs. |
| Parquet export | **Deferred** (roadmap "optional", not selected) | Keep the slice small; JSON snapshots already cover audit/replay. |

## Context & notes

- The ingestion layer (1a/1b) already exists: connectors + registry, `normalize`,
  relevance gate, `dedupe`, `ingest_signals`/`persist_signal`, the `signals` +
  `seen_rejected` schema, the on-demand `collect` CLI, and the always-on `service`
  (poller + webhook). 1c adds the `ingestion/batch/` loaders, `ingestion/retention.py`, the
  `agentic-scd-batch` CLI, and committed `data/seed/` snapshots.
- Reuses Phase 1 building blocks: `ingestion.normalize.normalize`,
  `ingestion.pipeline.ingest_signals`, `ingestion.store.persist_signal`,
  `ingestion.schema.DisruptionSignal`, `ingestion.paths` (add `SEED_DIR`), `db.connect` /
  `db.init_db`, and `config.Settings`.
- Everything stays **local** and offline-runnable — no cloud, no managed services, no new
  network/credential dependency. The committed seed snapshots are the offline source of truth.
