# Phase 1b — Ingestion Triggers (scheduled poller + webhook) · Validation

How to know the implementation succeeded and the branch can merge. Maps to the task
groups in [[plan]] and the scope in [[requirements]]. This branch completes the
**always-on triggers** part of the roadmap "Done when" for Phase 1b (batch loaders + TTL
are a deferred follow-up — see [[requirements]]).

> **Roadmap "Done when" (Phase 1b):** the ingestion service runs continuously
> (scheduled), accepts webhook pushes, and seeds history via batch loaders — all draining
> into the same `signals` table the pipeline reads. *This slice covers the **scheduled +
> webhook** triggers (and on-demand, from 1a); the **batch loaders** are validated in a
> later slice.*

## Acceptance criteria

### A. Service & scheduler
- [ ] `uv run agentic-scd-ingest` starts a FastAPI app with an **in-process APScheduler**;
      `GET /health` returns ok (and reports scheduler-running + DB-reachable flags).
- [ ] A scheduled tick runs the **full Phase 1a pipeline once** via `collect()`
      (`max_instances=1`, `coalesce=True`); each cycle logs a per-source tally.
- [ ] `INGEST_SCHEDULER_ENABLED=false` starts the service **without** the poller (webhook
      still works); `INGEST_POLL_INTERVAL_MINUTES` controls the cadence.

### B. Webhook
- [ ] `POST /signals` with a supply-chain event is **normalized → gated → deduped →
      persisted** (`status='new'`, provenance `source=supplier_webhook`,
      `source_type=WEBHOOK`) and returns a JSON summary (`kept`/`dropped`/`persisted`/
      `duplicate`).
- [ ] A clearly **off-topic** event (zero lexicon hits) is **dropped** (`kept=0`), its
      `dedup_hash` recorded in `seen_rejected`.
- [ ] **Idempotent:** re-POSTing the same event creates **no** duplicate row (exact-hash
      dedupe). No signature auth is required (HMAC is post-MVP).

### C. Persistence & decoupled handoff (reuse)
- [ ] The poller and the webhook write through the **same** `ingest_signals` tail into the
      **same** `signals` table — no second persistence path; `seen_rejected` and raw
      snapshots behave as in Phase 1a.
- [ ] `ingest_node` drains rows produced by **both** triggers (`status='new' → processing`,
      delta-only); a second drain with no new rows yields an empty batch.

### D. Graceful degradation (offline-runnable)
- [ ] With **no DB** reachable: the service still starts, `GET /health` reports DB down,
      a scheduled tick runs in-memory, and `POST /signals` returns **HTTP 200** with
      `persisted=0` — never a 5xx/crash for the expected offline case.
- [ ] With **no network**: a scheduled poll still yields signals via synthetic + cached
      fallbacks (Phase 1a behavior), path logged.

### E. Quality gates
- [ ] `uv run pytest` passes **with no DB and no network** (FastAPI `TestClient` webhook
      tests, `ingest_signals`, scheduler-tick, and sender tests run offline; DB-touching
      round-trips `pytest.skip` cleanly).
- [ ] With Postgres up (`docker compose up -d postgres`), the DB-touching webhook →
      persist → `ingest_node` round-trip is green.
- [ ] `uv run ruff check` and `uv run ruff format --check` are clean across the tree.
- [ ] New runtime deps (`fastapi`, `uvicorn`, `apscheduler`) are in `pyproject.toml` /
      `uv.lock`; nothing cloud/managed added.

## Manual smoke test

```bash
docker compose up -d postgres                 # Phase 0.5 DB
uv run agentic-scd-ingest                      # start the service (scheduler + webhook)
#   expect: GET /health ok; the poller logs a per-source summary each cycle

# In another shell — push a supplier event through the webhook:
uv run python scripts/send_synthetic_event.py  # POSTs synthetic events to /signals
#   expect: JSON summary per event (kept/dropped/persisted); rows land in `signals`

uv run agentic-scd                             # graph: ingest_node drains new rows ->
#   expect: input guardrail passes valid signals; end-to-end run prints real signals
```

Offline check (no Docker, no network):

```bash
uv run agentic-scd-ingest                      # starts; scheduler ticks in-memory, no crash
#   POST /signals returns 200 with persisted=0; synthetic poll still yields signals
uv run pytest                                  # expect: green; DB tests skipped
```

## Definition of done
- [ ] All acceptance criteria (A–E) checked.
- [ ] [[plan]] task groups 1–8 complete; scope matches [[requirements]] (no batch
      loaders / TTL crept in).
- [ ] README updated; PR opened from `phase-1b-ingestion-triggers` into `main` and green
      in CI.
