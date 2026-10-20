from typing import Literal, TypedDict

from pydantic import BaseModel

Route = Literal["docs", "data", "both", "out_of_scope"]


class Citation(BaseModel):
    doc_id: str
    doc_name: str
    section: str
    location: str  # "p.3-5" for PDFs, "line 12" for Markdown
    text: str = ""


class GraphState(TypedDict, total=False):
    question: str
    clean_question: str
    route: Route
    doc_context: list[Citation]
    sql_query: str | None
    sql_result: list[dict] | None
    sql_error: str | None
    answer: str
    grounded: bool
    guard_feedback: str | None
    retries: int
    blocked_reason: str | None
