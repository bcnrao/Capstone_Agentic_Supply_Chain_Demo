"""Build and compile the LangGraph pipeline.

Phase 1 wires the read side of ingestion: ``ingestion_node`` drains new signals from
Postgres and the ``input_guardrail`` node validates them (relevance · schema · safety
-> discard) before anything downstream. Later phases register the classification,
impact-mapping, forecasting, simulation and mitigation nodes after the guardrail on
this same graph.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from agentic_scd.graph.state import GraphState
from agentic_scd.ingestion.agent import ingestion_node
from agentic_scd.ingestion.guardrails import input_guardrail_node

INGESTION_NODE = "ingestion"
GUARDRAIL_NODE = "input_guardrail"


def build_graph() -> Any:
    """Construct and compile the disruption-pipeline graph."""
    builder = StateGraph(GraphState)
    builder.add_node(INGESTION_NODE, ingestion_node)
    builder.add_node(GUARDRAIL_NODE, input_guardrail_node)
    builder.add_edge(START, INGESTION_NODE)
    builder.add_edge(INGESTION_NODE, GUARDRAIL_NODE)
    builder.add_edge(GUARDRAIL_NODE, END)
    return builder.compile()
