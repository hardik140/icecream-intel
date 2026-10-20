"""Groundedness: claims backed by citations, numbers backed by SQL rows."""


def numbers_grounded(answer: str, sql_rows: list[dict] | None) -> bool:
    """Every number in the answer appears in sql_rows. (M5)"""
    raise NotImplementedError("M5")


def is_grounded(answer: str, context: str) -> bool:
    """LLM judge: is the answer supported by context? (M5)"""
    raise NotImplementedError("M5")
