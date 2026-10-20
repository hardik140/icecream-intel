from typing import Literal, TypedDict

from pydantic import BaseModel

Route = Literal["docs", "data", "both", "out_of_scope"]


class Citation(BaseModel):
    doc_id: str
    doc_name: str
    page: int
    text: str = ""


class GraphState(TypedDict, total=False):
    question: str
    clean_question: str
    route: Route
    doc_context: list[Citation]
    sql_query: str | None
    sql_result: list[dict] | None
    answer: str
    citations: list[Citation]
    grounded: bool
    retries: int
    blocked_reason: str | None
