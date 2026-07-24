from __future__ import annotations

from typing import Any

from agentic_scd.agents.classify import classify_node
from agentic_scd.agents.forecast import forecast_node
from agentic_scd.agents.impact import impact_node
from agentic_scd.agents.news import news_node
from agentic_scd.agents.recommend import recommend_node
from agentic_scd.agents.simulate import simulate_node
from agentic_scd.agents.weather import weather_node
from agentic_scd.graph.seed import seed_node
from agentic_scd.graph.state import GraphState
from agentic_scd.ingestion.agent import ingestion_node
from agentic_scd.ingestion.guardrails import input_guardrail_node

PIPELINE = [
    "ingestion",
    "input_guardrail",
    "seed",
    "news",
    "weather",
    "classify",
    "impact",
    "forecast",
    "simulate",
    "recommend",
]

NODE_FNS = {
    "ingestion": ingestion_node,
    "input_guardrail": input_guardrail_node,
    "seed": seed_node,
    "news": news_node,
    "weather": weather_node,
    "classify": classify_node,
    "impact": impact_node,
    "forecast": forecast_node,
    "simulate": simulate_node,
    "recommend": recommend_node,
}


class SimpleGraph:
    def invoke(self, state: dict | None = None, config: object | None = None, **_: object) -> GraphState:
        from agentic_scd.agents.output_guardrail import output_guardrail_node
        from agentic_scd.graph.routing import PRE_CLASSIFY_STEPS, route_steps

        current: dict = dict(state or {})
        node_fns = {**NODE_FNS, "output_guardrail": output_guardrail_node}
        for name in PRE_CLASSIFY_STEPS:
            update = node_fns[name](current)
            current.update(update or {})
        for name in route_steps(current):
            update = node_fns[name](current)
            current.update(update or {})
        return current


def build_graph() -> Any:
    try:
        from langgraph.graph import END, START, StateGraph

        from agentic_scd.agents.output_guardrail import output_guardrail_node
        from agentic_scd.graph.routing import PRE_CLASSIFY_STEPS, route_entry_node, route_exit_edges

        node_fns = {**NODE_FNS, "output_guardrail": output_guardrail_node}
        builder = StateGraph(GraphState)
        for name, node in node_fns.items():
            builder.add_node(name, node)
        builder.add_edge(START, PRE_CLASSIFY_STEPS[0])
        for upstream, downstream in zip(PRE_CLASSIFY_STEPS, PRE_CLASSIFY_STEPS[1:], strict=False):
            builder.add_edge(upstream, downstream)
        builder.add_conditional_edges("classify", route_entry_node, route_exit_edges())
        builder.add_edge("impact", "forecast")
        builder.add_edge("forecast", "simulate")
        builder.add_edge("simulate", "recommend")
        builder.add_edge("recommend", "output_guardrail")
        builder.add_edge("output_guardrail", END)
        return builder.compile()
    except Exception:
        return SimpleGraph()
