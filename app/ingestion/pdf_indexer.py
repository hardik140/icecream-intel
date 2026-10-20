"""PDF → PageIndex tree. Text-based PDFs only (local PageIndex has no OCR)."""
from pathlib import Path


def index_pdf(path: Path) -> str:
    """Build the PageIndex tree for a PDF, store it, return doc_id. (M2)"""
    raise NotImplementedError("M2")
