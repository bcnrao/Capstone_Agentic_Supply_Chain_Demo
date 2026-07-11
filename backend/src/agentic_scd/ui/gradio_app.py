from __future__ import annotations

import json
import os
from pathlib import Path

import gradio as gr
import pandas as pd

from agentic_scd.__main__ import run
from agentic_scd.config import get_settings
from agentic_scd.config.localfirst import CONFIG_FIELDS, apply_runtime_env, local_env_path
from agentic_scd.db import connect, init_db, ping
from agentic_scd.ingestion.collect import collect
from agentic_scd.ingestion.paths import SEED_DIR, lexicon_yaml_path, run_dir, snapshot_dir, sources_yaml_path
from agentic_scd.ingestion.relevance import load_lexicon
from agentic_scd.ingestion.store import recent_runs, recent_signals, serialize_state
from agentic_scd.llm.client import completion
from agentic_scd.rag.retriever import history_retriever, impact_retriever, mitigation_retriever, retrieval_mode, retriever_stats
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
    retriever = retriever_stats()
    llm_mode = llm_mode_label(settings)
    return (
        f"### System status\n"
        f"**Storage mode:** {database_mode(settings.resolved_database_url)} ({status.detail})  \n"
        f"**LLM mode:** {llm_mode}  \n"
        f"**Retrieval mode:** {retrieval_mode()} ({retriever['impact_documents']} impact docs / {retriever['mitigation_documents']} playbook docs)  \n"
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


def analysis_table(state: dict) -> pd.DataFrame:
    rows = []
    for item in state.get("event_analyses", []) or []:
        rows.append(
            {
                "event_type": item.event_type,
                "region": item.extracted_region or "",
                "severity_hint": item.severity_hint or "",
                "entities": ", ".join(item.entities),
                "summary": item.summary,
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


def weather_table(state: dict) -> pd.DataFrame:
    rows = []
    for risk in state.get("weather_risks", []) or []:
        rows.append(
            {
                "hub": risk.hub_port or "",
                "region": risk.region or "",
                "horizon_days": risk.horizon_days,
                "aggregate_severity": risk.aggregate_severity,
                "port_disruption_risk": risk.port_disruption_risk,
                "peak_day": risk.peak_day or "",
                "operations": ", ".join(risk.affected_operations),
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
        f"Engine: **{sim.engine or 'local'}**  \n"
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
        analysis_table(state),
        weather_table(state),
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
    docs = impact_retriever().search(question, top_k=3) + mitigation_retriever().search(question, top_k=3)
    if not docs:
        return "No local network or playbook context matched that question."
    settings = get_settings()
    lines = ["Relevant local context:"]
    seen: set[str] = set()
    context_rows: list[str] = []
    for doc in docs:
        if doc.doc_id in seen:
            continue
        seen.add(doc.doc_id)
        label = doc.metadata.get("name") or doc.metadata.get("title") or doc.doc_id
        row = f"- {label}: {doc.text}"
        lines.append(row)
        context_rows.append(row)
        if len(seen) >= 5:
            break
    if not settings.llm_is_mock:
        system = "Answer using the provided local supply-chain context only. Keep the response concise and practical."
        prompt = f"Question: {question}\n\nContext:\n" + "\n".join(context_rows)
        try:
            answer = completion(prompt, system=system, settings=settings, temperature=0).strip()
            if answer:
                return f"### Answer\n{answer}\n\n" + "\n".join(lines)
        except Exception:
            pass
    return "\n".join(lines)


def llm_mode_label(settings) -> str:
    return "mock" if settings.llm_is_mock else f"groq:{settings.groq_model}"


def dashboard_css() -> str:
    return """
    #config-modal {
        position: fixed !important;
        inset: 0;
        z-index: 999;
        background: rgba(15, 23, 42, 0.48);
        overflow-y: auto;
        padding: 24px 0 32px;
    }

    #config-panel {
        max-width: 1180px;
        margin: 0 auto;
        background: white;
        border-radius: 18px;
        padding: 20px 22px 24px;
        box-shadow: 0 28px 80px rgba(15, 23, 42, 0.24);
    }
    """


def config_input_value(field_name: str):
    settings = get_settings()
    if field_name in {
        "AGENTIC_SCD_HOME",
        "DATABASE_URL",
        "AGENTIC_SCD_SOURCES_YAML",
        "AGENTIC_SCD_LEXICON_YAML",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "HF_TOKEN",
        "XAI_API_KEY",
    }:
        return os.getenv(field_name, "")
    if field_name == "GROQ_MODEL":
        return os.getenv(field_name, settings.groq_model)
    if field_name == "USE_MOCK_LLM":
        return settings.use_mock_llm
    if field_name == "INGEST_POLL_INTERVAL_MINUTES":
        return str(settings.ingest_poll_interval_minutes)
    if field_name == "INGEST_SCHEDULER_ENABLED":
        return settings.ingest_scheduler_enabled
    if field_name == "INGEST_HOST":
        return settings.ingest_host
    if field_name == "INGEST_PORT":
        return str(settings.ingest_port)
    if field_name == "WEBHOOK_SOURCE_RELIABILITY":
        return str(settings.webhook_source_reliability)
    if field_name == "BATCH_ENABLED":
        return settings.batch_enabled
    if field_name == "RETENTION_ENABLED":
        return settings.retention_enabled
    if field_name == "RETENTION_REJECTED_TTL_DAYS":
        return str(settings.retention_rejected_ttl_days)
    if field_name == "RETENTION_SIGNALS_TTL_DAYS":
        return str(settings.retention_signals_ttl_days)
    if field_name == "SIMULATION_ITERATIONS":
        return str(settings.simulation_iterations)
    if field_name == "GRADIO_SHARE":
        return settings.dashboard_share
    if field_name == "GRADIO_SERVER_NAME":
        return os.getenv(field_name, "127.0.0.1")
    return os.getenv(field_name, "")


def config_runtime_values() -> tuple[str, ...]:
    settings = get_settings()
    status = ping(settings)
    retrieval = retriever_stats()
    return (
        str(local_env_path()),
        f"{database_mode(settings.resolved_database_url)} ({status.detail})",
        settings.resolved_database_url or "",
        llm_mode_label(settings),
        f"{retrieval_mode()} ({retrieval['history_documents']} history / {retrieval['impact_documents']} impact / {retrieval['mitigation_documents']} mitigation)",
        str(settings.data_dir),
        str(snapshot_dir()),
        str(run_dir()),
        str(sources_yaml_path()),
        str(lexicon_yaml_path()),
        str(SEED_DIR),
        "7860",
        "8000",
    )


def config_status_text(message: str) -> str:
    lines = []
    if message:
        lines.append(f"**{message}**")
    lines.append(f"Config file: `{local_env_path()}`")
    lines.append("Next dashboard action picks up storage selection, data-home changes, YAML overrides, Groq settings, retention values, and simulation iterations.")
    lines.append("Restart the dashboard or ingestion service for `GRADIO_SERVER_NAME`, `GRADIO_SHARE`, `INGEST_HOST`, `INGEST_PORT`, `INGEST_POLL_INTERVAL_MINUTES`, and `INGEST_SCHEDULER_ENABLED`.")
    lines.append("`OPENAI_API_KEY`, `HF_TOKEN`, and `XAI_API_KEY` are stored by the panel but are not consumed by the current local-first runtime yet.")
    return "\n\n".join(lines)


def config_snapshot(visible: bool, message: str) -> tuple:
    values = [config_input_value(field.name) for field in CONFIG_FIELDS]
    readonly = list(config_runtime_values())
    return (
        gr.update(visible=visible),
        *values,
        *readonly,
        config_status_text(message),
    )


def open_config_panel() -> tuple:
    return config_snapshot(True, "Local-first runtime configuration")


def reload_config_panel() -> tuple:
    return config_snapshot(True, "Reloaded current local-first settings")


def close_config_panel():
    return gr.update(visible=False)


def apply_config_panel(*args) -> tuple:
    values = {}
    for field, raw_value in zip(CONFIG_FIELDS, args, strict=False):
        values[field.name] = "1" if field.kind == "bool" and raw_value else "0" if field.kind == "bool" else raw_value
    apply_runtime_env(values)
    get_settings.cache_clear()
    load_lexicon.cache_clear()
    impact_retriever.cache_clear()
    mitigation_retriever.cache_clear()
    history_retriever.cache_clear()
    return config_snapshot(True, "Saved local-first configuration")


def build_dashboard() -> gr.Blocks:
    scenarios = [""] + scenario_names()
    sections: dict[str, list] = {}
    for field in CONFIG_FIELDS:
        sections.setdefault(field.section, []).append(field)
    with gr.Blocks(title="Agentic Supply Chain Disruption Predictor") as app:
        gr.HTML(f"<style>{dashboard_css()}</style>")
        gr.Markdown("# Agentic Supply Chain Disruption Predictor & Simulation Engine")
        gr.Markdown("Run a live or packaged scenario, inspect the agent path, and test mitigation choices from one local dashboard.")
        with gr.Row():
            scenario = gr.Dropdown(choices=scenarios, value=scenarios[0], label="Scenario")
            use_pending_signals = gr.Checkbox(label="Use pending DB signals", value=False)
            run_btn = gr.Button("Run pipeline", variant="primary")
            collect_btn = gr.Button("Refresh external data")
            config_btn = gr.Button("Config")
        collect_status = gr.Markdown()
        config_inputs = []
        with gr.Column(visible=False, elem_id="config-modal") as config_modal:
            with gr.Column(elem_id="config-panel"):
                gr.Markdown("## Config")
                gr.Markdown("Manage the local-first Python runtime without changing the notebook or docker paths.")
                with gr.Tabs():
                    for section, fields in sections.items():
                        with gr.Tab(section):
                            for field in fields:
                                if field.kind == "bool":
                                    component = gr.Checkbox(label=field.label)
                                else:
                                    component = gr.Textbox(
                                        label=field.label,
                                        type="password" if field.secret else "text",
                                    )
                                config_inputs.append(component)
                with gr.Row():
                    save_config = gr.Button("Save config", variant="primary")
                    reload_config = gr.Button("Reload values")
                    close_config = gr.Button("Close")
                config_status = gr.Markdown()
                with gr.Row():
                    config_file_box = gr.Textbox(label="Config file", interactive=False)
                    storage_box = gr.Textbox(label="Resolved storage", interactive=False)
                    llm_box = gr.Textbox(label="Resolved LLM mode", interactive=False)
                with gr.Row():
                    database_box = gr.Textbox(label="Resolved DB URL", interactive=False)
                    retrieval_box = gr.Textbox(label="Retrieval mode", interactive=False)
                with gr.Row():
                    data_home_box = gr.Textbox(label="Resolved data home", interactive=False)
                    sources_box = gr.Textbox(label="Resolved sources YAML", interactive=False)
                    lexicon_box = gr.Textbox(label="Resolved lexicon YAML", interactive=False)
                with gr.Row():
                    snapshot_box = gr.Textbox(label="Snapshot directory", interactive=False)
                    run_box = gr.Textbox(label="Run directory", interactive=False)
                    seed_box = gr.Textbox(label="Seed directory", interactive=False)
                with gr.Row():
                    dashboard_port_box = gr.Textbox(
                        label="Dashboard port", interactive=False
                    )
                    api_port_box = gr.Textbox(label="API port", interactive=False)
        config_outputs = [
            config_modal,
            *config_inputs,
            config_file_box,
            storage_box,
            database_box,
            llm_box,
            retrieval_box,
            data_home_box,
            snapshot_box,
            run_box,
            sources_box,
            lexicon_box,
            seed_box,
            dashboard_port_box,
            api_port_box,
            config_status,
        ]
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
            with gr.Tab("News analysis"):
                analyses = gr.Dataframe(label="Event extraction and summarization", interactive=False)
            with gr.Tab("Weather risk"):
                weather = gr.Dataframe(label="7-day hub weather risk", interactive=False)
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
        config_btn.click(open_config_panel, outputs=config_outputs)
        save_config.click(
            apply_config_panel, inputs=config_inputs, outputs=config_outputs
        )
        reload_config.click(reload_config_panel, outputs=config_outputs)
        close_config.click(close_config_panel, outputs=[config_modal])
        run_btn.click(run_dashboard, inputs=[scenario, use_pending_signals], outputs=[kpis, system_card, analyses, weather, signals, impacts, forecast, simulation, recommendations, evidence, raw]).then(history_table, outputs=[history]).then(inbox_table, outputs=[inbox])
        collect_btn.click(collect_dashboard, outputs=[collect_status]).then(inbox_table, outputs=[inbox])
        refresh_history.click(history_table, outputs=[history])
        refresh_inbox.click(inbox_table, outputs=[inbox])
        answer_btn.click(ask_network, inputs=[question], outputs=[answer])
    return app


def main() -> None:
    settings = get_settings()
    server_name = os.getenv("GRADIO_SERVER_NAME") or "127.0.0.1"
    build_dashboard().launch(server_name=server_name, server_port=7860, share=settings.dashboard_share)


if __name__ == "__main__":
    main()
