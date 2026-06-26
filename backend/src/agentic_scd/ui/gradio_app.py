"""Minimal Gradio dashboard for the walking skeleton.

A "Run pipeline" button runs the end-to-end graph and populates one panel per stage
(signals · classification · impact · forecast · simulation · recommendation), mirroring
the demo-walkthrough panel layout. Deliberately minimal — the run-status strip, heatmap,
and what-if controls arrive in later phases. Runs fully offline (synthetic seed).
"""

import gradio as gr

from agentic_scd.__main__ import run
from agentic_scd.graph.state import GraphState

PIPELINE_STAGES = (
    "ingest → input-guard → seed → classify → impact → forecast → simulate → recommend"
)


def signals_md(state: GraphState) -> str:
    signals = state.get("new_signals", [])
    if not signals:
        return "_No signals._"
    return "\n".join(f"- **[{s.source_type}]** {s.title}" for s in signals)


def classification_md(state: GraphState) -> str:
    rows = state.get("classifications", [])
    if not rows:
        return "_No classifications._"
    return "\n".join(
        f"- **{c.category}** — risk `{c.risk_score:.2f}` ({c.rationale})" for c in rows
    )


def impact_md(state: GraphState) -> str:
    rows = state.get("impacts", [])
    if not rows:
        return "_No impacts._"
    return "\n".join(f"- {', '.join(i.affected_entities)}" for i in rows)


def forecast_md(state: GraphState) -> str:
    forecast = state.get("forecast")
    if not forecast:
        return "_No forecast._"
    lines = ["| step | baseline | adjusted |", "|---|---|---|"]
    for step, (base, adj) in enumerate(
        zip(forecast.baseline, forecast.adjusted, strict=False), start=1
    ):
        lines.append(f"| {step} | {base:.0f} | {adj:.1f} |")
    return f"_{forecast.note}_\n\n" + "\n".join(lines)


def simulation_md(state: GraphState) -> str:
    sim = state.get("simulation")
    if not sim:
        return "_No simulation._"
    return (
        f"- **Stockout probability:** {sim.stockout_probability:.0%}\n"
        f"- **Revenue impact:** {sim.revenue_impact:,.0f}\n"
        f"- _{sim.assumptions}_"
    )


def recommendation_md(state: GraphState) -> str:
    rec = state.get("recommendation")
    if not rec:
        return "_No recommendation._"
    actions = "\n".join(f"- {a}" for a in rec.actions)
    return f"{actions}\n\n_{rec.summary}_"


def run_and_format() -> tuple[str, str, str, str, str, str, str]:
    """Run the pipeline once and render each stage as markdown."""
    state = run()
    status = f"**Run complete:** {PIPELINE_STAGES}"
    return (
        status,
        signals_md(state),
        classification_md(state),
        impact_md(state),
        forecast_md(state),
        simulation_md(state),
        recommendation_md(state),
    )


def build_dashboard() -> gr.Blocks:
    """Construct the Gradio app (does not launch a server)."""
    with gr.Blocks(title="Agentic SCD — walking skeleton") as app:
        gr.Markdown(
            "# Agentic Supply Chain Disruption — walking skeleton\n"
            "Run the end-to-end pipeline (Phase 1 ingestion + Phase 2 agent stubs)."
        )
        run_btn = gr.Button("Run pipeline", variant="primary")
        status = gr.Markdown()
        with gr.Tabs():
            with gr.Tab("Signals"):
                signals = gr.Markdown()
            with gr.Tab("Classification"):
                classification = gr.Markdown()
            with gr.Tab("Impact"):
                impact = gr.Markdown()
            with gr.Tab("Forecast"):
                forecast = gr.Markdown()
            with gr.Tab("Simulation"):
                simulation = gr.Markdown()
            with gr.Tab("Recommendation"):
                recommendation = gr.Markdown()

        run_btn.click(
            fn=run_and_format,
            outputs=[
                status,
                signals,
                classification,
                impact,
                forecast,
                simulation,
                recommendation,
            ],
        )
    return app


def main() -> None:
    """CLI entrypoint: launch the Gradio dashboard."""
    build_dashboard().launch(share=True)


if __name__ == "__main__":
    main()
