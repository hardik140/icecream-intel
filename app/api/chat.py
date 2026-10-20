from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.graph.state import Citation

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    route: str
    citations: list[Citation] = []
    sql: str | None = None
    trace_url: str | None = None


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Run the LangGraph pipeline (M4)."""
    raise HTTPException(501, "Not implemented yet (M4)")
