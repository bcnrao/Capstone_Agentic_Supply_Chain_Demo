from __future__ import annotations

import heapq

import numpy as np

from agentic_scd.agents.forecast import aggregate_risk
from agentic_scd.agents.schema import Classification, Forecast, ImpactMap


def impact_weights(impacts: list[ImpactMap]) -> list[int]:
    weights = []
    for impact in impacts:
        size = len(impact.affected_suppliers) + len(impact.affected_lanes) + len(impact.affected_facilities)
        weights.append(max(1, size))
    return weights or [1]


def simulate_iteration(rng: np.random.Generator, risk: float, weights: list[int], baseline_demand: float, adjusted_demand: float, inventory_days: float) -> tuple[float, float, float, float]:
    queue: list[tuple[float, str, int, float, float]] = []
    for idx, weight in enumerate(weights):
        start = float(rng.uniform(0.0, 2.0 + 0.25 * weight))
        duration = float(rng.gamma(shape=2.2 + risk * 1.4 + 0.08 * weight, scale=1.1 + 0.35 * risk))
        severity = float(0.45 + risk + rng.uniform(0.0, 0.25))
        heapq.heappush(queue, (start, "start", idx, duration, severity))
    clock = 0.0
    active = 0
    backlog = 0.0
    inventory = baseline_demand * max(1.0, inventory_days) / 7.0
    daily_demand = max(10.0, adjusted_demand / 7.0)
    max_delay = 0.0
    while queue:
        event_time, phase, node, duration, severity = heapq.heappop(queue)
        elapsed = max(0.0, event_time - clock)
        if elapsed and active:
            backlog += daily_demand * elapsed * active * (0.22 + 0.14 * severity)
            inventory -= daily_demand * elapsed * (0.12 + 0.05 * active)
        clock = event_time
        if phase == "start":
            active += 1
            max_delay = max(max_delay, duration)
            heapq.heappush(queue, (event_time + duration, "end", node, duration, severity))
        else:
            active = max(0, active - 1)
    inventory_effective = max(0.0, inventory) * max(0.05, 1 - (0.5 + 0.6 * risk + 0.08 * len(weights)))
    disruption_load = baseline_demand * risk * (0.45 + 0.12 * len(weights))
    shortage = max(0.0, backlog + disruption_load - inventory_effective)
    service_level = max(0.0, 1.0 - shortage / max(backlog + inventory + daily_demand, 1.0))
    revenue_impact = shortage * (18.0 + 7.5 * risk)
    recovery = max_delay + 1.5 + risk * 5.5
    return shortage, revenue_impact, recovery, service_level


def run_discrete_event(classifications: list[Classification], impacts: list[ImpactMap], forecast: Forecast | None, iterations: int) -> dict[str, float | int | str]:
    risk = aggregate_risk(classifications)
    affected = sum(len(item.affected_entities) for item in impacts)
    baseline_demand = float(np.mean(forecast.baseline)) if forecast and forecast.baseline else 900.0
    adjusted_demand = float(np.mean(forecast.adjusted)) if forecast and forecast.adjusted else baseline_demand * (1 - 0.18 * risk)
    inventory_days = max(1.0, forecast.inventory_days_left if forecast else 18.0)
    weights = impact_weights(impacts)
    seed = 97 + int(risk * 1000) + affected + int(baseline_demand) % 97
    rng = np.random.default_rng(seed)
    shortages = []
    revenues = []
    recoveries = []
    service_levels = []
    for _ in range(max(1, iterations)):
        shortage, revenue_impact, recovery, service_level = simulate_iteration(
            rng,
            risk,
            weights,
            baseline_demand,
            adjusted_demand,
            inventory_days,
        )
        shortages.append(shortage)
        revenues.append(revenue_impact)
        recoveries.append(recovery)
        service_levels.append(service_level)
    stockout = float(np.mean(np.array(shortages) > 0))
    assumptions = f"{iterations} discrete-event iterations, aggregate risk {risk:.2f}, affected network nodes {affected}, baseline demand {baseline_demand:.0f}."
    return {
        "stockout_probability": round(stockout, 4),
        "revenue_impact": round(float(np.mean(revenues)), 2),
        "recovery_time_days": round(float(np.percentile(recoveries, 80)), 1),
        "service_level": round(float(np.mean(service_levels)), 4),
        "expected_shortage_units": round(float(np.mean(shortages)), 2),
        "iterations": iterations,
        "assumptions": assumptions,
        "revenue_loss_p50": round(float(np.percentile(revenues, 50)), 2),
        "revenue_loss_p90": round(float(np.percentile(revenues, 90)), 2),
        "engine": "discrete_event_local",
    }
