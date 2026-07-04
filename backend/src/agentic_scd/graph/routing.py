from __future__ import annotations

PRE_CLASSIFY_STEPS = ("ingestion", "input_guardrail", "seed", "news", "weather", "classify")

ROUTE_STEPS = {
    "high_path_simulation_first": ("simulate", "recommend", "output_guardrail"),
    "full_path": ("impact", "forecast", "simulate", "recommend", "output_guardrail"),
    "monitor_only": ("recommend", "output_guardrail"),
}

ROUTE_ENTRIES = {
    "high_path_simulation_first": "simulate",
    "full_path": "impact",
    "monitor_only": "recommend",
}


def route_priority(route: str) -> int:
    return {
        "monitor_only": 1,
        "full_path": 2,
        "high_path_simulation_first": 3,
    }.get(route, 0)


def resolve_route(state: dict) -> str:
    rows = state.get("classifications", []) or []
    chosen = "monitor_only"
    best_score = (-1.0, -1)
    for row in rows:
        route = getattr(row, "route", "monitor_only") or "monitor_only"
        score = (float(getattr(row, "severity", 0.0)), route_priority(route))
        if score >= best_score:
            chosen = route
            best_score = score
    if best_score == (-1.0, -1):
        return "monitor_only" if not state.get("new_signals") else "full_path"
    return chosen


def route_steps(state: dict) -> tuple[str, ...]:
    route = resolve_route(state)
    return ROUTE_STEPS.get(route, ROUTE_STEPS["full_path"])


def route_entry_node(state: dict) -> str:
    return resolve_route(state)


def route_exit_edges() -> dict[str, str]:
    return dict(ROUTE_ENTRIES)
