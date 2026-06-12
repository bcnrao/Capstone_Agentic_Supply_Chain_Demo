"""Build and compile the LangGraph pipeline.

Phase 0 wires a single node (the ingestion stub). Later phases register the
classification, impact-mapping, forecasting, simulation and mitigation nodes and
the edges between them on this same graph.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from agentic_scd.graph.state import GraphState
from agentic_scd.ingestion.agent import ingestion_node

INGESTION_NODE = "ingestion"


def build_graph() -> Any:
    """Construct and compile the disruption-pipeline graph."""
    builder = StateGraph(GraphState)
    builder.add_node(INGESTION_NODE, ingestion_node)
    builder.add_edge(START, INGESTION_NODE)
    builder.add_edge(INGESTION_NODE, END)
    return builder.compile()
