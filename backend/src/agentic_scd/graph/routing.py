from __future__ import annotations

PRE_CLASSIFY_STEPS = ("ingestion", "input_guardrail", "seed", "news", "weather", "classify")

# Unified pipeline: every signal, regardless of severity, runs the full set of
# agents.  The former severity-based shortcuts have been removed so no agent is
# ever skipped:
#   HIGH / MEDIUM / LOW  ->  impact -> forecast -> simulate -> recommend
# Severity still drives risk_level (for urgency/display), but never the route.
FULL_PATH_STEPS = ("impact", "forecast", "simulate", "recommend", "output_guardrail")

ROUTE_STEPS = {"full_path": FULL_PATH_STEPS}
ROUTE_ENTRIES = {"full_path": "impact"}


def resolve_route(state: dict) -> str:
    """Every signal runs the full pipeline. Kept for API compatibility."""
    return "full_path"


def route_steps(state: dict) -> tuple:
    return FULL_PATH_STEPS


def route_entry_node(state: dict) -> str:
    return "full_path"


def route_exit_edges() -> dict:
    return dict(ROUTE_ENTRIES)
