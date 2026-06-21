# Phase 1c — Batch loaders & retention · Validation

How to know the implementation succeeded and the branch can merge. Maps to the task groups
in [[plan]] and the scope in [[requirements]]. The roadmap "Done when" for Phase 1c is the
north star: **a batch run seeds historical baselines into the `signals` table and
retention/TTL prunes stale rows — without disturbing the live triggers.**

## Acceptance criteria

### A. Batch loaders (seed → Postgres)
- [ ] `uv run agentic-scd-batch` runs the **Freightos** and **Kaggle SupplyChainNet**
      loaders from the **committed** `data/seed/` snapshots and persists `DisruptionSignal`
      rows into the `signals` table (when a DB is present), printing a per-source summary.
- [ ] Loaded rows carry a **batch/cached** `source_type` and pass through the **existing**
      `normalize → dedupe → persist` tail (no bespoke insert path).
- [ ] **Idempotent:** a second `agentic-scd-batch` run persists **no duplicate** rows
      (ON CONFLICT on `dedup_hash` holds), confirmed by row counts.

### B. Retention / TTL
- [ ] Retention prunes `seen_rejected` rows older than `retention_rejected_ttl_days` and
      stale `signals` (`status='done'` past `retention_signals_ttl_days`), reporting counts.
- [ ] Retention **never** deletes `new` / `processing` signals, nor in-window rows — the
      live pipeline's working set is untouched.
- [ ] Retention is a clean **no-op with no DB** (never raises).

### C. Does not disturb the live triggers
- [ ] The Phase 1b **poller** and **webhook** are unchanged in behaviour: batch + retention
      only read/write the same `signals` / `seen_rejected` tables; no scheduler coupling.
- [ ] A batch run during (or around) live polling does not block or corrupt the handoff
      (idempotent writes; retention scoped to terminal/old rows only).

### D. Vector-DB boundary (persist, don't embed)
- [ ] **No** vector store / embeddings dependency is introduced (no Chroma,
      sentence-transformers, etc. in `pyproject.toml` / `uv.lock`).
- [ ] KB-history records are **persisted** to Postgres/files only; embedding/indexing is
      left to Phase 4/7 (verified by the dependency set and code — no embed calls).

### E. Always demoable / local-first
- [ ] `uv run agentic-scd-batch` runs **fully offline** (no network, no Kaggle/Freightos
      download — the committed `data/seed/` snapshots are the source) and never crashes.
- [ ] With **no DB**, the CLI still parses the snapshots, prints a summary, and exits 0
      (nothing persisted, no exception).

### F. Quality gates
- [ ] `uv run pytest` passes **with no DB and no network** (per-loader, retention, and CLI
      smoke run offline; any DB-touching tests skip cleanly).
- [ ] `uv run ruff check` and `uv run ruff format --check` are clean across the tree.
- [ ] Console script `agentic-scd-batch` is registered in `pyproject.toml`; **no** new
      cloud/managed/vector deps pulled in.

## Manual smoke test

```bash
uv run agentic-scd-batch            # offline: load seed snapshots + run retention
#   expect: per-source loaded/persisted summary + rows pruned; runs with no DB/network

# Idempotency + real persistence with Postgres up:
docker compose up -d postgres
uv run agentic-scd-batch            # seeds signals from data/seed/
uv run agentic-scd-batch            # second run -> 0 new persisted (idempotent)
uv run agentic-scd                  # the pipeline reads the seeded historical signals
```

## Definition of done
- [ ] All acceptance criteria (A–F) checked.
- [ ] [[plan]] task groups 1–6 complete; scope matches [[requirements]] (batch loaders +
      retention only — no Parquet export, no embedding/vector store, no Prophet modelling,
      no scheduler coupling crept in).
- [ ] README updated; Phase 1c marked complete in [[roadmap]]; PR opened from
      `phase-1c-batch-loaders-retention` into `main` and green in CI.
