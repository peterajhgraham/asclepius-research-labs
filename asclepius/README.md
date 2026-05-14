# Asclepius — Web Application

> Production-grade scientific research intelligence: proposition-level hybrid retrieval, causal graph integration, 3-tier confidence-gated inference routing, and real-time SSE streaming.

---

## Overview

This directory contains the deployable web application. The backend is a FastAPI service exposing 15+ REST endpoints, including an SSE streaming endpoint that delivers inference tokens and citations concurrently. The frontend is a Next.js 15 App Router application that proxies all inference traffic server-side to avoid exposing API keys to the browser.

The system is domain-agnostic — the `vertical` parameter is a free-text string passed at query time. No source changes are required to switch from immunology to oncology, neuroscience, or any other scientific domain.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · Pydantic v2 · Uvicorn · asyncio |
| Retrieval | BM25 (BM25Okapi) + FAISS (all-MiniLM-L6-v2) + RRF k=60 + CrossEncoder (ms-marco-MiniLM-L-6-v2) |
| Inference Routing | 3-tier hierarchy with heuristic confidence estimation and daily budget cap |
| Graph | Causal belief propagation (decay=0.85) + intervention ranking |
| Observability | structlog JSON + Prometheus counters/histograms + JSONL cost audit |
| Persistence | SQLAlchemy async ORM + aiosqlite (PostgreSQL-compatible via URL) |
| Frontend | Next.js 15 (App Router) · TypeScript · TailwindCSS · Framer Motion · react-markdown |
| Deployment | Railway (backend) · Vercel (frontend) |

---

## Project Structure

```
asclepius/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI app + background retrieval warm-up
│   │   ├── api/
│   │   │   └── routes.py                   # 15+ endpoints + SSE streaming
│   │   ├── core/
│   │   │   └── config.py                   # Pydantic-settings: API keys, budget cap, DB URL
│   │   ├── retrieval/
│   │   │   ├── bm25_index.py               # BM25Okapi in-memory lexical index
│   │   │   ├── dense_index.py              # FAISS IndexFlatIP + sentence-transformers
│   │   │   ├── fusion.py                   # Reciprocal Rank Fusion (k=60)
│   │   │   ├── reranker.py                 # CrossEncoder ms-marco-MiniLM-L-6-v2
│   │   │   └── pipeline.py                 # Unified hybrid pipeline singleton
│   │   ├── chunking/
│   │   │   ├── document_parser.py          # PyMuPDF → text blocks + image blocks
│   │   │   ├── image_captioner.py          # Vision model → figure caption propositions
│   │   │   ├── proposition_extractor.py    # Atomic claim extraction from raw text
│   │   │   └── sliding_window.py           # Word-level chunker (no-API fallback)
│   │   ├── routing/
│   │   │   ├── classifier.py               # Query complexity → starting inference tier
│   │   │   ├── cost_tracker.py             # JSONL audit log + daily budget enforcement
│   │   │   └── router.py                   # 3-tier routing + streaming with metadata sentinel
│   │   ├── observability/
│   │   │   ├── metrics.py                  # Prometheus counters and histograms
│   │   │   └── logging.py                  # structlog JSON structured output
│   │   ├── db/
│   │   │   ├── models.py                   # SQLAlchemy async ORM (Proposition, Paper)
│   │   │   └── store.py                    # Async CRUD operations (aiosqlite)
│   │   ├── services/
│   │   │   ├── retrieval_service.py        # Pipeline singleton; KB + dataset indexing at startup
│   │   │   ├── llm_service.py              # Orchestration: retrieval → routing → response
│   │   │   ├── query_engine.py             # Structured keyword search across indexed datasets
│   │   │   ├── pubmed_service.py           # NCBI E-utilities search + interaction extraction
│   │   │   ├── graph_service.py            # Causal propagation + intervention ranking
│   │   │   ├── comparative_service.py      # Multi-dimensional topic comparison
│   │   │   ├── hypothesis_service.py       # 5-strategy testable hypothesis generation
│   │   │   ├── dossier_service.py          # Persistent research workspace CRUD
│   │   │   └── ingestion_service.py        # PDF ingestion: parse → chunk → caption → index
│   │   ├── data/
│   │   │   ├── knowledge_base.py           # Curated KB entries (domain-configurable)
│   │   │   └── ingestion.py                # JSON dataset loaders
│   │   ├── dmi/                            # Disease/Mechanism Intelligence module
│   │   │   ├── disease_report.py           #   Structured mechanism reports (domain = runtime param)
│   │   │   └── target_risk.py              #   Target druggability + risk scoring
│   │   └── models/
│   │       └── schema.py                   # Pydantic schemas for all request/response types
│   ├── tests/
│   │   └── test_retrieval.py               # 33 tests: BM25, FAISS, RRF, reranking, routing, cost
│   ├── scripts/
│   │   └── setup_dev.sh                    # One-shot venv + deps + .env bootstrap
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx                         # Main UI: 5 modes, SSE streaming, citation panel
    │   ├── layout.tsx                       # Root layout + optional auth provider
    │   └── api/                             # Next.js server-side proxy routes
    │       ├── query/stream/route.ts        #   SSE proxy → backend /query/stream
    │       └── ...                          #   One route per backend endpoint
    ├── components/
    │   ├── StreamingResponse.tsx            # Token-by-token streaming + markdown rendering
    │   ├── CitationPanel.tsx                # Sliding citation panel (retrieved propositions)
    │   ├── ResponseCard.tsx                 # Structured reasoning: entities, pathways, targets
    │   ├── CompareCard.tsx                  # Side-by-side topic comparison layout
    │   ├── HypothesisCard.tsx               # Testable hypothesis cards with experimental designs
    │   ├── DiseaseReportCard.tsx            # DMI mechanism report structured display
    │   └── TargetRiskCard.tsx               # Target risk assessment display
    ├── hooks/
    │   └── useStreamingQuery.ts             # SSE hook: AbortController + event type parsing
    └── lib/
        ├── api.ts                           # Typed API client (domain-agnostic field names)
        ├── backend.ts                       # URL resolver + server-side proxy helpers
        └── dmi-api.ts                       # DMI endpoint client (domain as free-text string)
```

