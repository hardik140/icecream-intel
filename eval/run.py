"""Run the golden dataset through the pipeline and score it in LangSmith.

Usage: python -m eval.run --experiment baseline [--recreate]
Needs ANTHROPIC_API_KEY and LANGSMITH_API_KEY, and the sample data loaded (python -m scripts.load_sample_data).
Exits 1 if any metric is below its PRD target.
"""
import argparse
import json
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
    args = p.parse_args()

    get_settings()  # loads .env into os.environ for LangSmith
    client = Client()
    ensure_dataset(client, args.dataset, args.recreate)
    results = client.evaluate(target, data=args.dataset, evaluators=ALL,
                              experiment_prefix=args.experiment, max_concurrency=2)

    df = results.to_pandas()
    failed = False
    print(f"\n{'metric':<22}{'score':>8}{'target':>8}")
    for key, goal in TARGETS.items():
        col = df.get(f"feedback.{key}")
        score = col.dropna().astype(float).mean() if col is not None and col.notna().any() else float("nan")
        ok = score >= goal
        failed |= not ok
        print(f"{key:<22}{score:>8.2f}{goal:>8.2f}  {'ok' if ok else 'BELOW TARGET'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
