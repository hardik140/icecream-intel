"""Numeric questions → LLM-written SQL → guard → locked-down DuckDB → rows."""
import json
import threading

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.llm import get_llm
from app.guardrails.sql_guard import check_sql
from app.ingestion.table_loader import get_schema, readonly_connection
from app.prompts import SQL_GENERATION


class SQLQuery(BaseModel):
    sql: str


def format_schema(schema: dict[str, list[str]]) -> str:
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in schema.items()) or "(no tables loaded)"


def run_sql(sql: str) -> list[dict]:
    """Guard, then execute with a timeout. Raises ValueError (guard) or duckdb.Error (execution)."""
    s = get_settings()
    safe_sql = check_sql(sql, s.max_sql_rows)
    with readonly_connection() as con:
        timer = threading.Timer(s.sql_timeout_s, con.interrupt)
        timer.start()
        try:
            df = con.execute(safe_sql).fetchdf()
        finally:
            timer.cancel()
    # via JSON so dates/decimals/NaN become plain JSON-safe values
    return json.loads(df.to_json(orient="records", date_format="iso"))


def query_sales_data(question: str) -> dict:
    """Return {sql, rows}. Raises ValueError if there is no data or the SQL is rejected."""
    schema = get_schema()
    if not schema:
        raise ValueError("No sales data loaded yet")
    prompt = SQL_GENERATION.format(schema=format_schema(schema), question=question)
    sql = get_llm("smart").with_structured_output(SQLQuery).invoke(prompt).sql
    return {"sql": sql, "rows": run_sql(sql)}
