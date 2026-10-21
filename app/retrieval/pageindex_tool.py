"""Vectorless retrieval: the LLM reads every document's PageIndex tree and picks the sections to read.

Adapted from llm_tree_search / find_nodes_by_ids in krishnaik06/RAG-Tutorials (PageIndex crash course),
extended to search across all indexed documents at once.
"""
import json

from pydantic import BaseModel

from app.core.llm import get_llm
from app.graph.state import Citation
from app.ingestion.doc_indexer import list_documents
from app.prompts import EXPERT_RULES, TREE_SEARCH

MAX_SECTIONS = 6
MAX_SECTION_CHARS = 6000


class TreeSearch(BaseModel):
    thinking: str
    node_list: list[str]


def _location(node: dict) -> str:
    if "start_index" in node:
        start, end = node["start_index"], node.get("end_index", node["start_index"])
        return f"p.{start}" if start == end else f"p.{start}-{end}"
    return f"line {node.get('line_num', '?')}"


def _compress(nodes: list[dict], doc_id: str) -> list[dict]:
    """Titles + short summaries only, to keep the prompt small. Node ids are made unique across docs."""
    out = []
    for n in nodes:
        entry = {"node_id": f"{doc_id}:{n['node_id']}", "title": n["title"], "location": _location(n),
                 "summary": (n.get("summary") or n.get("text") or "")[:150]}
        if n.get("nodes"):
            entry["children"] = _compress(n["nodes"], doc_id)
        out.append(entry)
    return out


def _find(nodes: list[dict], ids: set[str], doc: dict) -> list[Citation]:
    found = []
    for n in nodes:
        if f"{doc['doc_id']}:{n['node_id']}" in ids:
            found.append(Citation(doc_id=doc["doc_id"], doc_name=doc["name"], section=n["title"],
                                  location=_location(n), text=(n.get("text") or "")[:MAX_SECTION_CHARS]))
        found += _find(n.get("nodes") or [], ids, doc)
    return found


def document_outline() -> str:
    """One line per ready document with its top-level sections, so the router knows what docs cover."""
    lines = []
    for d in list_documents(with_tree=True):
        if d["status"] != "ready":
            continue
        tree = d["tree"]
        # Markdown trees have one root (the H1 title); its children are the real sections
        top = tree[0].get("nodes") or tree if len(tree) == 1 else tree
        lines.append(f"- {d['name']}: " + "; ".join(n["title"] for n in top[:12]))
    return "\n".join(lines) or "(no documents)"


def search_documents(question: str) -> list[Citation]:
    """Return the document sections that answer the question, with locations for citation."""
    docs = [d for d in list_documents(with_tree=True) if d["status"] == "ready"]
    if not docs:
        return []
    trees = [{"doc_name": d["name"], "nodes": _compress(d["tree"], d["doc_id"])} for d in docs]
    prompt = TREE_SEARCH.format(rules=EXPERT_RULES, question=question, trees=json.dumps(trees, indent=1))
    result = get_llm("smart").with_structured_output(TreeSearch).invoke(prompt)
    ids = set(result.node_list)
    return [c for d in docs for c in _find(d["tree"], ids, d)][:MAX_SECTIONS]
