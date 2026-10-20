# Ice Cream Brand Intelligence Assistant

Ask business questions about an ice cream brand in plain language. Answers come from the brand's own documents (**vectorless RAG** with [PageIndex](https://github.com/VectifyAI/PageIndex)) and sales data (**SQL** on DuckDB), with citations, exact numbers and guardrails.

**Stack:** LangChain · LangGraph · LangSmith · PageIndex (local, free) · DuckDB · FastAPI · Claude

```
question → input guard → router → PageIndex tree search ┐
                                → SQL on sales data     ┴→ synthesize → output guard → answer
```

Docs: [PRD](docs/PRD.md) · [TRD](docs/TRD.md)

## Quickstart

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
copy .env.example .env                               # add ANTHROPIC_API_KEY and LANGSMITH_API_KEY

python -m scripts.load_sample_data                   # sample brand "Frosty Scoops": sales.csv + 3 docs
uvicorn app.main:app --reload                        # open http://localhost:8000/docs
```

Try `POST /chat`:

```json
{"question": "How did Mango Alphonso revenue in the North change from 2024 to 2025, and why?"}
```

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/documents` | Upload a text PDF or Markdown file; PageIndex tree built in the background |
| `GET` | `/documents` | List documents and indexing status |
| `DELETE` | `/documents/{id}` | Remove a document |
| `POST` | `/data` | Upload CSV/Excel as a DuckDB table (`table_name` form field) |
| `GET` | `/data/tables` | Tables and columns |
| `POST` | `/chat` | Ask a question → answer, route, citations, SQL, LangSmith run id |
| `GET` | `/health` | Keys configured, documents ready, tables loaded |

## Guardrails

- **Input:** PII masking (email, phone, card), LLM classifier blocks off-topic and prompt-injection.
- **SQL:** sqlglot allows one `SELECT` only, row limit enforced; DuckDB connection is read-only with file/network access disabled and settings locked.
- **Output:** every number must appear in the SQL result or sources; LLM groundedness judge; one retry, then an honest "couldn't find it".

## Tests and evaluation

```bash
pytest -q                                   # offline, fake LLM, no keys needed
python -m eval.run --experiment baseline    # real LLM, results in LangSmith, fails below PRD targets
```

The evaluation runs `eval/datasets/golden.json` (data, document, combined and attack questions) with the evaluators `guard_correct`, `route_correct`, `numbers_match`, `correctness`, `groundedness` and `retrieval_relevance`.

## Project layout

```
app/
  api/          FastAPI routes (thin)
  core/         settings, logging, LLM factory
  ingestion/    doc_indexer (PageIndex), table_loader (DuckDB)
  retrieval/    pageindex_tool (tree search), sql_tool
  guardrails/   input, sql, output guards
  graph/        LangGraph state, nodes, builder
  prompts/      every prompt in one file
eval/           golden dataset, evaluators, LangSmith runner
scripts/        sample data generator and loader
tests/
```

## Credits

The tree search, expert-rules routing and LLM-judge evaluators are adapted from [krishnaik06/RAG-Tutorials](https://github.com/krishnaik06/RAG-Tutorials).