---

## Retrieval Pipeline

Every query passes through the following stages:

```
Query ──► BM25 (BM25Okapi)            ──┐
          Dense (FAISS / all-MiniLM)  ──┴──► RRF(k=60) ──► CrossEncoder ──► top-8 propositions
                                                                                    │
                                    Structured KB search (entities, pathways, therapeutics)
                                                                                    │
                                          Causal graph (1-hop subgraph, signed edges)
                                                                                    │
                                   Inference Router: Tier I → Tier II → Tier III
                                   (escalates when confidence heuristic < 0.60)
                                                                                    │
                                         SSE stream / structured JSON response
```

BM25 and FAISS execute in parallel. RRF merges ranked lists without score normalization — ordinal rank is invariant to score distribution shape. The CrossEncoder reranks the merged set to produce the final eight propositions passed as grounded context.

---

## Inference Routing

Streaming always uses Tier I for minimum latency. Non-streaming endpoints apply full confidence-gated escalation.

| Tier | Latency profile | Cost profile | Escalation trigger |
|------|-----------------|--------------|--------------------|
| I — Rapid | Lowest | Lowest | Default for all queries |
| II — Balanced | Moderate | ~4× Tier I | Response confidence < 0.60 |
| III — Deep | Highest | ~19× Tier I | Response confidence < 0.60 after Tier II |

The confidence heuristic is intentionally simple: responses shorter than 150 characters score 0.30; responses containing uncertainty phrases score 0.40; all others score 0.85. Threshold is 0.60. A daily budget cap (`DAILY_BUDGET_USD`, default $10.00) is enforced as a pre-call check before every inference request. All spend is written to `data/routing_logs/YYYY-MM-DD.jsonl`.

