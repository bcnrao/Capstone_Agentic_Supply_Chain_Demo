"""Shared helpers for the Phase 0.5 dump/restore scripts.

These scripts wrap ``docker compose exec`` so they work identically on Windows
(Docker Desktop) and Unix, run via ``uv run``. They read the same ``POSTGRES_*``
vars that the Compose ``postgres`` service uses, sourced from the project-root
``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root = parent of this scripts/ directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUPS_DIR = REPO_ROOT / "data" / "backups"
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

    Passes ``PGPASSWORD`` into the container so ``pg_dump`` / ``psql`` authenticate
    non-interactively.
    """
    return [
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        f"PGPASSWORD={cfg['password']}",
        COMPOSE_SERVICE,
        *inner,
    ]
