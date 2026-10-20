from fastapi import APIRouter

from app.core.config import get_settings
from app.ingestion.doc_indexer import list_documents
from app.ingestion.table_loader import get_schema

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "llm": bool(s.anthropic_api_key),
        "langsmith": bool(s.langsmith_api_key),
        "documents_ready": sum(d["status"] == "ready" for d in list_documents()),
        "tables": len(get_schema()),
    }
