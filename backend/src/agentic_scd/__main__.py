from __future__ import annotations

import argparse
import json
import uuid

from agentic_scd.config import get_settings
from agentic_scd.db import connect, init_db
from agentic_scd.graph import GraphState, build_graph
from agentic_scd.ingestion.store import mark_done, save_run_result, serialize_state
from agentic_scd.observability import build_run_config, configure_tracing, invoke_traced_pipeline


def run(scenario_name: str | None = None) -> GraphState:
    # Signals come from the DB inbox (filled separately via collect() / the
    # "Refresh external data" button) or a named scenario's seed. The pipeline
    # itself never fetches live data.
    configure_tracing()
    graph = build_graph()
    run_id = str(uuid.uuid4())
    initial: dict = {"run_id": run_id}
    if scenario_name:
        initial["scenario_name"] = scenario_name
    settings = get_settings()
    config = build_run_config(
        run_id=run_id,
        scenario_name=scenario_name,
        model_name=settings.groq_model,
        provider="groq" if not settings.llm_is_mock else "mock",
    )
    result: GraphState = invoke_traced_pipeline(graph, initial, config)
    result["run_id"] = run_id
    if scenario_name:
        result["scenario_name"] = scenario_name
    try:
        init_db()
        with connect() as conn:
            save_run_result(conn, run_id, result, scenario_name)
            mark_done(conn, [signal.signal_id for signal in result.get("new_signals", [])])
            conn.commit()
    except Exception:
        pass
    return result


def print_summary(state: GraphState) -> None:
    signals = state.get("new_signals", [])
    weather_risks = state.get("weather_risks", [])
    classifications = state.get("classifications", [])
    impacts = state.get("impacts", [])
    forecast = state.get("forecast")
    simulation = state.get("simulation")
    recommendation = state.get("recommendation")
    print(f"Pipeline run complete - {len(signals)} signal(s), run_id={state.get('run_id')}")
    print(f"Route: {state.get('route', 'not set')}\n")
    print("Signals")
    for signal in signals:
        region = f" ({signal.region})" if signal.region else ""
        print(f"  - [{signal.source_type}] {signal.title}{region}")
    if weather_risks:
        print("\nWeather hub risks")
        for risk in weather_risks:
            hub = risk.hub_port or risk.region or "hub"
            ops = ", ".join(risk.affected_operations) or "none"
            print(f"  - {hub}: severity {risk.aggregate_severity:.1f}/10 over {risk.horizon_days}d, peak {risk.peak_day}, port risk {risk.port_disruption_risk:.0%}, ops {ops}")
    print("\nRisk classification")
    for row in classifications:
        print(f"  - {row.category}: severity {row.severity:.1f}/10, risk {row.risk_score:.2f}, {row.risk_level}, confidence {row.confidence:.2f}")
    print("\nImpact map")
    for item in impacts:
        print(f"  - suppliers={', '.join(item.affected_suppliers)} | lanes={', '.join(item.affected_lanes)}")
    if forecast:
        print(f"\nForecast: deviation {forecast.demand_deviation_pct:.1f}%, inventory days left {forecast.inventory_days_left:.1f}, predicted delay {forecast.predicted_delay_days:.1f} days")
    if simulation:
        print(f"Simulation: stockout {simulation.stockout_probability:.0%}, service level {simulation.service_level:.0%}, revenue impact {simulation.revenue_impact:,.0f}, p90 loss {simulation.revenue_loss_p90:,.0f}")
    if recommendation:
        print("\nMitigation plan")
        for action in recommendation.actions:
            print(f"  - {action}")
        print(f"  {recommendation.summary}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="agentic-scd")
    parser.add_argument("--scenario", default=None, help="Run a named demo scenario from the scenario library")
    parser.add_argument("--json", action="store_true", help="Print the final graph state as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    state = run(args.scenario)
    if args.json:
        print(json.dumps(serialize_state(state), indent=2, default=str))
    else:
        print_summary(state)


if __name__ == "__main__":
    main()
