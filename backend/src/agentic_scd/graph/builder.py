"""Build and compile the LangGraph pipeline.

Phase 1 wired the ingestion read side (`ingestion_node` + `input_guardrail`). Phase 2
adds the walking skeleton: an always-demoable synthetic `seed`, then the five downstream
agent stubs (classify → impact → forecast → simulate → recommend), so the whole chain
runs end-to-end on this same graph. Phases 3-7 deepen each stub behind its signature.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from agentic_scd.agents.classify import classify_node
from agentic_scd.agents.forecast import forecast_node
from agentic_scd.agents.impact import impact_node
from agentic_scd.agents.recommend import recommend_node
from agentic_scd.agents.simulate import simulate_node
from agentic_scd.graph.seed import seed_node
from agentic_scd.graph.state import GraphState
from agentic_scd.ingestion.agent import ingestion_node
from agentic_scd.ingestion.guardrails import input_guardrail_node

INGESTION_NODE = "ingestion"
GUARDRAIL_NODE = "input_guardrail"
SEED_NODE = "seed"
CLASSIFY_NODE = "classify"
IMPACT_NODE = "impact"
FORECAST_NODE = "forecast"
SIMULATE_NODE = "simulate"
RECOMMEND_NODE = "recommend"

# The pipeline order (a linear walking skeleton); edges are wired in this sequence.
PIPELINE = [
    INGESTION_NODE,
    GUARDRAIL_NODE,
    SEED_NODE,
    CLASSIFY_NODE,
    IMPACT_NODE,
    FORECAST_NODE,
    SIMULATE_NODE,
    RECOMMEND_NODE,
]

_NODE_FNS = {
    INGESTION_NODE: ingestion_node,
    GUARDRAIL_NODE: input_guardrail_node,
    SEED_NODE: seed_node,
    CLASSIFY_NODE: classify_node,
    IMPACT_NODE: impact_node,
    FORECAST_NODE: forecast_node,
    SIMULATE_NODE: simulate_node,
    RECOMMEND_NODE: recommend_node,
}


def build_graph() -> Any:
    """Construct and compile the disruption-pipeline graph."""
    builder = StateGraph(GraphState)
    for name in PIPELINE:
        builder.add_node(name, _NODE_FNS[name])

    builder.add_edge(START, PIPELINE[0])
    for upstream, downstream in zip(PIPELINE, PIPELINE[1:], strict=False):
        builder.add_edge(upstream, downstream)
    builder.add_edge(PIPELINE[-1], END)
    return builder.compile()
