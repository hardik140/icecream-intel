from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from app.api.uploads import save_upload
from app.ingestion import doc_indexer

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=202)
async def upload_document(file: UploadFile, background: BackgroundTasks) -> dict:
    """Upload a text PDF or Markdown file; the PageIndex tree is built in the background."""
    tmp = await save_upload(file, doc_indexer.SUPPORTED)
    try:
        doc_indexer.validate(tmp)
    except ValueError as e:
        tmp.unlink(missing_ok=True)
        raise HTTPException(422, str(e)) from e
    doc_id = doc_indexer.register(tmp, Path(file.filename).name)
    background.add_task(doc_indexer.build_tree, doc_id)
    return {"doc_id": doc_id, "status": "indexing"}


@router.get("")
def list_documents() -> list[dict]:
    return doc_indexer.list_documents()


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str) -> None:
    try:
        doc_indexer.delete_document(doc_id)
    except KeyError:
        raise HTTPException(404, "Document not found") from None
