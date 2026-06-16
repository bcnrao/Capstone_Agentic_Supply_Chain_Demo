"""Thin Postgres connectivity layer (see ``client``)."""

from agentic_scd.db.client import (
    DatabaseNotConfiguredError,
    PingResult,
    connect,
    ping,
)
