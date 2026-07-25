"""Central LangSmith tracing configuration for the LangGraph pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

GRAPH_NAME = "supply-chain-disruption-pipeline"
GRAPH_RUN_NAME = "Supply Chain Disruption Pipeline"

_configured = False

# Legacy env names still accepted for backwards compatibility.
_LEGACY_TO_MODERN = (
    ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"),
    ("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"),
    ("LANGCHAIN_PROJECT", "LANGSMITH_PROJECT"),
)


def _copy_if_unset(source: str, dest: str) -> None:
    if os.getenv(dest):
        return
    value = os.getenv(source)
    if value is not None and value != "":
        os.environ[dest] = value


def configure_tracing() -> bool:
    """Normalize LangSmith env vars and report whether tracing is enabled.

    Prefer modern ``LANGSMITH_*`` names. If only legacy ``LANGCHAIN_*`` values
    are set, copy them into the modern names so the SDK picks them up.
    Safe to call multiple times.
    """
    global _configured

    load_dotenv()

    for legacy, modern in _LEGACY_TO_MODERN:
        _copy_if_unset(legacy, modern)

    # Keep the older flag in sync when only LANGSMITH_TRACING is set, so any
    # residual LANGCHAIN_TRACING_V2 readers still see tracing enabled.
    if os.getenv("LANGSMITH_TRACING") and not os.getenv("LANGCHAIN_TRACING_V2"):
        os.environ["LANGCHAIN_TRACING_V2"] = os.environ["LANGSMITH_TRACING"]

    # Do not upload traces from pytest (avoids noise / accidental Cloud spam).
    if "PYTEST_CURRENT_TEST" in os.environ:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"

    enabled = os.getenv("LANGSMITH_TRACING", "").strip().lower() in {"1", "true", "yes", "on"}
    has_key = bool(os.getenv("LANGSMITH_API_KEY", "").strip())

    if not _configured:
        if enabled and has_key:
            project = os.getenv("LANGSMITH_PROJECT") or "default"
            logger.info("LangSmith tracing enabled (project=%s)", project)
        elif enabled and not has_key:
            logger.warning(
                "LANGSMITH_TRACING is set but LANGSMITH_API_KEY is missing; traces will not upload"
            )
        _configured = True

    return enabled and has_key


def _optional_meta(key: str, value: str | None) -> dict[str, str]:
    if value is None:
        return {}
    cleaned = value.strip()
    if not cleaned:
        return {}
    return {key: cleaned}


def build_run_config(
    *,
    run_id: str | None = None,
    scenario_name: str | None = None,
    request_id: str | None = None,
    model_name: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Build a LangGraph invoke ``config`` with run name, tags, and metadata.

    Only includes metadata fields that are actually available — never invents
    user/thread/session/tenant identifiers.
    """
    configure_tracing()

    app_name = os.getenv("APP_NAME", "").strip()
    app_version = os.getenv("APP_VERSION", "").strip()
    app_env = os.getenv("APP_ENV", "").strip()

    metadata: dict[str, str] = {"graph_name": GRAPH_NAME}
    metadata.update(_optional_meta("app_name", app_name or None))
    metadata.update(_optional_meta("app_version", app_version or None))
    metadata.update(_optional_meta("app_env", app_env or None))
    metadata.update(_optional_meta("run_id", run_id))
    metadata.update(_optional_meta("scenario_name", scenario_name))
    metadata.update(_optional_meta("request_id", request_id))
    metadata.update(_optional_meta("model_name", model_name))
    metadata.update(_optional_meta("provider", provider))

    tags = [GRAPH_NAME]
    if app_env:
        tags.append(app_env)

    return {
        "run_name": GRAPH_RUN_NAME,
        "tags": tags,
        "metadata": metadata,
    }
