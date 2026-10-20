# PRD — Ice Cream Brand Intelligence Assistant

| | |
|---|---|
| **Status** | Draft v0.1 |
| **Date** | 2026-10-20 |
| **Owner** | hardik140 |
| **Related** | [TRD](TRD.md) |

## 1. Problem

An ice cream brand's knowledge is split across two worlds:

- **Documents** — market reports, supplier contracts, SOPs, campaign reports, exported customer reviews (PDFs).
- **Numbers** — sales, inventory and store data (CSV / Excel).

Managers who need a decision ("Should we drop the mango flavour in the north region?") must dig through both by hand or wait for an analyst. Answers are slow, inconsistent and rarely cite their source.

## 2. Goal

A chat assistant that answers business questions about the brand in plain language, **using the brand's own documents and data only**, with every answer **cited** and every number **exact**.

### Success metrics

| Metric | Target (v1) |
|---|---|
| Answer correctness on golden dataset (LLM-judge) | ≥ 85% |
| Groundedness (claims backed by a citation or SQL result) | ≥ 95% |
| Numeric answers matching ground-truth SQL | 100% |
| Router picks correct path (docs / numbers / both) | ≥ 90% |
| Off-topic / injection prompts blocked | ≥ 95% |
| p95 latency for `/chat` | ≤ 20 s |

## 3. Users

| Persona | Needs |
|---|---|
| **Brand / marketing manager** | Why is a flavour trending up or down? What do customers complain about? |
| **Sales / regional head** | Revenue by flavour, region, store, season. |
| **Operations / supply** | Supplier terms, SOP lookups, inventory questions. |
| **Data admin** | Upload new PDFs and sales files, see indexing status. |

## 4. User stories

1. As a manager, I ask *"Top 5 flavours by revenue in summer 2025 by region"* and get an exact table.
2. As a manager, I ask *"Why are customers unhappy with the chocolate cone?"* and get a summary with page citations from the review report.
3. As a manager, I ask *"Which flavour is declining in sales and also getting bad reviews?"* and get an answer that combines data and documents.
4. As an admin, I upload a PDF or CSV and see when it is ready to query.
5. As any user, if I ask something outside the brand's data (or try to break the system), I get a polite refusal — never a made-up answer.
6. As the developer, I can see every request's full trace and run an evaluation suite after any change.

## 5. Scope

### In scope (v1)
- Upload and index **text-based PDFs** (PageIndex, vectorless).
- Upload **CSV / Excel** sales data into a queryable store.
- Chat endpoint that routes to documents, data or both.
- Citations (document + page) and exact numbers from SQL.
- Guardrails: off-topic, prompt-injection, PII scrubbing, read-only SQL, groundedness check.
- Evaluation suite in LangSmith.
- REST backend, Docker, CI on GitHub.
- Sample (fake) brand dataset so anyone can run the project.

### Out of scope (v1)
- Scanned / image PDFs (needs PageIndex cloud OCR).
- User accounts, login, multi-tenant / multi-brand.
- Frontend beyond a minimal demo (API first).
- Forecasting / ML predictions.
- Live connections to POS or ERP systems.
- Cloud deployment.

## 6. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | System accepts PDF upload and indexes it asynchronously; status is queryable. |
| FR-2 | System accepts CSV/XLSX upload and loads it as a table. |
| FR-3 | `/chat` classifies the question as `docs`, `data`, `both` or `out_of_scope`. |
| FR-4 | Document answers cite document name and page. |
| FR-5 | Every number in an answer must come from an executed SQL result. |
| FR-6 | SQL is read-only; writes, DDL and multi-statements are rejected. |
| FR-7 | Inputs are screened for off-topic requests, prompt injection and PII before any retrieval. |
| FR-8 | Ungrounded answers are retried once, then replaced by an honest "I couldn't find this". |
| FR-9 | Every request is traced in LangSmith. |
| FR-10 | An evaluation command runs the golden dataset and reports all metrics in §2. |

## 7. Non-functional requirements

- **Modular:** each component (ingestion, retrieval, guardrails, graph, API) is swappable and tested alone.
- **Secure:** secrets only in `.env`; real brand data never committed.
- **Reproducible:** `docker compose up` + sample data = working demo.
- **Cost-aware:** cheap model for routing/guards, strong model for answers.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Local PageIndex only reads text PDFs | Validate on upload, return a clear error. |
| Several LLM calls per question → cost/latency | Small model for router and guards; cache document trees. |
| LLM writes wrong SQL | Schema in prompt, few-shot examples, SQL eval set. |
| No real brand data yet | Ship realistic synthetic dataset. |

## 9. Milestones

| # | Milestone |
|---|---|
| M1 | Repo skeleton, config, sample data |
| M2 | Ingestion (PageIndex + DuckDB) |
| M3 | Retrieval tools, tested alone |
| M4 | LangGraph flow + LangSmith tracing |
| M5 | Guardrails |
| M6 | FastAPI backend + Docker |
| M7 | Evaluation suite |
| M8 | CI + README polish |
