from langchain_core.tools import tool


@tool
def query_sales_data(question: str) -> dict:
    """Answer numeric questions (sales, revenue, inventory) by running read-only SQL. Returns {sql, rows}."""
    raise NotImplementedError("M3")
