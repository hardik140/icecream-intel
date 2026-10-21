"""CSV/XLSX → DuckDB table, plus the locked-down connection used for LLM-written SQL."""
import re
from pathlib import Path

import duckdb
import pandas as pd

from app.core.config import get_settings

TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def snake(name) -> str:
    """'Year / period' -> 'year_period'. Never empty, never starts with a digit (SQL-safe identifier)."""
    s = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    return s if s[:1].isalpha() else f"c_{s}"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """SQL-friendly columns; text columns that are really numbers become numbers."""
    df = df.dropna(how="all").dropna(axis=1, how="all")
    names, seen = [], {}
    for c in df.columns:
        n = snake(c)
        seen[n] = seen.get(n, 0) + 1
        names.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    df.columns = names
    for c in df.columns[df.dtypes == object]:
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            df[c] = df[c].map(lambda v: None if pd.isna(v) else str(v))  # mixed text like "4–6" stays text
    return df


def load_table(path: Path, table_name: str) -> dict:
    """Load a CSV (one table) or a workbook (one table per non-empty sheet, `<name>_<sheet>`),
    replacing tables of the same name. Returns {"tables": [{table, rows, columns}, ...]}."""
    if not TABLE_NAME.match(table_name):
        raise ValueError("table_name must be lowercase letters, digits, underscores, starting with a letter")
    ext = path.suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise ValueError(f"Unsupported file type {ext}; use CSV or Excel")
    loaded = []
    with duckdb.connect(str(get_settings().db_path)) as con:
        # table names are regex-validated / snake-cased, so interpolation is safe
        try:
            if ext == ".csv":  # DuckDB's sniffer infers dates/numbers better than pandas
                con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto(?)", [str(path)])
                # same column naming as workbooks (DuckDB's normalize_names would turn "month" into "_month")
                for (col,) in con.execute(f"SELECT column_name FROM (DESCRIBE {table_name})").fetchall():
                    if snake(col) != col:
                        quoted = '"' + col.replace('"', '""') + '"'
                        con.execute(f"ALTER TABLE {table_name} RENAME COLUMN {quoted} TO {snake(col)}")
                loaded.append(table_name)
            else:
                sheets = {s: _prepare(df) for s, df in pd.read_excel(path, sheet_name=None).items()}
                sheets = {s: df for s, df in sheets.items() if not df.empty}
                for sheet, df in sheets.items():
                    name = table_name if len(sheets) == 1 else f"{table_name}_{snake(sheet)}"[:63]
                    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM df")
                    loaded.append(name)
        except (duckdb.Error, ValueError) as e:
            raise ValueError(f"Could not read file: {e}") from e
        tables = [{"table": t, "rows": con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0],
                   "columns": [c[0] for c in con.execute(f"DESCRIBE {t}").fetchall()]} for t in loaded]
    return {"tables": tables}


def upsert_rows(df: pd.DataFrame, table_name: str, key: str) -> int:
    """Insert rows, replacing existing rows with the same key. Creates the table on first use."""
    if not TABLE_NAME.match(table_name) or not TABLE_NAME.match(key):
        raise ValueError("invalid table or key name")
    with duckdb.connect(str(get_settings().db_path)) as con:
        con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM df LIMIT 0")
        con.execute(f"DELETE FROM {table_name} WHERE {key} IN (SELECT {key} FROM df)")
        con.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM df")
        return con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


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
