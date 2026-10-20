"""Every test gets an empty data dir and a fake LLM — no network, no API keys, no LangSmith traces."""
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.core.config import get_settings

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"
LLM_USERS = ["app.graph.nodes", "app.guardrails.input_guard", "app.guardrails.output_guard",
             "app.retrieval.sql_tool", "app.retrieval.pageindex_tool"]


class FakeLLM:
    """responses: {SchemaName: callable(prompt) -> instance, "text": callable(prompt) -> str}."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []

    def with_structured_output(self, schema):
        fake = self

        class _Structured:
            def invoke(self, prompt):
                fake.calls.append(schema.__name__)
                return fake.responses[schema.__name__](prompt)

        return _Structured()

    def invoke(self, prompt):
        self.calls.append("text")
        return AIMessage(content=self.responses["text"](prompt))


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_llm(monkeypatch):
    def install(responses: dict) -> FakeLLM:
        fake = FakeLLM(responses)
        for mod in LLM_USERS:
            monkeypatch.setattr(f"{mod}.get_llm", lambda tier="smart": fake)
        return fake
    return install


@pytest.fixture
def sample_data():
    """sales.csv in DuckDB + the Markdown docs indexed (offline)."""
    import shutil
    from app.ingestion import doc_indexer
    from app.ingestion.table_loader import load_table

    load_table(SAMPLE / "sales.csv", "sales")
    for src in sorted(SAMPLE.glob("*.md")):
        tmp = get_settings().data_dir / src.name
        shutil.copy(src, tmp)
        doc_indexer.build_tree(doc_indexer.register(tmp, src.name))
