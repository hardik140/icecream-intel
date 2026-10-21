"""Tree search: one-step when all trees fit in a prompt, documents picked first when they don't."""
import re

from app.retrieval import pageindex_tool
from app.retrieval.pageindex_tool import DocChoice, TreeSearch


def _pick_supplier_section(prompt: str) -> TreeSearch:
    return TreeSearch(thinking="", node_list=re.findall(r'"node_id":"([^"]+)","title":"Mango Pulp"', prompt))


def test_small_corpus_searches_all_trees_in_one_step(sample_data, fake_llm):
    fake = fake_llm({"TreeSearch": _pick_supplier_section})
    found = pageindex_tool.search_documents("Who supplies mango pulp?")
    assert [c.section for c in found] == ["Mango Pulp"]
    assert fake.calls == ["TreeSearch"]


def test_large_corpus_picks_documents_first(sample_data, fake_llm, monkeypatch):
    monkeypatch.setattr(pageindex_tool, "MAX_TREE_PROMPT_CHARS", 1000)
    tree_prompts = []

    def tree_search(prompt):
        tree_prompts.append(prompt)
        return _pick_supplier_section(prompt)

    fake = fake_llm({"DocChoice": lambda p: DocChoice(doc_names=["operations_sop.md"]),
                     "TreeSearch": tree_search})
    found = pageindex_tool.search_documents("Who supplies mango pulp?")
    assert fake.calls == ["DocChoice", "TreeSearch"]
    assert "operations_sop.md" in tree_prompts[0] and "customer_review_report" not in tree_prompts[0]
    assert [c.section for c in found] == ["Mango Pulp"]


def test_unknown_document_names_fall_back_to_all(sample_data, fake_llm, monkeypatch):
    monkeypatch.setattr(pageindex_tool, "MAX_TREE_PROMPT_CHARS", 1000)
    fake_llm({"DocChoice": lambda p: DocChoice(doc_names=["made_up.pdf"]), "TreeSearch": _pick_supplier_section})
    assert [c.section for c in pageindex_tool.search_documents("Who supplies mango pulp?")] == ["Mango Pulp"]
