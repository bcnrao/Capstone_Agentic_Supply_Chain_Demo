"""Thin Postgres connectivity seam.

Phase 0.5 is infra only — there are no tables, schema, or migrations yet. This
module just proves the local ``uv`` app can reach the Compose-managed Postgres
over ``settings.database_url``. Following the same offline-runnable contract as
``llm/client.py``, it degrades **gracefully**: when no DB is configured or the
server is unreachable, ``ping`` returns a clear failure status instead of
raising an unhandled error.
"""

from dataclasses import dataclass

import psycopg

from agentic_scd.config import Settings, get_settings

# Bound connection attempts so an unreachable DB fails fast instead of hanging on a
# dropped SYN (keeps ping() and the DB-skip tests prompt). libpq clamps this to >= 2s.
CONNECT_TIMEOUT_SECONDS = 5


class DatabaseNotConfiguredError(RuntimeError):
    """Raised by ``connect`` when no ``database_url`` is configured."""


@dataclass(frozen=True)
class PingResult:
    """Outcome of a connectivity check.

    ``ok`` is True only when a connection opened and ``SELECT 1`` returned. The
    human-readable ``detail`` explains why a check failed (no config / server
    down) so callers and demos get a clear message without crashing.
    """

    ok: bool
    detail: str

    def __bool__(self) -> bool:
        return self.ok


def connect(
    settings: Settings | None = None, *, connect_timeout: int = CONNECT_TIMEOUT_SECONDS
) -> psycopg.Connection:
    """Open a new Postgres connection from ``settings.database_url``.

    A bounded ``connect_timeout`` keeps the offline contract real: when no server is
    listening, some networks drop the SYN and the OS retransmits for ~20s before
    giving up. The timeout makes an unreachable DB fail fast (raising
    ``OperationalError``) so ``ping`` and the DB-skip tests degrade promptly instead
    of hanging.

    Raises:
        DatabaseNotConfiguredError: if no ``database_url`` is configured.
        psycopg.OperationalError: if the server cannot be reached.
    """
    settings = settings or get_settings()
    if not settings.database_url:
        raise DatabaseNotConfiguredError(
            "No DATABASE_URL configured (set DATABASE_URL or the POSTGRES_* "
            "vars in .env); see .env.example."
        )
    return psycopg.connect(settings.database_url, connect_timeout=connect_timeout)


def ping(settings: Settings | None = None) -> PingResult:
    """Check connectivity by running ``SELECT 1``.

    Never raises for the expected offline cases (no config, server down): those
    return ``PingResult(ok=False, ...)`` so the app stays offline-runnable.
    """
    settings = settings or get_settings()
    if not settings.database_url:
        return PingResult(
            ok=False,
            detail="database not configured (no DATABASE_URL / POSTGRES_* set)",
        )

    try:
        with connect(settings) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
    except psycopg.OperationalError as exc:
        # Server unreachable / auth failure — expected when the DB is not up.
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
        return PingResult(ok=False, detail=f"database unreachable: {message}")

    if row == (1,):
        return PingResult(ok=True, detail="SELECT 1 ok")
    return PingResult(ok=False, detail=f"unexpected result from SELECT 1: {row!r}")
