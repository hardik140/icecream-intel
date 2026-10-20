# TRD — Ice Cream Brand Intelligence Assistant

| | |
|---|---|
| **Status** | Draft v0.1 |
| **Date** | 2026-10-20 |
| **Related** | [PRD](PRD.md) |

## 1. Architecture

```
            ┌──────────────┐
 question → │ input guard  │── blocked → refusal
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │   router     │  docs / data / both
            └──┬────────┬──┘
               ▼        ▼
     ┌──────────────┐ ┌──────────────┐
     │ PageIndex    │ │ SQL agent    │  read-only DuckDB
     │ tree search  │ │              │
     └──────┬───────┘ └──────┬───────┘
            └──────┬─────────┘
                   ▼
            ┌──────────────┐
            │  synthesize  │  answer + citations
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │ output guard │── ungrounded → retry once → "not found"
            └──────┬───────┘
                   ▼
                answer          (all nodes traced in LangSmith)
```

## 2. Tech stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Orchestration | **LangGraph** | State machine above |
| LLM + tools | **LangChain** (`langchain-anthropic`, `langchain-community`) | |
| Tracing + eval | **LangSmith** | Free tier: 5k traces/month |
| Document retrieval | **PageIndex** local (`pip install pageindex`, MIT) | Vectorless, tree-based, text PDFs only |
| Numeric data | **DuckDB** | Embedded, read-only connection for queries |
| Backend | **FastAPI** + Uvicorn | Async, streaming responses |
| Validation | Pydantic v2 / pydantic-settings | Request models, config, structured LLM output |
| Tests | pytest | |
| Packaging | `pyproject.toml`, Docker, docker-compose | |
| CI | GitHub Actions | lint + tests on push |

### Models (default, configurable in `.env`)

| Role | Model |
|---|---|
| Router, guards, PageIndex indexing | `claude-haiku-5-5` |
| SQL generation, synthesis, PageIndex chat | `claude-sonnet-5-5` |
| Eval judge | `claude-sonnet-5-5` |

> **Resolved:** PageIndex local calls models through LiteLLM, so `anthropic/<model>` works with `ANTHROPIC_API_KEY`. No OpenAI key needed. Markdown files are indexed from their headings with no LLM call at all.

## 3. Repository layout

```
icecream-intel/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── api/                 # routes: documents, data, chat, health
│   ├── core/                # config (pydantic-settings), logging, llm factory
│   ├── ingestion/
│   │   ├── doc_indexer.py   # PDF / Markdown → PageIndex tree (background task)
│   │   └── table_loader.py  # CSV/XLSX → DuckDB table
│   ├── retrieval/
│   │   ├── pageindex_tool.py
│   │   └── sql_tool.py
│   ├── guardrails/
│   │   ├── input_guard.py
│   │   ├── sql_guard.py
│   │   └── output_guard.py
│   ├── graph/
│   │   ├── state.py         # GraphState TypedDict
│   │   ├── nodes.py
│   │   └── builder.py       # build_graph()
│   └── prompts/             # all prompt templates
├── eval/
│   ├── datasets/golden.json
│   ├── evaluators.py
│   └── run.py
├── data/
│   ├── sample/              # synthetic PDFs + sales.csv (committed)
│   └── store/               # duckdb file, PageIndex trees (git-ignored)
├── scripts/make_sample_data.py
├── tests/
├── docs/  PRD.md  TRD.md
├── Dockerfile  docker-compose.yml  pyproject.toml
└── .env.example  .gitignore  README.md
```

**Rule:** routes call services; services never import from `api/`. Each folder in `app/` can be unit-tested without the others.

## 4. Graph state

```python
class GraphState(TypedDict):
    question: str
    clean_question: str            # after PII scrub
    route: Literal["docs", "data", "both", "out_of_scope"]
    doc_context: list[Citation]    # {doc_id, doc_name, section, location ("p.3-5" | "line 12"), text}
    sql_query: str | None
    sql_result: list[dict] | None
    sql_error: str | None
    answer: str
    grounded: bool
    guard_feedback: str | None     # why the output guard rejected the last answer (drives the retry)
    retries: int
    blocked_reason: str | None
```

## 5. Components

### 5.1 Ingestion
- **Documents:** PDF or Markdown. PDFs must have extractable text (scanned → HTTP 422). The file is saved, and the PageIndex tree is built as a FastAPI background task: `page_index()` for PDFs (LLM, with node summaries) and `md_to_tree()` for Markdown (headings, offline). Each document is one JSON file in `data/store/docs/` (`doc_id, name, status, tree, created_at`).
- **Tables:** CSV goes through DuckDB `read_csv_auto` (infers dates); XLSX goes through pandas. Table names must match `^[a-z][a-z0-9_]*$`. The schema is read from `information_schema` for the prompts.

