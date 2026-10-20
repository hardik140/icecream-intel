"""One function per graph node. Each takes GraphState and returns a partial state update."""
import json
import logging

import duckdb
from pydantic import BaseModel

from app.core.llm import get_llm
from app.graph.state import GraphState, Route
from app.guardrails.input_guard import classify_input, scrub_pii
from app.guardrails.output_guard import facts_text, judge_grounded, ungrounded_numbers
from app.ingestion.table_loader import get_schema
from app.prompts import NOT_FOUND, REFUSALS, ROUTER, SYNTHESIZE
from app.retrieval.pageindex_tool import search_documents
from app.retrieval.sql_tool import format_schema, query_sales_data

log = logging.getLogger(__name__)
MAX_RETRIES = 1


def input_guard(state: GraphState) -> dict:
    clean = scrub_pii(state["question"])
    verdict = classify_input(clean)
    if verdict.label != "ok":
        log.info("Blocked input (%s): %s", verdict.label, verdict.reason)
        return {"clean_question": clean, "blocked_reason": verdict.label, "answer": REFUSALS[verdict.label]}
    return {"clean_question": clean, "blocked_reason": None, "retries": 0}


class RouteDecision(BaseModel):
    route: Route


def route(state: GraphState) -> dict:
    prompt = ROUTER.format(schema=format_schema(get_schema()), question=state["clean_question"])
    decision = get_llm("fast").with_structured_output(RouteDecision).invoke(prompt)
    update = {"route": decision.route}
    if decision.route == "out_of_scope":
        update["answer"] = REFUSALS["out_of_scope"]
    return update


def retrieve_docs(state: GraphState) -> dict:
    return {"doc_context": search_documents(state["clean_question"])}


def query_data(state: GraphState) -> dict:
    try:
        result = query_sales_data(state["clean_question"])
    except (ValueError, duckdb.Error) as e:
        log.warning("SQL path failed: %s", e)
        return {"sql_query": None, "sql_result": None, "sql_error": str(e)}
    return {"sql_query": result["sql"], "sql_result": result["rows"], "sql_error": None}


def synthesize(state: GraphState) -> dict:
    docs = state.get("doc_context") or []
    feedback = state.get("guard_feedback")
    prompt = SYNTHESIZE.format(
        question=state["clean_question"],
        docs="\n\n".join(f"[{c.doc_name}, {c.location}] {c.section}\n{c.text}" for c in docs) or "(none)",
        sql=state.get("sql_query") or state.get("sql_error") or "(none)",
        rows=json.dumps(state.get("sql_result"), ensure_ascii=False) if state.get("sql_result") else "(none)",
        feedback=f"\nYour previous answer was rejected: {feedback}. Fix this.\n" if feedback else "",
    )
    return {"answer": get_llm("smart").invoke(prompt).text}


def output_guard(state: GraphState) -> dict:
    facts = facts_text(state["clean_question"], state.get("doc_context") or [], state.get("sql_result"))
    problems = []
    if bad := ungrounded_numbers(state["answer"], facts):
        problems.append(f"these numbers are not in the SQL result or documents: {bad}")
    grade = judge_grounded(state["answer"], facts)
    if not grade.grounded:
        problems.append(grade.explanation)
    if not problems:
        return {"grounded": True, "guard_feedback": None}
    retries = state.get("retries", 0)
    if retries < MAX_RETRIES:
        return {"grounded": False, "guard_feedback": "; ".join(problems), "retries": retries + 1}
    log.warning("Answer still ungrounded after retry: %s", problems)
    return {"grounded": False, "guard_feedback": None, "answer": NOT_FOUND}
