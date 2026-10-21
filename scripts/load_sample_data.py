"""Load data/sample into the store: sales.csv → DuckDB, *.md / *.pdf → PageIndex trees.

Markdown indexing is offline and free; PDFs need GOOGLE_API_KEY.
Usage: python -m scripts.load_sample_data
"""
import shutil
import tempfile
from pathlib import Path

from app.ingestion import doc_indexer
from app.ingestion.table_loader import load_table

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


def main() -> None:
    print(load_table(SAMPLE / "sales.csv", "sales"))
    existing = {d["name"] for d in doc_indexer.list_documents()}
    for src in sorted(SAMPLE.iterdir()):
        if src.suffix.lower() not in doc_indexer.SUPPORTED or src.name in existing:
            continue
        doc_indexer.validate(src)
        tmp = Path(tempfile.mkdtemp()) / src.name
        shutil.copy(src, tmp)
        doc_id = doc_indexer.register(tmp, src.name)
        doc_indexer.build_tree(doc_id)
        print(src.name, doc_indexer.get_document(doc_id)["status"])


if __name__ == "__main__":
    main()
