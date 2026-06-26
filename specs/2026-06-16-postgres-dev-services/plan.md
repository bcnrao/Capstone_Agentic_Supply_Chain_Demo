# Phase 0.5 — Dev Data Services (Postgres) · Plan

Numbered task groups. Each group is independently reviewable; the order respects
dependencies (compose + config before the connectivity helper that uses them, before
the scripts that exec into the running service). Scope and decisions in [[requirements]];
success criteria in [[validation]].

---

## 1. Compose service (`docker-compose.yml`)
1.1 Author a root `docker-compose.yml` with a single **`postgres`** service using the
    pinned image **`postgres:16-alpine`**.
1.2 Wire env from `.env`: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (Compose
    reads `.env` in the project root automatically).
1.3 Add a **`pg_isready`** healthcheck (interval/retries/timeout) so the service reports
    `healthy`.
1.4 Map the host port (`${POSTGRES_PORT}:5432`) so the local `uv` app can connect.
1.5 Mount a **named volume `pgdata`** at `/var/lib/postgresql/data`; declare it under
    top-level `volumes:`. **No bind mount** of the data dir.
1.6 Confirm `docker compose up postgres` brings up **just the database**.

## 2. Configuration & `.env` handling
2.1 Add to `.env.example` (documented): `POSTGRES_DB`, `POSTGRES_USER`,
    `POSTGRES_PASSWORD`, `POSTGRES_HOST` (default `localhost`), `POSTGRES_PORT`
    (default `5432`), and a derived **`DATABASE_URL`**
    (`postgresql://USER:PASSWORD@HOST:PORT/DB`).
2.2 Extend `config/settings.py`: add a `database_url: str | None` field to `Settings`
    and populate it in `get_settings()` (prefer an explicit `DATABASE_URL`; otherwise
    assemble it from the `POSTGRES_*` parts). Keep the existing graceful-degradation
    pattern.
2.3 Verify `.env` remains git-ignored; no secret committed.

## 3. Thin DB connectivity layer
3.1 `uv add "psycopg[binary]"` (only this dependency is added in Phase 0.5).
3.2 Add a `db` module (`src/agentic_scd/db/`) exposing a connection helper and a
    **`ping()`** that opens a connection from `settings.database_url` and runs
    `SELECT 1`.
3.3 Fail **gracefully** when the DB is unreachable — return a clear status / raise a
    typed, caught error rather than an unhandled crash; the rest of the app stays
    offline-runnable.

## 4. Backup / restore scripts
4.1 Add `scripts/db_dump.py` and `scripts/db_restore.py` (cross-platform Python, run via
    `uv run`), each wrapping `docker compose exec -T postgres` → `pg_dump` / `psql`.
4.2 Dumps write timestamped files to **`data/backups/`**; restore reads a given snapshot
    back into the DB.
4.3 Gitignore **`data/backups/`** (keep the directory via a tracked `.gitkeep` if
    desired).
4.4 Verify a **round-trip**: dump → make a change / drop → restore reproduces the data.

## 5. Quality baseline (CI-lite)
5.1 Add a `pytest` connectivity test that calls `db.ping()` and **skips cleanly**
    (`pytest.skip`) when no DB is reachable — the suite stays green fully offline.
5.2 Ensure `ruff check` and `ruff format --check` pass on the whole tree (compose YAML
    excluded; new Python under the lint bar).

## 6. Docs & wrap-up
6.1 README section: `docker compose up -d postgres`, connect via `DATABASE_URL`, and the
    `uv run` dump/restore round-trip; note Docker Desktop is required and the DB-only
    scope.
6.2 Confirm all [[validation]] criteria pass; open a PR from
    `phase-0.5-postgres-dev-services` into `main`.
