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

    # Unified routing: every signal (HIGH/MEDIUM/LOW) runs the full pipeline —
    # impact + forecast + simulation + recommendation — no agent is skipped.
    route = state.get("route", "")
    assert state.get("impacts") and all(isinstance(i, ImpactMap) for i in state["impacts"]), \
        f"pipeline must produce impacts. route='{route}'"
    assert isinstance(state.get("forecast"), Forecast), \
        f"pipeline must produce forecast. route='{route}'"
    assert isinstance(state.get("simulation"), Simulation), \
        f"pipeline must produce simulation. route='{route}'"

    # Recommendation always runs regardless of route
    assert isinstance(state["recommendation"], Recommendation)
    assert state["recommendation"].actions  # the chain produced an action


def test_run_is_content_deterministic() -> None:
    # signal_id is a fresh uuid each run, but the derived content is deterministic.
    a, b = run(), run()
    ca, cb = a["classifications"][0], b["classifications"][0]
    assert (ca.category, ca.risk_score) == (cb.category, cb.risk_score)

    # forecast and simulation now run for every signal and are deterministic.
    assert a["forecast"].adjusted == b["forecast"].adjusted
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
