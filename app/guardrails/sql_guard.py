"""Allow only a single SELECT; enforce LIMIT. Parsed with sqlglot."""


def check_sql(sql: str, max_rows: int = 1000) -> str:
    """Return safe SQL (with LIMIT) or raise ValueError. (M5)"""
    raise NotImplementedError("M5")
