# Phase 0.5 — Dev Data Services (Postgres) · Requirements

> Roadmap phase: **Phase 0.5 — Dev data services (Docker Compose for Postgres)**
> (see [[roadmap]]).
> Guidance: [[mission]] (capstone MVP; local-first, no cloud, always demoable),
> [[tech-stack]] (local PostgreSQL system of record; Docker compose as an *additional*
> run path; local `uv` workflow stays the dev default). Consumed first by [[data-ingestion]].

## Goal

Stand up a throwaway **local Postgres** via Docker Compose so the database exists from
**Phase 1** onward, while the app keeps running on the local `uv` workflow and connects
over an `.env` connection string. Persist data on a named `pgdata` volume and provide
`pg_dump`/restore scripts that round-trip a snapshot to a gitignored `data/backups/`.

This phase is **infra + a thin connectivity seam** — there are **no tables, schema, or
migrations yet** (those land in Phase 1 with the signals table). It only proves that a
healthy, volume-persisted Postgres comes up and the app can connect to it.

**Roadmap "Done when":** `docker compose up postgres` brings up a healthy,
volume-persisted Postgres the app connects to, and the dump/restore scripts round-trip
a snapshot to `data/backups/`.

## In scope

1. **Compose service** — a root `docker-compose.yml` with a single **`postgres`**
   service (`postgres:16-alpine`), a `pg_isready` healthcheck, env (`POSTGRES_DB` /
   `POSTGRES_USER` / `POSTGRES_PASSWORD`) sourced from `.env`, a host port mapping, and
   a named **`pgdata`** volume. `docker compose up postgres` runs **just the database**;
   nothing else is containerized in this phase.
2. **Config & `.env`** — add `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
   `POSTGRES_HOST`, `POSTGRES_PORT` **and** a derived `DATABASE_URL` to `.env.example`;
   extend `config/settings.py` (`Settings` + `get_settings`) with a `database_url`
   field. Every var documented; `.env` stays git-ignored.
3. **Thin DB connectivity layer** — add `psycopg[binary]`; a small `db` module exposing
   a connection/`ping()` helper that runs `SELECT 1`. It must fail **gracefully** (clear
   message, no crash) when the DB is not up, preserving offline-runnability.
4. **Backup/restore scripts** — cross-platform **Python** scripts under `scripts/`,
   invoked via `uv run`, wrapping `docker compose exec` → `pg_dump` / `psql`. They write
   to / read from `data/backups/`, which is **gitignored**.
5. **Quality + tests** — a `pytest` connectivity test that **skips cleanly** when no DB
   is reachable, so the suite still passes fully offline; `ruff check` and
   `ruff format --check` stay clean.
6. **Docs & wrap-up** — a README section covering `docker compose up postgres`,
   connecting, and the dump/restore round-trip.

## Out of scope (deferred to later phases)

- **Tables / schema / migrations** (the signals table, watermark/status flag, indexes)
  — **Phase 1** (full design in [[data-ingestion]]).
- Ingestion collectors, normalization, relevance gate, dedupe, persistence logic —
  **Phase 1**.
- **Chroma** vector store, **FastAPI**, **React** — their own later phases.
- **Full-stack containerization** (app + Chroma + React layered onto this same compose)
  — **Phase 10**.
- **Managed/cloud Postgres**, secrets manager — **post-MVP (Phase 12)**.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| DB scope this phase | **Thin connectivity layer** (`psycopg` + `db.ping()` + smoke test), no schema | Makes the roadmap "the app connects to" real and testable without leaking Phase-1 schema work. |
| Postgres image | **`postgres:16-alpine`** (pinned) | Stable, widely used major; small Alpine image → fast pulls on Docker Desktop. |
| Dump/restore scripts | **Cross-platform Python via `uv run`** wrapping `docker compose exec` | Consistent with the `uv` dev workflow; runs natively on Windows 11 / Docker Desktop (no Git Bash dependency). |
| Connection config | **Both** individual `POSTGRES_*` parts **and** a derived `DATABASE_URL` | Parts feed the compose service (`POSTGRES_DB/USER/PASSWORD`); the app connects via `DATABASE_URL` — matches the roadmap wording exactly and keeps the Tier-2 swap a connection-string change. |
| Data persistence | **Named `pgdata` volume** (not a bind mount) | Robust on Windows / Docker Desktop; survives restarts and rebuilds (per [[roadmap]]). |

## Open questions / notes

- Requires **Docker Desktop** running locally; no host Postgres install needed.
- Seed/demo data is kept portable via `pg_dump` snapshots in `data/backups/` (gitignored)
  rather than bind-mounting the Postgres data directory.
- The local `uv` workflow remains the dev default — Docker here runs **only** the DB.
- Heavier per-agent libs stay deferred; only `psycopg` is added in this phase.
