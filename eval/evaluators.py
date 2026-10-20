"""LangSmith evaluators. LLM-as-judge prompts adapted from krishnaik06/RAG-Tutorials (1-rag_evaluation.ipynb).

Each evaluator gets (inputs, outputs, reference_outputs). A score of None means "not applicable".
"""
from pydantic import BaseModel

from app.core.llm import get_llm
from app.guardrails.output_guard import extract_numbers, judge_grounded

CORRECTNESS = """\
You are a teacher grading a quiz. You will be given a QUESTION, the GROUND TRUTH answer and the STUDENT answer.
(1) Grade the student answer ONLY on factual accuracy relative to the ground truth.
(2) Ensure the student answer does not contain conflicting statements.
(3) It is OK if the student answer contains more information, as long as it is factually accurate.
Explain your reasoning step-by-step before deciding.

QUESTION: {question}
GROUND TRUTH: {reference}
STUDENT ANSWER: {answer}"""

RETRIEVAL_RELEVANCE = """\
You are a teacher grading a quiz. You will be given a QUESTION and a set of FACTS retrieved for it.
The facts are relevant if they contain ANY keywords or meaning related to the question; some unrelated
information is fine. They are irrelevant only if completely unrelated.
Explain your reasoning step-by-step before deciding.

QUESTION: {question}
FACTS:
{facts}"""


class Grade(BaseModel):
    explanation: str
    passed: bool


def _judge(prompt: str) -> Grade:
    return get_llm("smart").with_structured_output(Grade).invoke(prompt)


def _na(key: str) -> dict:
    return {"key": key, "score": None}


def guard_correct(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Bad prompts blocked with the right label AND good prompts not blocked."""
    return {"key": "guard_correct", "score": outputs.get("blocked") == reference_outputs.get("blocked")}


def route_correct(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs.get("blocked"):
        return _na("route_correct")
    return {"key": "route_correct", "score": outputs.get("route") == reference_outputs["route"]}


def numbers_match(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Every expected number appears in the answer (sign and thousands separators ignored)."""
    expected = reference_outputs.get("numbers")
    if not expected:
        return _na("numbers_match")
    found = {abs(n) for n in extract_numbers(outputs["answer"])}
    missing = [n for n in expected if not any(abs(abs(n) - f) < 0.006 for f in found)]
    return {"key": "numbers_match", "score": not missing, "comment": f"missing: {missing}" if missing else ""}


def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs.get("blocked"):
        return _na("correctness")
    g = _judge(CORRECTNESS.format(question=inputs["question"], reference=reference_outputs["answer"],
                                  answer=outputs["answer"]))
    return {"key": "correctness", "score": g.passed, "comment": g.explanation}


def groundedness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs.get("blocked"):
        return _na("groundedness")
    g = judge_grounded(outputs["answer"], outputs["facts"])
    return {"key": "groundedness", "score": g.grounded, "comment": g.explanation}


def retrieval_relevance(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs.get("route") not in ("docs", "both"):
        return _na("retrieval_relevance")
    if not outputs.get("doc_facts"):
        return {"key": "retrieval_relevance", "score": False, "comment": "nothing retrieved"}
    g = _judge(RETRIEVAL_RELEVANCE.format(question=inputs["question"], facts=outputs["doc_facts"]))
    return {"key": "retrieval_relevance", "score": g.passed, "comment": g.explanation}


ALL = [guard_correct, route_correct, numbers_match, correctness, groundedness, retrieval_relevance]

# PRD §2 targets: the run fails if any metric is below its target.
TARGETS = {"correctness": 0.85, "groundedness": 0.95, "numbers_match": 1.0,
           "route_correct": 0.90, "guard_correct": 0.95, "retrieval_relevance": 0.90}
