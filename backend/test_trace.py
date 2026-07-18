import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_PROJECT"] = "Test Project"

from langgraph.graph import StateGraph, END, START
from typing import TypedDict

class State(TypedDict):
    foo: str

def node1(state):
    return {"foo": "bar"}

builder = StateGraph(State)
builder.add_node("node1", node1)
builder.add_edge(START, "node1")
builder.add_edge("node1", END)

graph = builder.compile()
result = graph.invoke({"foo": "baz"})
print(result)
