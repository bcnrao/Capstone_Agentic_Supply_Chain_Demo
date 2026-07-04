from __future__ import annotations

import json
from pathlib import Path

import gradio as gr
import pandas as pd

from agentic_scd.__main__ import run
from agentic_scd.config import get_settings
from agentic_scd.db import connect, init_db, ping
from agentic_scd.ingestion.collect import collect
from agentic_scd.ingestion.paths import SEED_DIR
from agentic_scd.ingestion.store import recent_runs, recent_signals, serialize_state
from agentic_scd.runtime_warnings import suppress_known_dependency_warnings

suppress_known_dependency_warnings()


def scenario_names() -> list[str]:
    path = SEED_DIR / "scenarios.json"
    if not path.exists():
        return []
    return [row["name"] for row in json.loads(path.read_text(encoding="utf-8"))]


def database_mode(url: str | None) -> str:
    lowered = (url or "").lower()
    if lowered.startswith("postgresql:") or lowered.startswith("postgres:"):
        return "postgres"
    if lowered.startswith("sqlite:"):
        return "sqlite"
    return "none"


def kpi_markdown(state: dict) -> str:
    classifications = state.get("classifications", []) or []
    simulation = state.get("simulation")
    forecast = state.get("forecast")
    max_severity = max((item.severity for item in classifications), default=0.0)
    active = len(classifications)
    stockout = simulation.stockout_probability if simulation else 0.0
    revenue = simulation.revenue_impact if simulation else 0.0
    deviation = forecast.demand_deviation_pct if forecast else 0.0
    return (
        f"### Executive overview\n"
        f"**Overall risk index:** {max_severity:.1f}/10  \n"
        f"**Active disruption signals:** {active}  \n"
        f"**Stockout probability:** {stockout:.0%}  \n"
        f"**Expected revenue impact:** {revenue:,.0f}  \n"
        f"**Demand deviation:** {deviation:.1f}%  \n"
        f"**Route:** {state.get('route', 'not set')}"
    )


def system_markdown(state: dict) -> str:
    settings = get_settings()
    status = ping(settings)
    data_dir = Path(settings.data_dir)
    forecast = state.get("forecast")
    llm_mode = "mock" if settings.llm_is_mock else settings.groq_model
    return (
        f"### System status\n"
        f"**Storage mode:** {database_mode(settings.resolved_database_url)} ({status.detail})  \n"
        f"**LLM mode:** {llm_mode}  \n"
        f"**Data home:** {data_dir}  \n"
        f"**Signals used this run:** {len(state.get('new_signals', []) or [])}  \n"
        f"**Forecast baseline:** {forecast.note if forecast else 'No forecast baseline generated.'}"
    )


def signals_table(state: dict) -> pd.DataFrame:
    rows = []
    classifications = {item.signal_id: item for item in state.get("classifications", []) or []}
    for signal in state.get("new_signals", []) or []:
        cls = classifications.get(signal.signal_id)
        rows.append(
            {
                "title": signal.title,
                "source": signal.source,
                "region": signal.region or "",
                "category": cls.category if cls else "",
                "severity": cls.severity if cls else 0,
                "risk_level": cls.risk_level if cls else "",
                "confidence": cls.confidence if cls else 0,
                "route": cls.route if cls else "",
            }
        )
    return pd.DataFrame(rows)


def impact_table(state: dict) -> pd.DataFrame:
    rows = []
    for impact in state.get("impacts", []) or []:
        rows.append(
            {
                "suppliers": ", ".join(impact.affected_suppliers),
                "lanes": ", ".join(impact.affected_lanes),
                "facilities": ", ".join(impact.affected_facilities),
                "products": ", ".join(impact.product_categories),
                "reasoning": impact.reasoning,
            }
        )
    return pd.DataFrame(rows)


def forecast_table(state: dict) -> pd.DataFrame:
    forecast = state.get("forecast")
    if not forecast:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "date": forecast.dates,
            "baseline": forecast.baseline,
            "risk_adjusted": forecast.adjusted,
            "delta": [round(adjusted - baseline, 2) for baseline, adjusted in zip(forecast.baseline, forecast.adjusted, strict=False)],
        }
    )


def recommendation_table(state: dict) -> pd.DataFrame:
    rec = state.get("recommendation")
    if not rec:
        return pd.DataFrame()
    return pd.DataFrame([item.model_dump() for item in rec.structured_actions])


def evidence_table(state: dict) -> pd.DataFrame:
    rec = state.get("recommendation")
    if not rec:
        return pd.DataFrame()
    return pd.DataFrame({"evidence": rec.evidence})


def simulation_markdown(state: dict) -> str:
    sim = state.get("simulation")
    if not sim:
        return "No simulation has run yet for this route."
    return (
        f"### Simulation lab\n"
        f"Stockout probability: **{sim.stockout_probability:.0%}**  \n"
        f"Service level: **{sim.service_level:.0%}**  \n"
        f"Expected shortage: **{sim.expected_shortage_units:,.0f} units**  \n"
        f"Recovery time: **{sim.recovery_time_days:.1f} days**  \n"
        f"Revenue impact mean / p50 / p90: **{sim.revenue_impact:,.0f} / {sim.revenue_loss_p50:,.0f} / {sim.revenue_loss_p90:,.0f}**  \n"
        f"{sim.assumptions}"
    )


