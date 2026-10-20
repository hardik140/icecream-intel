"""CSV/XLSX → DuckDB table."""
from pathlib import Path


def load_table(path: Path, table_name: str) -> dict:
    """Load file into DuckDB, return {table, rows, columns}. (M2)"""
    raise NotImplementedError("M2")


def get_schema() -> dict[str, list[str]]:
    """Return {table: [column types]} for the SQL prompt. (M2)"""
    raise NotImplementedError("M2")
