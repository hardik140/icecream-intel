import duckdb
import pandas as pd
import pytest

from app.ingestion import doc_indexer
from app.ingestion.table_loader import get_schema, load_table, readonly_connection
from app.retrieval.sql_tool import run_sql
from tests.conftest import SAMPLE


def test_load_csv_infers_types():
    info = load_table(SAMPLE / "sales.csv", "sales")
    assert info["tables"][0]["rows"] > 2000
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


def test_workbook_loads_every_sheet_with_sql_safe_columns(tmp_path):
    book = tmp_path / "market.xlsx"
    with pd.ExcelWriter(book) as w:
        pd.DataFrame({"Year / period": [2020, 2025], "Value": ["116", "243.5"]}).to_excel(w, sheet_name="Market Data", index=False)
        pd.DataFrame({"Company": ["Amul", "Hatsun"], "Share / range": [19, "4–6"]}).to_excel(w, sheet_name="Competitors", index=False)
        pd.DataFrame().to_excel(w, sheet_name="Empty", index=False)
    info = load_table(book, "market")
    assert [t["table"] for t in info["tables"]] == ["market_market_data", "market_competitors"]
    assert get_schema()["market_market_data"] == ["year_period BIGINT", "value DOUBLE"]  # "116" text -> number
    assert get_schema()["market_competitors"] == ["company VARCHAR", "share_range VARCHAR"]  # mixed stays text


def test_snake_names():
    from app.ingestion.table_loader import snake
    assert snake("Year / period") == "year_period" and snake("2026 value") == "c_2026_value" and snake("%") == "c_"
