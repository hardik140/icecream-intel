"""One function per graph node. Each takes GraphState, returns a partial state update. (M4)"""
from app.graph.state import GraphState


def input_guard(state: GraphState) -> dict:
    raise NotImplementedError("M5")


def route(state: GraphState) -> dict:
    raise NotImplementedError("M4")


def retrieve_docs(state: GraphState) -> dict:
    raise NotImplementedError("M4")


def query_data(state: GraphState) -> dict:
    raise NotImplementedError("M4")


def synthesize(state: GraphState) -> dict:
    raise NotImplementedError("M4")


def output_guard(state: GraphState) -> dict:
    raise NotImplementedError("M5")
