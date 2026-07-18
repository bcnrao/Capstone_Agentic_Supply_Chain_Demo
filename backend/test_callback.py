from langchain_core.callbacks.stdout import StdOutCallbackHandler
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

handler = StdOutCallbackHandler()
config = {"callbacks": [handler]}
result = graph.invoke({"foo": "baz"}, config=config)
print("Result:", result)
