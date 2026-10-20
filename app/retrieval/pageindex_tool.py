from langchain_core.tools import tool


@tool
def search_documents(question: str) -> list[dict]:
    """Search the brand's indexed documents (reports, SOPs, reviews). Returns citations with doc name and page."""
    raise NotImplementedError("M3")
