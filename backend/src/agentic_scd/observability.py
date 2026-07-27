"""Central LangSmith tracing configuration for the LangGraph pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from langsmith import get_current_run_tree, traceable

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


def _serialize_item(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def build_judge_outputs(state: dict[str, Any]) -> dict[str, Any]:
    """Plain JSON payload for LangSmith online LLM-as-judge variable mapping."""
    recommendation = state.get("recommendation")
    classifications = state.get("classifications") or []
    signals = state.get("new_signals") or []
    top = classifications[0] if classifications else None

    rec_dict = _serialize_item(recommendation) if recommendation is not None else None
    if isinstance(rec_dict, dict):
        recommendation_out: dict[str, Any] | None = {
            "summary": rec_dict.get("summary", ""),
            "actions": rec_dict.get("actions") or [],
            "structured_actions": rec_dict.get("structured_actions") or [],
            "evidence": rec_dict.get("evidence") or [],
            "generation_mode": rec_dict.get("generation_mode", ""),
        }
    else:
        recommendation_out = None

    top_classification = None
    if top is not None:
        if hasattr(top, "model_dump"):
            dumped = top.model_dump(mode="json")
            top_classification = {
                "category": dumped.get("category"),
                "severity": dumped.get("severity"),
                "rationale": dumped.get("rationale"),
            }
        elif isinstance(top, dict):
            top_classification = {
                "category": top.get("category"),
                "severity": top.get("severity"),
                "rationale": top.get("rationale"),
            }

    return {
        "recommendation": recommendation_out,
        "route": state.get("route"),
        "top_classification": top_classification,
        "signal_titles": [
            getattr(signal, "title", None) or (signal.get("title") if isinstance(signal, dict) else None)
            for signal in signals
        ],
        "scenario_name": state.get("scenario_name"),
        "run_id": state.get("run_id"),
    }


def build_judge_inputs(initial: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Compact input context for the online judge (scenario + signal titles)."""
    signals = state.get("new_signals") or []
    titles = [
        getattr(signal, "title", None) or (signal.get("title") if isinstance(signal, dict) else None)
        for signal in signals
    ]
    return {
        "scenario_name": initial.get("scenario_name") or state.get("scenario_name"),
        "signal_titles": [title for title in titles if title],
        "use_pending_signals": bool(initial.get("use_pending_signals")),
    }


def attach_judge_io(initial: dict[str, Any], state: dict[str, Any]) -> None:
    """Merge judge-friendly inputs onto the current LangSmith run tree.

    Outputs are handled by ``process_outputs`` on ``invoke_traced_pipeline`` so
    the ``@traceable`` decorator does not overwrite them with the raw return value.
    """
    if not configure_tracing():
        return
    try:
        run_tree = get_current_run_tree()
        if run_tree is None:
            return
        run_tree.inputs = {**(run_tree.inputs or {}), **build_judge_inputs(initial, state)}
    except Exception as exc:
        logger.debug("Could not attach LangSmith judge inputs: %s", exc)


def _process_pipeline_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Serialize only judge-relevant args (avoid dumping the graph object)."""
    initial = inputs.get("initial") if isinstance(inputs, dict) else None
    if not isinstance(initial, dict):
        return {"scenario_name": None, "use_pending_signals": False, "run_id": None}
    return {
        "scenario_name": initial.get("scenario_name"),
        "use_pending_signals": bool(initial.get("use_pending_signals")),
        "run_id": initial.get("run_id"),
    }


def _process_pipeline_outputs(outputs: Any) -> dict[str, Any]:
    """Keep root-run outputs as a plain recommendation payload for online judges."""
    if isinstance(outputs, dict):
        return build_judge_outputs(outputs)
    return {"output": outputs}


@traceable(
    name=GRAPH_RUN_NAME,
    run_type="chain",
    process_inputs=_process_pipeline_inputs,
    process_outputs=_process_pipeline_outputs,
)
def invoke_traced_pipeline(graph: Any, initial: dict[str, Any], config: dict[str, Any]) -> Any:
    """Invoke the LangGraph and attach plain recommendation I/O for online evaluators.

    The ``@traceable`` wrapper is the root run named ``Supply Chain Disruption Pipeline``
    that online LLM-as-judge filters should target.
    """
    # Nested LangGraph spans keep tags/metadata; root name comes from @traceable.
    lg_config = {key: value for key, value in config.items() if key != "run_name"}
    result = graph.invoke(initial, config=lg_config)
    if isinstance(result, dict):
        enriched = dict(result)
        if initial.get("run_id"):
            enriched["run_id"] = initial["run_id"]
        if initial.get("scenario_name"):
            enriched["scenario_name"] = initial["scenario_name"]
        attach_judge_io(initial, enriched)
        return enriched
    return result
