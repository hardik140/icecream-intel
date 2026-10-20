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

> **Open item:** PageIndex local documents OpenAI keys and a `pageindex[claude]` extra for Claude subscriptions. Confirm in M2 that it runs with an Anthropic API key; fallback is an OpenAI key used only for PageIndex.

## 3. Repository layout

```
icecream-intel/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── api/                 # routes: documents, data, chat, health
│   ├── core/                # config (pydantic-settings), logging, llm factory
│   ├── ingestion/
│   │   ├── pdf_indexer.py   # PDF → PageIndex tree (background task)
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
    doc_context: list[Citation]    # {doc_id, doc_name, page, text}
    sql_query: str | None
    sql_result: list[dict] | None
    answer: str
    citations: list[Citation]
    grounded: bool
    retries: int
    blocked_reason: str | None
```

## 5. Components

### 5.1 Ingestion
- **PDF:** validate MIME type and that text is extractable (reject scanned PDFs with HTTP 422). Save the file, run PageIndex indexing as a FastAPI background task, store the tree JSON plus a `documents` registry row (`id, name, status, pages, created_at`).
- **Tables:** CSV/XLSX → `CREATE TABLE ... AS SELECT * FROM read_csv_auto(...)` (or via pandas for xlsx). Table names sanitised to `[a-z0-9_]`. Schema is stored for the SQL prompt.

### 5.2 Retrieval tools (LangChain `@tool`)
- `search_documents(question) -> list[Citation]` — PageIndex tree reasoning over indexed docs.
- `query_sales_data(question) -> {sql, rows}` — LLM writes SQL from schema + few-shot examples → SQL guard → execute.

### 5.3 Guardrails

| Guard | Check | Implementation |
|---|---|---|
| Input: size | ≤ 2,000 chars | Pydantic |
| Input: PII | emails, phones, card numbers masked | regex |
| Input: injection + topic | classify `ok / off_topic / injection` | Haiku, structured output |
| SQL | single `SELECT`, no DDL/DML/`ATTACH`/`COPY`/`PRAGMA`; `LIMIT 1000` enforced; 10 s timeout | `sqlglot` parse + read-only DuckDB connection |
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
| `POST` | `/chat` | `{question, stream?: bool}` | `{answer, citations, sql, route, trace_url}` or SSE stream |
| `GET` | `/health` | — | `{status, langsmith, llm}` |

Errors use a single shape: `{error: {code, message}}`.

## 7. Configuration (`.env`)

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=              # only if PageIndex needs it
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=icecream-intel
MODEL_FAST=claude-haiku-5-5
MODEL_SMART=claude-sonnet-5-5
DATA_DIR=./data/store
MAX_QUESTION_CHARS=2000
```

## 8. Evaluation

- **Dataset** (`eval/datasets/golden.json`, ~40 items): 12 docs, 12 data, 8 both, 8 adversarial (off-topic / injection). Each has `question`, `expected_route`, `expected_answer` and optionally `expected_sql_result`.
- **Evaluators** (LangSmith `evaluate()`):
  - `route_correct` — exact match
  - `answer_correctness` — LLM judge vs reference
  - `groundedness` — LLM judge vs retrieved context
  - `sql_result_match` — compare result rows to expected
  - `guard_blocked` — adversarial items must be blocked
- **Run:** `python -m eval.run --experiment <name>` → results in LangSmith; CI fails if any metric drops below PRD targets (manual trigger, since it costs tokens).

## 9. Observability
- LangSmith traces every graph run; `trace_url` returned in `/chat` response.
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