The streaming endpoint emits a terminal metadata sentinel as the last generator item — `{"_done": true, "model": "...", "cost": 0.000xx}` — which the route handler consumes to populate the SSE `done` event with the actual model ID and precise cost, rather than a hardcoded placeholder.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/query/stream?question=...` | **SSE streaming** — tokens + citations delivered in real-time |
| `POST` | `/query` | Standard structured JSON response |
| `POST` | `/query/images` | Multimodal — base64 image + question, KB-grounded visual analysis |
| `POST` | `/ingest/document` | PDF upload — text extraction + chunking + figure captioning + index rebuild |
| `POST` | `/compare` | Multi-dimensional side-by-side topic comparison |
| `POST` | `/hypotheses` | Testable hypothesis generation (5 strategies) |
| `POST` | `/pubmed/search` | Live PubMed search + molecular interaction extraction |
| `GET` | `/graph/stats` | Knowledge graph statistics |
| `POST` | `/graph/subgraph` | 1-hop subgraph extraction around seed nodes |
| `GET` | `/graph/hubs` | Highest-degree nodes in the graph |
| `POST` | `/graph/propagate` | Causal signal propagation (configurable decay, direction) |
| `POST` | `/graph/interventions` | Rank upstream intervention candidates by predicted phenotypic impact |
| `POST` | `/dmi/disease-report` | Structured mechanism report (domain = runtime parameter) |
| `POST` | `/dmi/target-risk` | Target druggability and risk scoring (domain = runtime parameter) |
| `GET` | `/metrics` | Cost tracking + pipeline health (Prometheus exposition format) |
| `GET` | `/health` | Service health + retrieval index status |
| `POST/GET/PUT/DELETE` | `/dossiers/*` | Research dossier CRUD |

### SSE Event Schema

```
start:     {"type": "start",     "question": "..."}
citations: {"type": "citations", "data": [{text, score, rerank_score, type, pmid, source}, ...]}
token:     {"type": "token",     "text": "..."}
done:      {"type": "done",      "model": "...", "cost": 0.00042, "sources": [...]}
error:     {"type": "error",     "message": "..."}
```

Citations are emitted before the first token, allowing the frontend to populate the citation panel while the answer is still generating.

---

## Domain Configuration

Pass any string as `vertical`. No source changes required.

```json
{ "disease_name": "Alzheimer's disease", "vertical": "neuroscience" }
{ "disease_name": "Non-small cell lung cancer", "target_name": "EGFR", "vertical": "oncology" }
{ "question": "How does tau aggregation drive neurodegeneration?" }
```

Built-in prompt templates are available for `immunology`, `oncology`, and `neuroscience`. Any other value resolves to a general scientific extraction prompt.

---

## Environment Variables

### Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | — | Primary inference key — 3-tier routing |
| `DAILY_BUDGET_USD` | | `10.00` | Hard spend cap; enforced before each inference call |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./data/asclepius.db` | Async proposition store; swap URL for PostgreSQL |
| `OPENAI_API_KEY` | | — | Fallback inference provider |
| `NCBI_API_KEY` | | — | Raises PubMed rate limit from 3 to 10 req/s |

### Frontend

| Variable | Required | Description |
|----------|----------|-------------|
| `API_URL` | ✅ | Backend base URL (used server-side only; never exposed to browser) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | | Clerk auth (optional) |
| `CLERK_SECRET_KEY` | | Clerk auth (optional) |

---

## Development

> **macOS venv note:** `python` may resolve to system Python 3.9 even inside an activated virtualenv. Use `venv/bin/python` and `venv/bin/uvicorn` explicitly, or rely on `scripts/setup_dev.sh`.

```bash
# Backend
cd asclepius/backend
bash scripts/setup_dev.sh                    # creates venv, installs deps, copies .env.example
cp .env.example .env                         # add ANTHROPIC_API_KEY
venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app

# Tests
venv/bin/pytest tests/test_retrieval.py -v

# Frontend (separate terminal)
cd asclepius/frontend
cp .env.local.example .env.local             # set API_URL=http://localhost:8000
npm install && npm run dev
```

Swagger UI: `http://localhost:8000/docs` · Frontend: `http://localhost:3000`

---

## Deployment

### Railway (backend)

Set *Root Directory* = `asclepius/backend`. Railway auto-detects Python via `requirements.txt` and `.python-version`, resolves the `Procfile` (`web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`), and starts the service.

Cold-start note: `all-MiniLM-L6-v2` (~90 MB) downloads on first deploy. Subsequent starts use Railway's volume cache, reducing warm-up from ~30s to ~5s.

### Vercel (frontend)

Set *Root Directory* = `asclepius/frontend`. Vercel auto-detects Next.js 15, applies App Router build conventions, and manages the serverless function routes automatically.
