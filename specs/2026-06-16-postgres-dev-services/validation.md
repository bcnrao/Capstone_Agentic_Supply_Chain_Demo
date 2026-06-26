# Phase 0.5 — Dev Data Services (Postgres) · Validation

How we know Phase 0.5 is complete and the branch can merge to `main`. Maps to the
roadmap "Done when" and the [[requirements]] scope. Plan in [[plan]].

## Primary acceptance criterion (roadmap)

> **Done when:** `docker compose up postgres` brings up a healthy, volume-persisted
> Postgres the app connects to, and the dump/restore scripts round-trip a snapshot to
> `data/backups/`.

✅ `docker compose up postgres` reaches a **healthy** state; the local `uv` app connects
over `DATABASE_URL` (`db.ping()` → `SELECT 1` succeeds); data survives a
`down`/`up` cycle on the `pgdata` volume; and `pg_dump` → restore reproduces a snapshot
through `data/backups/`.

## Acceptance checklist

### Compose & service
- [ ] `docker-compose.yml` defines a `postgres` service on **`postgres:16-alpine`**.
- [ ] `docker compose up -d postgres` reports the service **`healthy`** (`pg_isready`).
- [ ] `POSTGRES_DB/USER/PASSWORD` are read from `.env` (nothing secret hard-coded).
- [ ] The host port is published and reachable from the local `uv` process.

### Persistence
- [ ] Data is stored on the named **`pgdata`** volume (not a bind mount).
- [ ] Data **survives** `docker compose down` → `up` (without `-v`); is removed by
      `down -v` (confirming the volume is the system of record).

### Config & secrets
- [ ] `.env.example` lists `POSTGRES_*` parts **and** `DATABASE_URL`, all documented.
- [ ] `Settings`/`get_settings()` expose `database_url`; explicit env wins over `.env`.
- [ ] `.env` is git-ignored; **no secret committed** (`git log -p` scan clean).

### Connectivity layer
- [ ] `psycopg[binary]` is the only new dependency added this phase.
- [ ] `db.ping()` opens a connection and returns success on `SELECT 1` when the DB is up.
- [ ] With **no DB reachable**, the helper fails **gracefully** (clear message, no
      unhandled crash) and the app stays offline-runnable.

### Backup / restore
- [ ] `uv run python scripts/db_dump.py` writes a snapshot into `data/backups/`.
- [ ] `uv run python scripts/db_restore.py <snapshot>` restores it.
- [ ] **Round-trip** verified: dump → change/drop → restore reproduces the data.
- [ ] `data/backups/` is git-ignored.

### Quality baseline (CI-lite)
- [ ] The connectivity `pytest` **skips cleanly** when no DB is up — the suite passes
      fully offline.
- [ ] With the DB up, the connectivity test passes.
- [ ] `ruff check` passes; `ruff format --check` passes.

## Commands (expected to pass)

```bash
docker compose up -d postgres                       # healthy, volume-persisted DB (DB only)
docker compose ps                                   # postgres = healthy

uv run python -c "from agentic_scd.db import ping; print(ping())"   # SELECT 1 succeeds

uv run python scripts/db_dump.py                    # snapshot -> data/backups/
uv run python scripts/db_restore.py <snapshot>      # round-trips the snapshot back

uv run pytest -q                                    # green (connectivity test skips if no DB)
uv run ruff check .                                 # clean
uv run ruff format --check .                        # clean

docker compose down                                 # stop; data persists on pgdata
docker compose up -d postgres                       # data still present after restart
```

## Definition of done (merge gate)

All checklist boxes ticked, the commands above pass on a clean checkout (with Docker
Desktop running), the offline test suite stays green with **no DB up**, and the work is
scoped to Phase 0.5 only — **no Phase-1 schema/tables or other-phase logic leaked in**.
Open a PR from `phase-0.5-postgres-dev-services` into `main`; merge once verified.

## Explicitly NOT validated here (later phases)
- Signals table, schema, migrations, watermark/status flag — **Phase 1** (see
  [[data-ingestion]]).
- Ingestion collectors, normalization, relevance gate, dedupe, persistence logic —
  **Phase 1**.
- Chroma, FastAPI, React, full-stack containerization — **Phase 10**.
- Managed/cloud Postgres, secrets manager — **post-MVP (Phase 12)**.
