"""Restore a SQL snapshot into the dev Postgres.

Usage (Docker Desktop running, the postgres service up):

    uv run python scripts/db_restore.py data/backups/pgdump-YYYYmmdd-HHMMSS.sql

Pipes the given snapshot into ``docker compose exec -T postgres psql``. The
snapshot path may be absolute or relative to the repo root.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _common import REPO_ROOT, compose_exec_cmd, pg_env


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(
            "usage: uv run python scripts/db_restore.py <snapshot.sql>",
            file=sys.stderr,
        )
        return 2

    snapshot = Path(argv[0])
    if not snapshot.is_absolute():
        snapshot = (REPO_ROOT / snapshot).resolve()
    if not snapshot.is_file():
        print(f"error: snapshot not found: {snapshot}", file=sys.stderr)
        return 1

    cfg = pg_env()
    cmd = compose_exec_cmd(cfg, "psql", "-U", cfg["user"], "-d", cfg["db"])
    print(f"Restoring {snapshot} -> database '{cfg['db']}'")

    try:
        with snapshot.open("rb") as fh:
            proc = subprocess.run(cmd, stdin=fh, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(
            "error: `docker` not found. Install Docker Desktop and ensure it is "
            "on PATH.",
            file=sys.stderr,
        )
        return 1

    if proc.returncode != 0:
        sys.stderr.buffer.write(proc.stderr)
        print(
            "\nerror: psql restore failed. Is the postgres service up? "
            "(`docker compose up -d postgres`)",
            file=sys.stderr,
        )
        return proc.returncode

    print("Restore complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
