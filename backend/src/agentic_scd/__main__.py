"""Console entrypoint: run the end-to-end pipeline and print a stage-by-stage summary.

Runs fully offline with no API key, DB, or network (a synthetic seed guarantees a
result). Exposed as the ``agentic-scd`` console script and via ``python -m``.
The Gradio dashboard (`agentic-scd-dashboard`) renders the same run visually.
"""

from agentic_scd.graph import GraphState, build_graph


def run() -> GraphState:
    """Build and invoke the graph, returning the final state."""
    graph = build_graph()
    result: GraphState = graph.invoke({})
    return result


def main() -> None:
    """CLI entrypoint: run the pipeline and print each stage's result."""
    state = run()
    signals = state.get("new_signals", [])
    classifications = state.get("classifications", [])
    impacts = state.get("impacts", [])
    forecast = state.get("forecast")
    simulation = state.get("simulation")
    recommendation = state.get("recommendation")

    print(f"Pipeline run complete - {len(signals)} signal(s) through the chain.\n")

    print("Signals:")
    for signal in signals:
        print(f"  - [{signal.source_type}] {signal.title}")

    print("\nClassification:")
    for c in classifications:
        print(f"  - {c.category} (risk {c.risk_score:.2f}): {c.rationale}")

    print("\nImpact:")
    for i in impacts:
        print(f"  - {', '.join(i.affected_entities)}")

    if forecast:
        print(
            f"\nForecast: baseline {forecast.baseline[0]:.0f} -> "
            f"adjusted {forecast.adjusted[-1]:.1f} ({forecast.note})"
        )
    if simulation:
        print(
            f"Simulation: stockout {simulation.stockout_probability:.0%}, "
            f"revenue impact {simulation.revenue_impact:,.0f}"
        )
    if recommendation:
        print("\nRecommended actions:")
        for action in recommendation.actions:
            print(f"  - {action}")
        print(f"  ({recommendation.summary})")


if __name__ == "__main__":
    main()
