"""Shared helpers for the Phase 0.5 dump/restore scripts.

These scripts wrap ``docker compose exec`` so they work identically on Windows
(Docker Desktop) and Unix, run via ``uv run``. They read the same ``POSTGRES_*``
vars that the Compose ``postgres`` service uses, sourced from the repo-root ``.env``.

This file lives at ``<repo>/backend/scripts/``: the Python project is under
``backend/`` while ``.env`` and ``docker-compose.yml`` live at the repo root, so the
backend root and the repo root are resolved separately, and the compose file is passed
with ``-f`` so the command works regardless of the current directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# <repo>/backend/scripts/_common.py -> parents[1] = backend, parents[2] = repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUPS_DIR = BACKEND_ROOT / "data" / "backups"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
COMPOSE_SERVICE = "postgres"


def pg_env() -> dict[str, str]:
    """Resolve Postgres connection parts from ``.env`` / the environment."""
    load_dotenv(REPO_ROOT / ".env")
    return {
        "db": os.getenv("POSTGRES_DB", "agentic_scd"),
        "user": os.getenv("POSTGRES_USER", "agentic"),
        "password": os.getenv("POSTGRES_PASSWORD", "agentic"),
    }


def compose_exec_cmd(cfg: dict[str, str], *inner: str) -> list[str]:
    """Build a ``docker compose exec -T`` command for the postgres service.

    The compose file is referenced with ``-f`` (its repo-root path) so the command
    works from any directory. Passes ``PGPASSWORD`` into the container so
    ``pg_dump`` / ``psql`` authenticate non-interactively.
    """
    return [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "exec",
        "-T",
        "-e",
        f"PGPASSWORD={cfg['password']}",
        COMPOSE_SERVICE,
        *inner,
    ]
