"""Groundedness: numbers must come from SQL rows / sources, claims must be backed by the facts."""
import json
import re

from pydantic import BaseModel

from app.core.llm import get_llm
from app.prompts import GROUNDEDNESS

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def extract_numbers(text: str) -> set[float]:
    out = set()
    for raw in _NUMBER.findall(text):
        try:
            out.add(float(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def ungrounded_numbers(answer: str, sources: str) -> list[float]:
    """Numbers in the answer that appear nowhere in the sources (SQL rows, doc text, question)."""
    allowed = set()
    for n in extract_numbers(sources):
        n = abs(n)  # "fell 23.09%" is grounded by a SQL value of -23.09
        allowed |= {n, round(n, 2), round(n, 1), float(round(n))}
    # Small integers ("top 3", "Q2", list numbering) are not data claims.
    return sorted(n for n in map(abs, extract_numbers(answer)) if n not in allowed and not (n.is_integer() and n <= 12))


class GroundedGrade(BaseModel):
    explanation: str
    grounded: bool


def judge_grounded(answer: str, facts: str) -> GroundedGrade:
    llm = get_llm("fast").with_structured_output(GroundedGrade)
    return llm.invoke(GROUNDEDNESS.format(facts=facts, answer=answer))


def facts_text(question: str, docs: list, rows: list[dict] | None) -> str:
    """Everything the answer is allowed to rely on, as one string."""
    parts = [f"QUESTION: {question}"]
    parts += [f"[{c.doc_name}, {c.location}] {c.section}\n{c.text}" for c in docs]
    if rows:
        parts.append("SQL RESULT: " + json.dumps(rows, ensure_ascii=False))
    return "\n\n".join(parts)
