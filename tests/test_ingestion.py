import duckdb
import pytest

from app.ingestion import doc_indexer
from app.ingestion.table_loader import get_schema, load_table, readonly_connection
from app.retrieval.sql_tool import run_sql
from tests.conftest import SAMPLE


def test_load_csv_infers_types():
    info = load_table(SAMPLE / "sales.csv", "sales")
    assert info["rows"] > 2000
    assert "month DATE" in get_schema()["sales"]


def test_bad_table_name_rejected():
    with pytest.raises(ValueError):
        load_table(SAMPLE / "sales.csv", "sales; DROP TABLE x")


def test_readonly_connection_is_locked_down():
    load_table(SAMPLE / "sales.csv", "sales")
    with readonly_connection() as con:
        for sql in ["SELECT * FROM read_csv('pyproject.toml')", "CREATE TABLE x (a INT)",
                    "SET enable_external_access = true"]:
            with pytest.raises(duckdb.Error):
                con.execute(sql)


def test_run_sql_returns_json_rows():
    load_table(SAMPLE / "sales.csv", "sales")
    rows = run_sql("SELECT region, SUM(units_sold) AS u FROM sales GROUP BY 1 ORDER BY 1")
    assert [r["region"] for r in rows] == ["East", "North", "South", "West"]


def test_markdown_document_indexed_offline(sample_data):
    docs = doc_indexer.list_documents(with_tree=True)
    assert {d["status"] for d in docs} == {"ready"}
    sop = next(d for d in docs if d["name"] == "operations_sop.md")
    titles = [n["title"] for n in sop["tree"][0]["nodes"]]
    assert "Suppliers" in titles


def test_scanned_or_fake_pdf_rejected(tmp_path):
    fake = tmp_path / "x.pdf"
    fake.write_bytes(b"not a pdf")
    with pytest.raises(ValueError):
        doc_indexer.validate(fake)
