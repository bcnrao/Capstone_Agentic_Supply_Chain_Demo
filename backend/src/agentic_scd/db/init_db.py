"""Idempotent schema initialization.

Applies ``schema.sql`` (plain DDL, ``CREATE ... IF NOT EXISTS``) over the Phase 0.5
``connect()`` seam — no ORM, no Alembic. Following the same offline-runnable contract
as ``ping()``: when no DB is configured or reachable, ``init_db`` returns ``False``
instead of raising, so the collector and tests stay green fully offline.
"""

from pathlib import Path

import psycopg

from agentic_scd.config import Settings
from agentic_scd.db.client import DatabaseNotConfiguredError, connect

SCHEMA_SQL_PATH = Path(__file__).with_name("schema.sql")


def schema_sql() -> str:
    """Return the bundled DDL script text."""
    return SCHEMA_SQL_PATH.read_text(encoding="utf-8")


def init_db(settings: Settings | None = None) -> bool:
    """Create the ``signals`` and ``seen_rejected`` tables if absent.

    Idempotent: re-running is a no-op. Returns ``True`` when the DDL was applied,
    ``False`` when no DB is configured/reachable (never raises for those expected
    offline cases, matching ``db.ping``).
    """
    try:
        with connect(settings) as conn, conn.cursor() as cur:
            cur.execute(schema_sql())
            conn.commit()
    except (DatabaseNotConfiguredError, psycopg.OperationalError):
        return False
    return True