def run_dashboard(scenario: str | None, use_pending_signals: bool) -> tuple:
    scenario_value = scenario or None
    state = run(scenario_value, use_pending_signals=use_pending_signals)
    return (
        kpi_markdown(state),
        system_markdown(state),
        signals_table(state),
        impact_table(state),
        forecast_table(state),
        simulation_markdown(state),
        recommendation_table(state),
        evidence_table(state),
        json.dumps(serialize_state(state), indent=2, default=str),
    )


def collect_dashboard() -> str:
    summary = collect()
    total = summary.totals
    settings = get_settings()
    return f"Collected {total.fetched} raw items, kept {total.kept}, dropped {total.dropped}, persisted {total.persisted}. Storage mode: {database_mode(settings.resolved_database_url)}."


def history_table() -> pd.DataFrame:
    init_db()
    try:
        with connect() as conn:
            rows = recent_runs(conn, 20)
    except Exception:
        rows = []
    return pd.DataFrame([{key: row[key] for key in ("run_id", "created_at", "scenario_name", "route", "max_severity")} for row in rows])


def inbox_table() -> pd.DataFrame:
    init_db()
    try:
        with connect() as conn:
            signals = recent_signals(conn, 50)
    except Exception:
        signals = []
    return pd.DataFrame(
        [
            {
                "title": item.title,
                "source": item.source,
                "type": item.source_type,
                "region": item.region or "",
                "severity_hint": item.severity_hint or "",
                "status": "stored",
            }
            for item in signals
        ]
    )


def ask_network(question: str) -> str:
    from agentic_scd.rag.retriever import impact_retriever, mitigation_retriever

    docs = impact_retriever().search(question, top_k=3) + mitigation_retriever().search(question, top_k=3)
    if not docs:
        return "No local network or playbook context matched that question."
    lines = ["Relevant local context:"]
    seen: set[str] = set()
    for doc in docs:
        if doc.doc_id in seen:
            continue
        seen.add(doc.doc_id)
        label = doc.metadata.get("name") or doc.metadata.get("title") or doc.doc_id
        lines.append(f"- {label}: {doc.text}")
        if len(seen) >= 5:
            break
    return "\n".join(lines)


def build_dashboard() -> gr.Blocks:
    scenarios = [""] + scenario_names()
    with gr.Blocks(title="Agentic Supply Chain Disruption Predictor") as app:
        gr.Markdown("# Agentic Supply Chain Disruption Predictor & Simulation Engine")
        gr.Markdown("Run a live or packaged scenario, inspect the agent path, and test mitigation choices from one local dashboard.")
        with gr.Row():
            scenario = gr.Dropdown(choices=scenarios, value=scenarios[0], label="Scenario")
            use_pending_signals = gr.Checkbox(label="Use pending DB signals", value=False)
            run_btn = gr.Button("Run pipeline", variant="primary")
            collect_btn = gr.Button("Refresh external data")
        collect_status = gr.Markdown()
        with gr.Tabs():
            with gr.Tab("Executive"):
                kpis = gr.Markdown()
                system_card = gr.Markdown()
                history = gr.Dataframe(label="Recent runs", interactive=False)
                refresh_history = gr.Button("Refresh run history")
            with gr.Tab("Risk monitor"):
                signals = gr.Dataframe(label="Signals and classification", interactive=False)
                inbox = gr.Dataframe(label="Stored signal inbox", interactive=False)
                refresh_inbox = gr.Button("Refresh inbox")
            with gr.Tab("Impact map"):
                impacts = gr.Dataframe(label="Affected suppliers, lanes, and facilities", interactive=False)
            with gr.Tab("Demand forecast"):
                forecast = gr.Dataframe(label="Baseline vs risk-adjusted forecast", interactive=False)
            with gr.Tab("Simulation"):
                simulation = gr.Markdown()
            with gr.Tab("Mitigation"):
                recommendations = gr.Dataframe(label="Ranked action plan", interactive=False)
                evidence = gr.Dataframe(label="Supporting evidence", interactive=False)
            with gr.Tab("Trace JSON"):
                raw = gr.Code(language="json")
            with gr.Tab("Ask the local KB"):
                question = gr.Textbox(label="Question", value="Which suppliers and lanes are exposed to Shanghai weather disruption?")
                answer_btn = gr.Button("Ask")
                answer = gr.Markdown()
        run_btn.click(run_dashboard, inputs=[scenario, use_pending_signals], outputs=[kpis, system_card, signals, impacts, forecast, simulation, recommendations, evidence, raw]).then(history_table, outputs=[history]).then(inbox_table, outputs=[inbox])
        collect_btn.click(collect_dashboard, outputs=[collect_status]).then(inbox_table, outputs=[inbox])
        refresh_history.click(history_table, outputs=[history])
        refresh_inbox.click(inbox_table, outputs=[inbox])
        answer_btn.click(ask_network, inputs=[question], outputs=[answer])
    return app


def main() -> None:
    settings = get_settings()
    server_name = None
    import os

    server_name = os.getenv("GRADIO_SERVER_NAME") or "127.0.0.1"
    build_dashboard().launch(server_name=server_name, server_port=7860, share=settings.dashboard_share)


if __name__ == "__main__":
    main()
