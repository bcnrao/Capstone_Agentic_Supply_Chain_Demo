# Phase 1b — Ingestion Triggers (scheduled poller + webhook) · Plan

Numbered task groups. Each group is independently reviewable; the order respects
dependencies — config + the shared persistence tail come before the service that uses
them, the service exists before the scheduler job and synthetic sender that drive it, and
tests/docs come last. Scope and decisions in [[requirements]]; success criteria in
[[validation]]. Full design context in [[data-ingestion]]; reuses the Phase 1a pipeline
([[2026-06-16-data-ingestion]]).

---

## 1. Dependencies & configuration
1.1 `uv add fastapi uvicorn apscheduler` (only what this slice needs; `httpx` for the
    synthetic sender is already present). Keep the offline-runnable contract.
1.2 Add to `.env.example` (documented) and `config/settings.py`:
    `INGEST_POLL_INTERVAL_MINUTES` (default `10`), `INGEST_SCHEDULER_ENABLED`
    (default `true`), `INGEST_HOST` (default `127.0.0.1`), `INGEST_PORT` (default `8001`),
    and `WEBHOOK_SOURCE_RELIABILITY` (default `0.6`). Follow the existing graceful
    `get_settings()` pattern.

## 2. Shared persistence tail (reuse refactor)
2.1 Extract the **gate → dedupe → persist** block currently inside
    `collect.process_connector` into a reusable
    `ingest_signals(signals, conn) -> tuple[kept, dropped, persisted]` (in
    `ingestion/collect.py` or a small `ingestion/pipeline.py`). It must keep the existing
    behavior: skip duplicates (`dedupe.is_duplicate`), `store.persist_signal` accepted
    rows, `store.record_rejected` dropped ones, commit; and degrade to in-memory when
    `conn is None`.
2.2 Rewrite `process_connector` to call `ingest_signals` (no behavior change). One
    persistence path is now shared by the poller (via `collect`) and the webhook.

## 3. Webhook source identity & request model
3.1 Add `SourceType.WEBHOOK` to `connectors/base.py`.
3.2 A `WebhookEvent` **Pydantic request model** (`ingestion/service.py` or
    `ingestion/webhook.py`): `title`, optional `body`/`summary`, `url`, `published`,
    `location`, free `payload`. Map it → `connectors.base.RawItem`.
3.3 A lightweight **webhook source** object (name `supplier_webhook`,
    `source_type=WEBHOOK`, `reliability=WEBHOOK_SOURCE_RELIABILITY`) so the existing
    `normalize(raw, source)` stamps provenance unchanged — no special-casing in normalize.

## 4. FastAPI ingestion service (`ingestion/service.py`)
4.1 An app factory `create_app()` with a **lifespan**: on startup run idempotent
    `init_db()` and start the APScheduler (task group 5); on shutdown stop it cleanly.
4.2 Routes:
    - `POST /signals` — validate `WebhookEvent` → `normalize` → `ingest_signals` (opening
      a short-lived `connect()` when a DB is available) → JSON summary
      (`kept`/`dropped`/`persisted`/`duplicate`). **Graceful**: no DB → HTTP 200 with
      `persisted=0` (never 5xx for the expected offline case).
    - `POST /collect` — trigger an on-demand `collect()` and return its summary.
    - `GET /health` — liveness + whether the scheduler is running and DB reachable.
4.3 Console script `agentic-scd-ingest = "agentic_scd.ingestion.service:main"`; `main()`
    runs uvicorn on `INGEST_HOST:INGEST_PORT`.

## 5. Scheduled poller (APScheduler, in-process)
5.1 Start an APScheduler scheduler in the service lifespan with one job calling
    `collect()` every `INGEST_POLL_INTERVAL_MINUTES`, `max_instances=1`, `coalesce=True`
    (a slow cycle never stacks), gated by `INGEST_SCHEDULER_ENABLED`.
5.2 Each cycle logs a per-source tally (reuse the `print_summary` shape via `logging`),
    so the dashboard/operator can see live-vs-fallback and kept/dropped per run.

## 6. Synthetic sender
6.1 `scripts/send_synthetic_event.py` (run via `uv run`) that POSTs deterministic
    synthetic supplier events to `POST /signals` (reuse `SyntheticConnector` scenarios),
    driving the push path with no real supplier. Prints each response summary.

## 7. Quality baseline & tests (offline)
7.1 `pytest` with FastAPI `TestClient`, all offline (no network/DB):
    - webhook **accepts** a supply-chain event (200, kept=1) and **drops** an off-topic one
      (kept=0) via the Stage 1 lexicon;
    - webhook is **graceful with no DB** (200, `persisted=0`, no crash);
    - `ingest_signals` unit test (kept/dropped/persisted counts; in-memory when `conn=None`);
    - one **scheduler tick** invokes the pipeline once (synthetic-only registry / patched
      interval), `max_instances=1` honored;
    - the **synthetic sender** builds valid `WebhookEvent` payloads.
7.2 DB-touching tests (webhook → persist → `ingest_node` drain round-trip) **`pytest.skip`
    cleanly** when no DB, matching the Phase 0.5/1a pattern.
7.3 `ruff check` and `ruff format --check` pass on the whole tree.

## 8. Docs & wrap-up
8.1 README "Always-on ingestion service" section: run `uv run agentic-scd-ingest`, the
    poll cadence + scheduler toggle, `POST /signals` / `uv run scripts/send_synthetic_event.py`,
    and how the same rows drain via `ingest_node` (`uv run agentic-scd`). Note batch
    loaders + TTL are the remaining Phase 1b follow-up.
8.2 Confirm all [[validation]] criteria pass; open a PR from
    `phase-1b-ingestion-triggers` into `main`.
