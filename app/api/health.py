from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "llm": bool(s.anthropic_api_key),
        "langsmith": bool(s.langsmith_api_key),
    }
