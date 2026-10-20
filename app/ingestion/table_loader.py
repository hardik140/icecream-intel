"""CSV/XLSX → DuckDB table, plus the locked-down connection used for LLM-written SQL."""
import re
from pathlib import Path

import duckdb
import pandas as pd

from app.core.config import get_settings

TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def load_table(path: Path, table_name: str) -> dict:
    """Load file into DuckDB (replacing any table of that name). Returns {table, rows, columns}."""
    if not TABLE_NAME.match(table_name):
        raise ValueError("table_name must be lowercase letters, digits, underscores, starting with a letter")
    ext = path.suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise ValueError(f"Unsupported file type {ext}; use CSV or Excel")
    with duckdb.connect(str(get_settings().db_path)) as con:
        # table_name is regex-validated above, so interpolation is safe
        try:
            if ext == ".csv":  # DuckDB's sniffer infers dates/numbers better than pandas
                con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto(?)", [str(path)])
            else:
                df = pd.read_excel(path)  # noqa: F841 — referenced by name in the SQL below
                con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
        except (duckdb.Error, ValueError) as e:
            raise ValueError(f"Could not read file: {e}") from e
        rows = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        columns = [c[0] for c in con.execute(f"DESCRIBE {table_name}").fetchall()]
    return {"table": table_name, "rows": rows, "columns": columns}


def readonly_connection() -> duckdb.DuckDBPyConnection:
    """No writes, no file/network access, settings locked — safe for LLM-generated SQL.

    shortcut: one connection per query; a query during an upload can hit DuckDB's file lock.
    Move to a single shared connection if uploads become frequent.
    """
    path = get_settings().db_path
    if not path.exists():
        raise ValueError("No sales data loaded yet. Upload a CSV/Excel file first.")
    return duckdb.connect(str(path), read_only=True,
                          config={"enable_external_access": False, "lock_configuration": True})


def get_schema() -> dict[str, list[str]]:
    """{table: ["column TYPE", ...]} for the SQL prompt and /data/tables."""
    try:
        con = readonly_connection()
    except ValueError:
        return {}
    with con:
        rows = con.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'main' ORDER BY table_name, ordinal_position"
        ).fetchall()
    schema: dict[str, list[str]] = {}
    for table, col, dtype in rows:
        schema.setdefault(table, []).append(f"{col} {dtype}")
    return schema
