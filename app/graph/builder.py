"""Wires nodes into the LangGraph flow from TRD §1."""
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import GraphState


def _after_input(state: GraphState) -> str:
    return END if state.get("blocked_reason") else "route"


def _after_route(state: GraphState) -> list[str] | str:
    return {
        "docs": ["retrieve_docs"],
        "data": ["query_data"],
        "both": ["retrieve_docs", "query_data"],  # run in parallel, synthesize waits for both
    }.get(state["route"], END)


def _after_output(state: GraphState) -> str:
    return "synthesize" if state.get("guard_feedback") and not state.get("grounded") else END


@lru_cache
def build_graph():
    g = StateGraph(GraphState)
    for name in ("input_guard", "route", "retrieve_docs", "query_data", "synthesize", "output_guard"):
        g.add_node(name, getattr(nodes, name))
    g.add_edge(START, "input_guard")
    g.add_conditional_edges("input_guard", _after_input, ["route", END])
    g.add_conditional_edges("route", _after_route, ["retrieve_docs", "query_data", END])
    g.add_edge("retrieve_docs", "synthesize")
    g.add_edge("query_data", "synthesize")
    g.add_edge("synthesize", "output_guard")
    g.add_conditional_edges("output_guard", _after_output, ["synthesize", END])
    return g.compile()


def ask(question: str) -> GraphState:
    return build_graph().invoke({"question": question})
