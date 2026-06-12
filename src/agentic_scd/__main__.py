"""Console entrypoint: build the graph, run it, print the resulting state.

Runs fully offline with no API key configured. Exposed both as the
``agentic-scd`` console script (see ``[project.scripts]``) and via
``python -m agentic_scd``.
"""

from agentic_scd.graph import GraphState, build_graph


def run() -> GraphState:
    """Build and invoke the graph, returning the final state."""
    graph = build_graph()
    result: GraphState = graph.invoke({})
    return result


def main() -> None:
    """CLI entrypoint: run the graph and print a summary of the state."""
    state = run()
    signals = state.get("new_signals", [])
    print(f"Graph run complete. new_signals: {len(signals)}")
    for signal in signals:
        print(f"  - [{signal.source_type}] {signal.title} ({signal.signal_id})")


if __name__ == "__main__":
    main()
