# Ice Cream Brand Intelligence Assistant

Ask business questions about an ice cream brand in plain language. Answers come from the brand's own documents (**vectorless RAG** with [PageIndex](https://github.com/VectifyAI/PageIndex)) and sales data (**SQL** on DuckDB), with citations, exact numbers and guardrails.

**Stack:** LangChain · LangGraph · LangSmith · PageIndex (local, free) · DuckDB · FastAPI · Google Gemini + Groq (automatic fallback)

```
question → input guard → router → PageIndex tree search ┐
                                → SQL on sales data     ┴→ synthesize → output guard → answer
```

Docs: [PRD](docs/PRD.md) · [TRD](docs/TRD.md)

## Quickstart

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
copy .env.example .env                               # add GOOGLE_API_KEY, GROQ_API_KEY, LANGSMITH_API_KEY

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
| `POST` | `/documents` | Upload a PDF or Markdown file; PageIndex tree built in the background (PDFs via PageIndex cloud if `PAGEINDEX_API_KEY` is set) |
| `GET` | `/documents` | List documents and indexing status |
| `DELETE` | `/documents/{id}` | Remove a document |
| `POST` | `/data` | Upload CSV/Excel as a DuckDB table (`table_name` form field) |
| `GET` | `/data/tables` | Tables and columns |
| `POST` | `/collect/google-maps` | Scrape competitors from Google Maps (background job, 1–5 min) |
| `GET` | `/collect/jobs/{id}` | Collection job status and summary |
| `POST` | `/chat` | Ask a question → answer, route, citations, SQL, LangSmith run id |
| `GET` | `/health` | Keys configured, documents ready, tables loaded |

## Competitor data from Google Maps

Uses [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) (MIT). Places go into the `competitors` table (rating, review count, star breakdown, location, ...) for SQL, and reviews go into a Markdown document for PageIndex.

```bash
python -m scripts.install_gmaps_scraper     # downloads the pinned binary into bin/ (~60 MB)
curl -X POST localhost:8000/collect/google-maps -H "Content-Type: application/json" \
     -d '{"queries": ["ice cream parlour in Koramangala Bangalore"]}'
```

Then ask: *"Which competitors near Koramangala have the best ratings, and what do their customers praise?"*

> ⚠️ This is a scraper, not an official Google API, and it may violate Google's Terms of Service. Keep volume low (max 10 queries per job, one job at a time). Reviewer names, photos and profile links are dropped, and review text is PII-scrubbed. For production use, switch to the official Places API.

## PageIndex: local or cloud

- **No `PAGEINDEX_API_KEY`:** PDFs are indexed locally, so they must have a text layer, and indexing uses our LLM tokens.
- **With `PAGEINDEX_API_KEY`:** PDFs go to PageIndex cloud. It does OCR, so scanned PDFs work, and no tokens of ours are spent. A 12-page report took about 30 s. Deleting a document also deletes its cloud copy.
- Markdown is always indexed locally from its headings, which is free.
- Retrieval always runs here. When all document trees together are too large for one prompt (the free tiers cap a request at about 7k tokens), a cheap first step picks up to 3 documents, and only their trees are searched.

## Two LLM providers

| Tier | Used for | Primary | Fallback |
|---|---|---|---|
| fast | guards, router, judges | Groq `openai/gpt-oss-20b` | Gemini `gemini-3.5-flash-lite` |
| smart | tree search, SQL, answers | Gemini `gemini-3.5-flash` | Groq `openai/gpt-oss-120b`, then `qwen/qwen3.8-27b` |

Any error on the primary (quota, outage) switches to the other provider automatically. A provider without a key is skipped, so either key alone also works. Models are `provider:model` strings in `.env`.

## Guardrails

- **Input:** PII masking (email, phone, card), LLM classifier blocks off-topic and prompt-injection.
- **SQL:** sqlglot allows one `SELECT` only, row limit enforced; DuckDB connection is read-only with file/network access disabled and settings locked.
- **Output:** every number must appear in the SQL result or sources; LLM groundedness judge; one retry, then an honest "couldn't find it".

## Tests and evaluation

```bash
pytest -q                                   # offline, fake LLM, no keys needed
RUN_LIVE_SCRAPE=1 pytest tests/test_google_maps.py   # + one real Google Maps scrape
python -m eval.run --experiment baseline    # real LLM, results in LangSmith, fails below PRD targets
python -m eval.run --experiment baseline --local   # same, scored locally (no LangSmith)
```

The evaluation runs `eval/datasets/golden.json` (data, document, combined and attack questions) with the evaluators `guard_correct`, `route_correct`, `numbers_match`, `correctness`, `groundedness` and `retrieval_relevance`.

## Project layout

```
app/
  api/          FastAPI routes (thin)
  core/         settings, logging, LLM factory
  collectors/   google_maps (scraper → competitors table + reviews doc)
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
