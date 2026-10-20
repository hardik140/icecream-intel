from fastapi import APIRouter, HTTPException, UploadFile

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202)
async def upload_document(file: UploadFile) -> dict:
    """Validate PDF, save, index with PageIndex in background (M2)."""
    raise HTTPException(501, "Not implemented yet (M2)")


@router.get("")
def list_documents() -> list[dict]:
    raise HTTPException(501, "Not implemented yet (M2)")


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str) -> None:
    raise HTTPException(501, "Not implemented yet (M2)")
