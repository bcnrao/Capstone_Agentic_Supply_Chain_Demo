from __future__ import annotations

PRE_CLASSIFY_STEPS = ("ingestion", "input_guardrail", "seed", "news", "weather", "classify")

# Per-spec routing:
#   HIGH  (>7)  -> skip RAG and forecast, go straight to simulation
#   MEDIUM(4-7) -> full pipeline: impact -> forecast -> simulate -> recommend
#   LOW   (<=3) -> skip impact analysis, monitor only
ROUTE_STEPS = {
    "high_path_simulation_first": ("simulate", "recommend", "output_guardrail"),
    "full_path":                  ("impact", "forecast", "simulate", "recommend", "output_guardrail"),
    "monitor_only":               ("recommend", "output_guardrail"),
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
    """Pick the pipeline route.

    Per spec:
      HIGH (>7)   -> high_path_simulation_first (skip impact + forecast)
      MEDIUM (4-7)-> full_path (impact + forecast + simulate)
      LOW (<=3)   -> monitor_only (skip impact)

    Special case: when a HIGH signal co-occurs with MEDIUM signals in the
    same run (live feeds can return multiple signals), dropping straight to
    high_path would skip impact + forecast for the MEDIUM signals entirely.
    In that case the route falls back to full_path so every MEDIUM signal
    gets impact mapping and demand forecast, while the HIGH signal's risk
    score is folded in by aggregate_risk() in simulate_node.
    A pure-HIGH run (no MEDIUM signals) still takes high_path as specified.
    """
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
    # If the overall winner is HIGH but MEDIUM signals are also present,
    # use full_path so impact + forecast run for the MEDIUM signals.
    # The HIGH signal still contributes to aggregate_risk in simulation.
    if chosen == "high_path_simulation_first":
        medium_present = any(
            4.0 <= float(getattr(r, "severity", 0.0)) <= 7.0
            for r in rows
        )
        if medium_present:
            return "full_path"
    return chosen


def route_steps(state: dict) -> tuple:
    route = resolve_route(state)
    return ROUTE_STEPS.get(route, ROUTE_STEPS["full_path"])


def route_entry_node(state: dict) -> str:
    return resolve_route(state)


def route_exit_edges() -> dict:
    return dict(ROUTE_ENTRIES)
