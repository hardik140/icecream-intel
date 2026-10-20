"""First line of defence for LLM-written SQL. The second is the locked-down DuckDB connection."""
import sqlglot
from sqlglot import exp

_FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop,
              exp.Alter, exp.Command, exp.Set, exp.Pragma, exp.Copy, exp.Attach, exp.Detach)


def check_sql(sql: str, max_rows: int = 1000) -> str:
    """Return the query wrapped with a row limit, or raise ValueError."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"SQL does not parse: {e}") from e
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is allowed")
    stmt = statements[0]
    if not isinstance(stmt, exp.Query):
        raise ValueError("Only SELECT queries are allowed")
    if any(isinstance(node, _FORBIDDEN) for node in stmt.walk()):
        raise ValueError("Query contains a forbidden operation")
    return f"SELECT * FROM ({stmt.sql(dialect='duckdb')}) AS q LIMIT {max_rows}"
