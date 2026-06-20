"""Offline test doubles for the batch loaders & CLI (no DB, no network).

``FakeConn`` emulates just the handful of SQL operations the ingest tail performs
(``is_duplicate`` lookup, ``persist_signal`` insert w/ ON CONFLICT, ``record_rejected``)
so loader **idempotency** can be exercised without Postgres — a second run of the same
snapshot persists no new rows. ``make_settings`` builds an offline ``Settings``.
"""

from agentic_scd.config import Settings


def make_settings(**overrides) -> Settings:
    """Build an offline ``Settings`` (no DB) with optional field overrides."""
    base = dict(
        groq_api_key=None,
        groq_model="mock",
        use_mock_llm=True,
        database_url=None,
    )
    base.update(overrides)
    return Settings(**base)


class FakeCursor:
    def __init__(self, store: "FakeConn") -> None:
        self._store = store
        self._result: tuple | None = None
        self.rowcount = 0

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:  # noqa: ANN001
        text = " ".join(sql.split())
        if "INSERT INTO signals" in text:
            dedup = params["dedup_hash"]
            if dedup in self._store.signals:
                self.rowcount = 0
            else:
                self._store.signals.add(dedup)
                self.rowcount = 1
        elif "FROM seen_rejected" in text and "UNION" in text:
            dedup = params[0]
            hit = dedup in self._store.signals or dedup in self._store.rejected
            self._result = (1,) if hit else None
        elif "INSERT INTO seen_rejected" in text:
            self._store.rejected.add(params[0])
            self.rowcount = 1
        else:  # pragma: no cover - unexpected SQL in these tests
            raise AssertionError(f"unexpected SQL: {text}")

    def fetchone(self) -> tuple | None:
        return self._result


class FakeConn:
    """In-memory stand-in for a psycopg connection used by the ingest tail."""

    def __init__(self) -> None:
        self.signals: set[str] = set()
        self.rejected: set[str] = set()
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:  # pragma: no cover - parity with real conn
        return None
