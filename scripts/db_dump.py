"""Dump the dev Postgres to a timestamped SQL snapshot in ``data/backups/``.

Usage (Docker Desktop running, the postgres service up):

    uv run python scripts/db_dump.py

Wraps ``docker compose exec -T postgres pg_dump`` and writes the plain-SQL dump
to ``data/backups/pgdump-YYYYmmdd-HHMMSS.sql`` (gitignored). Prints the path of
the snapshot it created.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime

from _common import BACKUPS_DIR, compose_exec_cmd, pg_env


def main() -> int:
    cfg = pg_env()
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = BACKUPS_DIR / f"pgdump-{stamp}.sql"

    cmd = compose_exec_cmd(cfg, "pg_dump", "-U", cfg["user"], cfg["db"])
    print(f"Dumping database '{cfg['db']}' -> {out_path}")

    try:
        with out_path.open("wb") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(
            "error: `docker` not found. Install Docker Desktop and ensure it is "
            "on PATH.",
            file=sys.stderr,
        )
        return 1

    if proc.returncode != 0:
        out_path.unlink(missing_ok=True)
        sys.stderr.buffer.write(proc.stderr)
        print(
            "\nerror: pg_dump failed. Is the postgres service up? "
            "(`docker compose up -d postgres`)",
            file=sys.stderr,
        )
        return proc.returncode

    print(f"Wrote snapshot: {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