### 5.2 Retrieval (plain functions called by graph nodes)
- `search_documents(question) -> list[Citation]`: all ready document trees are compressed (titles plus 150-char summaries, node ids prefixed with `doc_id:`) and sent to the LLM with ice-cream **expert routing rules**. The LLM returns node ids; their full section text becomes the context. This is adapted from the PageIndex crash course in krishnaik06/RAG-Tutorials.
- `query_sales_data(question) -> {sql, rows}`: the LLM writes SQL from the schema and a few-shot example, then it passes the SQL guard and runs on a locked-down connection with a timeout.

### 5.3 Guardrails

| Guard | Check | Implementation |
|---|---|---|
| Input: size | ≤ 2,000 chars | Pydantic |
| Input: PII | emails, phones, card numbers masked | regex |
| Input: injection + topic | classify `ok / off_topic / injection` | Haiku, structured output |
| SQL | single `SELECT`, no DDL/DML/`ATTACH`/`COPY`/`PRAGMA`; `LIMIT 1000` enforced; 10 s timeout | `sqlglot` parse + DuckDB `read_only`, `enable_external_access=false`, `lock_configuration=true` |
| Output: grounding | every claim supported by context; every number present in `sql_result` | LLM judge + numeric cross-check |
| Output: citations | doc answers must include ≥1 citation | code check |

Failure on output guard → one retry with feedback → else fixed "couldn't find this in your data" message.

### 5.4 Synthesis
Single prompt: question + doc citations + SQL rows → answer in markdown with `[doc, p.N]` citations and a short "what this means for the business" line.

## 6. API

| Method | Path | Body / Params | Response |
|---|---|---|---|
| `POST` | `/documents` | multipart PDF | `202 {id, status:"indexing"}` |
| `GET` | `/documents` | — | list with status |
| `DELETE` | `/documents/{id}` | — | `204` |
| `POST` | `/data` | multipart CSV/XLSX, `table_name` | `201 {table, rows, columns}` |
| `GET` | `/data/tables` | — | tables + schemas |
| `POST` | `/chat` | `{question}` | `{answer, route, blocked, grounded, citations, sql, run_id}` (streaming not built yet) |
| `GET` | `/health` | — | `{status, langsmith, llm}` |

Errors use a single shape: `{error: {code, message}}`.

## 7. Configuration (`.env`)

```
ANTHROPIC_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=icecream-intel
MODEL_FAST=claude-haiku-5-5
MODEL_SMART=claude-sonnet-5-5
DATA_DIR=./data/store
MAX_QUESTION_CHARS=2000
```

## 8. Evaluation

- **Dataset** (`eval/datasets/golden.json`, 22 items for now; target is 40): 6 data, 6 docs, 4 both, 6 adversarial (off-topic / injection). Each item has `question` plus `route`, `answer` and optionally `numbers`, or `blocked` for attack items. The expected numbers come from the sample `sales.csv`.
- **Evaluators** (LangSmith `evaluate()`, judges adapted from krishnaik06/RAG-Tutorials):
  - `guard_correct`: attack items blocked with the right label, and normal items not blocked
  - `route_correct`: exact match
  - `numbers_match`: every expected number appears in the answer
  - `correctness`: LLM judge against the reference answer
  - `groundedness`: LLM judge against the retrieved sections and SQL rows
  - `retrieval_relevance`: LLM judge on the retrieved sections
- **Run:** `python -m eval.run --experiment <name>` → results in LangSmith; CI fails if any metric drops below PRD targets (manual trigger, since it costs tokens).

## 9. Observability
- LangSmith traces every graph run; the `run_id` is returned in the `/chat` response.
- Structured JSON logs (request id, route, latency, tokens).

## 10. Security
- Secrets only via env; `.env` git-ignored.
- `data/store/` and any real data git-ignored.
- DuckDB opened `read_only=True` for queries; separate write connection only in ingestion.
- Upload size limit (25 MB) and type validation.
- PII scrubbed before any LLM call.

## 11. Testing

| Level | What |
|---|---|
| Unit | guards (PII regex, SQL guard allow/deny cases), table loader, state transitions |
| Integration | graph with LLM mocked; API routes with `TestClient` |
| Eval | LangSmith suite (real LLM, manual/CI-dispatch) |

## 12. Delivery plan
Matches PRD milestones M1–M8; one PR per milestone, CI green before merge.
