"""Walking skeleton — graph runs end-to-end offline; dashboard builds."""

from agentic_scd.__main__ import run
from agentic_scd.agents.schema import (
    Classification,
    Forecast,
    ImpactMap,
    Recommendation,
    Simulation,
)
from agentic_scd.ingestion.schema import DisruptionSignal


def test_graph_runs_end_to_end_offline() -> None:
    # No DB / no network: the synthetic seed guarantees a full result.
    state = run()
    signals = state["new_signals"]
    assert len(signals) >= 1
    assert all(isinstance(s, DisruptionSignal) for s in signals)

    assert state["classifications"] and all(
        isinstance(c, Classification) for c in state["classifications"]
    )

    # Per spec routing:
    #   HIGH (>7)   -> skips impact + forecast, goes straight to simulation
    #   MEDIUM (4-7)-> runs full pipeline including impact + forecast
    #   LOW (<=3)   -> monitor-only, skips impact + simulation
    # The seed fallback rotates through scenarios; we assert based on route.
    route = state.get("route", "")
    is_high   = "HIGH" in route or "high_path" in route
    is_medium = "MEDIUM" in route or "full_path" in route
    is_low    = "LOW" in route or "monitor" in route

    if is_medium:
        # Full pipeline: impact + forecast + simulation must all be present
        assert state.get("impacts") and all(isinstance(i, ImpactMap) for i in state["impacts"]), \
            f"MEDIUM route must produce impacts. route='{route}'"
        assert isinstance(state.get("forecast"), Forecast), \
            f"MEDIUM route must produce forecast. route='{route}'"
        assert isinstance(state.get("simulation"), Simulation), \
            f"MEDIUM route must produce simulation. route='{route}'"
    elif is_high:
        # HIGH path: simulation runs, impact + forecast are intentionally skipped
        assert isinstance(state.get("simulation"), Simulation), \
            f"HIGH route must produce simulation. route='{route}'"
        # impacts and forecast are None by design on pure HIGH path
    elif is_low:
        # Monitor-only: nothing beyond classify + recommend runs
        pass

    # Recommendation always runs regardless of route
    assert isinstance(state["recommendation"], Recommendation)
    assert state["recommendation"].actions  # the chain produced an action


def test_run_is_content_deterministic() -> None:
    # signal_id is a fresh uuid each run, but the derived content is deterministic.
    a, b = run(), run()
    ca, cb = a["classifications"][0], b["classifications"][0]
    assert (ca.category, ca.risk_score) == (cb.category, cb.risk_score)

    # forecast and simulation are present on MEDIUM path, None on HIGH path —
    # check conditionally to avoid AttributeError on None
    if a.get("forecast") and b.get("forecast"):
        assert a["forecast"].adjusted == b["forecast"].adjusted
    if a.get("simulation") and b.get("simulation"):
        assert (
            a["simulation"].stockout_probability,
            a["simulation"].revenue_impact,
        ) == (b["simulation"].stockout_probability, b["simulation"].revenue_impact)

    assert a["recommendation"].actions == b["recommendation"].actions


def test_dashboard_builds_without_launch() -> None:
    import gradio as gr

    from agentic_scd.ui.gradio_app import build_dashboard

    app = build_dashboard()
    assert isinstance(app, gr.Blocks)
