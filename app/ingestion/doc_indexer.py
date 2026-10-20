"""Brand documents (PDF / Markdown) → PageIndex tree, stored as one JSON file per document.

PDF trees are built by an LLM (costs tokens). Markdown trees come from the headings (free, offline).
"""
import asyncio
import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PyPDF2 import PdfReader

from app.core.config import get_settings
from app.core.llm import litellm_name

log = logging.getLogger(__name__)
SUPPORTED = {".pdf", ".md"}


def _meta_path(doc_id: str) -> Path:
    return get_settings().docs_dir / f"{doc_id}.json"


def _write(meta: dict) -> None:
    path = _meta_path(meta["doc_id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # atomic, so readers never see half a file


def validate(path: Path) -> None:
    """Raise ValueError for unsupported or unreadable files. Local PageIndex has no OCR."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type {ext}; use PDF or Markdown")
    if ext == ".pdf":
        try:
            pages = PdfReader(str(path)).pages
            has_text = any((p.extract_text() or "").strip() for p in pages[:5])
        except Exception as e:
            raise ValueError(f"Not a readable PDF: {e}") from e
        if not has_text:
            raise ValueError("PDF has no extractable text (scanned?). Only text-based PDFs are supported")


def register(src: Path, name: str) -> str:
    """Move a validated upload into the store and mark it as indexing. Returns doc_id."""
    doc_id = uuid.uuid4().hex[:12]
    dest = get_settings().docs_dir / f"{doc_id}{src.suffix.lower()}"
    shutil.move(src, dest)
    _write({"doc_id": doc_id, "name": name, "file": dest.name, "status": "indexing",
            "created_at": datetime.now(timezone.utc).isoformat()})
    return doc_id


def build_tree(doc_id: str) -> None:
    """Build the PageIndex tree. Runs as a background task; failures are recorded, not raised."""
    meta = get_document(doc_id)
    path = get_settings().docs_dir / meta["file"]
    try:
        if path.suffix == ".md":
            from pageindex.page_index_md import md_to_tree
            result = asyncio.run(md_to_tree(str(path), if_add_node_text="yes", if_add_node_id="yes"))
        else:
            from pageindex import page_index
            result = page_index(str(path), model=litellm_name("fast"),
                                if_add_node_id="yes", if_add_node_summary="yes", if_add_node_text="yes")
        meta.update(status="ready", tree=result["structure"])
    except Exception as e:
        log.exception("Indexing failed for %s", doc_id)
        meta.update(status="failed", error=str(e))
    _write(meta)


def get_document(doc_id: str) -> dict:
    path = _meta_path(doc_id)
    if not path.exists():
        raise KeyError(doc_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_documents(with_tree: bool = False) -> list[dict]:
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in get_settings().docs_dir.glob("*.json")]
    if not with_tree:
        for d in docs:
            d.pop("tree", None)
    return sorted(docs, key=lambda d: d["created_at"])


def delete_document(doc_id: str) -> None:
    meta = get_document(doc_id)
    (get_settings().docs_dir / meta["file"]).unlink(missing_ok=True)
    _meta_path(doc_id).unlink()
