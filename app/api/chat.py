from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from langchain_core.tracers.context import collect_runs
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.graph.builder import ask
from app.graph.state import Citation

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=get_settings().max_question_chars)


class ChatResponse(BaseModel):
    answer: str
    route: str | None = None
    blocked: str | None = None
    grounded: bool | None = None
    citations: list[Citation] = []
    sql: str | None = None
    run_id: str | None = None  # LangSmith run id, to find the trace


def _run(question: str) -> ChatResponse:
    with collect_runs() as cb:
        state = ask(question)
    return ChatResponse(
        answer=state["answer"],
        route=state.get("route"),
        blocked=state.get("blocked_reason"),
        grounded=state.get("grounded"),
        citations=state.get("doc_context") or [],
        sql=state.get("sql_query"),
        run_id=str(cb.traced_runs[0].id) if cb.traced_runs else None,
    )


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    return await run_in_threadpool(_run, req.question)
