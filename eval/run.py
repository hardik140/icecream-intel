"""Run the golden dataset through the pipeline and score it in LangSmith.

Usage: python -m eval.run --experiment baseline [--recreate]   # LangSmith
       python -m eval.run --experiment baseline --local          # no LangSmith
Needs GOOGLE_API_KEY and LANGSMITH_API_KEY, and the sample data loaded (python -m scripts.load_sample_data).
Exits 1 if any metric is below its PRD target.
"""
import argparse
import json
import time
from pathlib import Path

from langsmith import Client

from app.core.config import get_settings
from app.graph.builder import ask
from app.guardrails.output_guard import facts_text
from eval.evaluators import ALL, TARGETS

GOLDEN = Path(__file__).parent / "datasets" / "golden.json"


def target(inputs: dict) -> dict:
    state = ask(inputs["question"])
    docs = state.get("doc_context") or []
    return {
        "answer": state["answer"],
        "route": state.get("route"),
        "blocked": state.get("blocked_reason"),
        "facts": facts_text(state.get("clean_question", inputs["question"]), docs, state.get("sql_result")),
        "doc_facts": "\n\n".join(f"{c.section}: {c.text}" for c in docs),
        "sections": [f"{c.doc_name} > {c.section}" for c in docs],
        "sql_error": state.get("sql_error"),
    }


def ensure_dataset(client: Client, name: str, recreate: bool) -> None:
    if client.has_dataset(dataset_name=name):
        if not recreate:
            return
        client.delete_dataset(dataset_name=name)
    items = json.loads(GOLDEN.read_text(encoding="utf-8"))
    ds = client.create_dataset(name, description="Ice cream brand golden Q&A")
    client.create_examples(dataset_id=ds.id, examples=[
        {"inputs": {"question": i["question"]}, "outputs": {k: v for k, v in i.items() if k != "question"}}
        for i in items
    ])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--experiment", default="baseline")
    p.add_argument("--dataset", default="icecream-golden")
    p.add_argument("--recreate", action="store_true", help="re-upload golden.json to LangSmith")
    p.add_argument("--concurrency", type=int, default=1, help="parallel questions; keep 1 on free tiers")
    p.add_argument("--local", action="store_true", help="score locally without LangSmith")
    args = p.parse_args()

    s = get_settings()  # loads .env into os.environ for LangSmith
    scores = run_local(s.data_dir / f"eval_{args.experiment}.json") if args.local else run_langsmith(args)
    failed = False
    print(f"\n{'metric':<22}{'score':>8}{'target':>8}{'n':>5}")
    for key, goal in TARGETS.items():
        vals = scores.get(key, [])
        score = sum(vals) / len(vals) if vals else float("nan")
        ok = score >= goal
        failed |= not ok
        print(f"{key:<22}{score:>8.2f}{goal:>8.2f}{len(vals):>5}  {'ok' if ok else 'BELOW TARGET'}")
    raise SystemExit(1 if failed else 0)


def run_langsmith(args) -> dict[str, list[float]]:
    client = Client()
    ensure_dataset(client, args.dataset, args.recreate)
    df = client.evaluate(target, data=args.dataset, evaluators=ALL, experiment_prefix=args.experiment,
                         max_concurrency=args.concurrency).to_pandas()
    return {k: df[f"feedback.{k}"].dropna().astype(float).tolist() for k in TARGETS if f"feedback.{k}" in df}


def run_local(report_path: Path) -> dict[str, list[float]]:
    """Same golden set and evaluators, no LangSmith. Writes per-question results to report_path."""
    scores: dict[str, list[float]] = {}
    report = []
    for i, item in enumerate(json.loads(GOLDEN.read_text(encoding="utf-8")), 1):
        inputs = {"question": item["question"]}
        reference = {k: v for k, v in item.items() if k != "question"}
        try:
            outputs = target(inputs)
        except Exception as e:  # one failing question must not kill the run
            outputs = {"answer": f"ERROR: {e}", "route": None, "blocked": None, "facts": "", "doc_facts": ""}
        row = {"question": item["question"], "answer": outputs["answer"], "route": outputs["route"],
               "sections": outputs.get("sections", []), "sql_error": outputs.get("sql_error"),
               "scores": {}, "comments": {}, "judge_errors": []}
        for ev in ALL:
            r = _evaluate(ev, inputs, outputs, reference)
            if r is None:
                row["judge_errors"].append(ev.__name__)
            elif r["score"] is not None:
                scores.setdefault(r["key"], []).append(float(r["score"]))
                row["scores"][r["key"]] = r["score"]
                row["comments"][r["key"]] = r.get("comment", "")
        fails = [k for k, v in row["scores"].items() if not v]
        status = "PASS" if not fails else "FAIL " + ",".join(fails)
        if row["judge_errors"]:
            status += f" (judge error: {','.join(row['judge_errors'])})"
        print(f"[{i:>2}] {status:<40} {item['question'][:70]}", flush=True)
        report.append(row)
        report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")  # partial results survive a crash
    print(f"\nPer-question report: {report_path}")
    return scores


def _evaluate(ev, inputs, outputs, reference) -> dict | None:
    """LLM judges can hit free-tier per-minute limits: wait for the window to reset, retry once, else skip."""
    for attempt in range(2):
        try:
            return ev(inputs, outputs, reference)
        except Exception as e:
            print(f"     judge {ev.__name__} failed ({type(e).__name__}); {'retrying in 60s' if attempt == 0 else 'skipped'}",
                  flush=True)
            if attempt == 0:
                time.sleep(60)
    return None


if __name__ == "__main__":
    main()
