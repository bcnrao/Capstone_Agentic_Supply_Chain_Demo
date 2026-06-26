"""Phase 0.5 connectivity test.

Stays green fully offline: when no Postgres is reachable, the test ``skip``s
cleanly rather than failing. With the Compose ``postgres`` service up (and
``DATABASE_URL`` configured), ``ping()`` runs ``SELECT 1`` and succeeds.
"""

import pytest

from agentic_scd.config.settings import Settings
from agentic_scd.db import DatabaseNotConfiguredError, PingResult, connect, ping


def test_ping_graceful_when_unconfigured() -> None:
    # No database_url configured -> graceful failure, never a crash.
    settings = Settings(
        groq_api_key=None, groq_model="unused", use_mock_llm=True, database_url=None
    )
    result = ping(settings)
    assert isinstance(result, PingResult)
    assert result.ok is False
    assert not result  # __bool__ reflects ok
    assert "not configured" in result.detail


def test_connect_raises_when_unconfigured() -> None:
    settings = Settings(
        groq_api_key=None, groq_model="unused", use_mock_llm=True, database_url=None
    )
    with pytest.raises(DatabaseNotConfiguredError):
        connect(settings)


def test_ping_live_database_if_available() -> None:
    # Uses the real process settings (.env / env). Skip cleanly when no DB is up
    # so the suite passes offline; assert success when one is reachable.
    result = ping()
    if not result.ok:
        pytest.skip(f"no Postgres reachable ({result.detail})")
    assert result.detail == "SELECT 1 ok"
