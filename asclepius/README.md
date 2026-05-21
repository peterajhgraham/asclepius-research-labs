# Asclepius — Web Application

> Production-grade scientific research intelligence: **truly multimodal** proposition-level retrieval (text + figures + tables fused via CLIP), causal graph integration, tool-using research agent, figure-grounded verification, 3-tier confidence-gated inference routing, and real-time SSE streaming.

---

## Overview

This directory contains the deployable web application. The backend is a FastAPI service exposing 18+ REST endpoints, including two SSE streaming endpoints: `/query/stream` for single-shot RAG (tokens + citations concurrently) and `/query/agent` for the tool-using research agent (planner steps + tool calls + final answer + optional verification). The frontend is a Next.js 15 App Router application that proxies all inference traffic server-side to avoid exposing API keys to the browser, and renders retrieved figures and tables inline in the citation panel.

The system is domain-agnostic — the `vertical` parameter is a free-text string passed at query time. No source changes are required to switch from immunology to oncology, neuroscience, or any other scientific domain.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · Pydantic v2 · Uvicorn · asyncio |
| Retrieval (3-leg hybrid) | BM25Okapi (lexical) + FAISS+all-MiniLM-L6-v2 (semantic text) + FAISS+CLIP ViT-B/32 (cross-modal text↔image) + RRF k=60 + CrossEncoder (ms-marco-MiniLM-L-6-v2) |
| PDF parsing | PyMuPDF (reading-order text + dedup'd embedded images) + pdfplumber (tables → markdown + bbox) + region rasterization |
| Chunking | Layout-aware sentence-bounded packer (~1800 chars, page-bounded) + Haiku proposition extraction |
| Image storage | Content-addressed disk store (`./data/images/<shard>/<hash>.<ext>`) with SHA-256 dedup |
| Multimodal LLM | Anthropic vision content blocks — retrieved figures + tables attached to every grounded answer |
| Research agent | Anthropic native tool-use loop (Sonnet 4.6 planner; retriever / PubMed / graph / comparator as tools) |
| Verification | Sonnet vision pass over cited figures — claim-level supported / unclear / unsupported tagging |
| Inference Routing | 3-tier hierarchy with heuristic confidence estimation and daily budget cap |
| Graph | Causal belief propagation (decay=0.85) + intervention ranking |
| Observability | structlog JSON + Prometheus counters/histograms + JSONL cost audit |
| Persistence | SQLAlchemy async ORM + aiosqlite (PostgreSQL-compatible via URL); backward-compatible ALTER TABLE migrations for multimodal columns |
| Frontend | Next.js 15 (App Router) · TypeScript · TailwindCSS · Framer Motion · react-markdown · inline figure/table rendering in citation panel |
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
│   │   │   ├── dense_index.py              # FAISS IndexFlatIP + all-MiniLM-L6-v2
│   │   │   ├── clip_index.py               # FAISS IndexFlatIP + CLIP ViT-B/32 (text↔image)
│   │   │   ├── fusion.py                   # Reciprocal Rank Fusion (k=60)
│   │   │   ├── reranker.py                 # CrossEncoder ms-marco-MiniLM-L-6-v2
│   │   │   └── pipeline.py                 # 3-leg hybrid (BM25 + dense + CLIP) + optional image-probe leg
│   │   ├── chunking/
│   │   │   ├── document_parser.py          # PyMuPDF text + dedup'd embedded images
│   │   │   ├── table_extractor.py          # pdfplumber tables → markdown + bbox + raster
│   │   │   ├── layout_chunker.py           # Page-bounded sentence packer (~1800 chars)
│   │   │   ├── image_captioner.py          # Haiku vision caption + CLIP image embedding
│   │   │   ├── proposition_extractor.py    # Atomic claim extraction from raw text
│   │   │   └── sliding_window.py           # Word-level chunker (no-API fallback)
│   │   ├── storage/
│   │   │   └── image_store.py              # Content-addressed disk store (SHA-256 sharded)
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
│   │   │   ├── retrieval_service.py        # Pipeline singleton; KB + dataset + DB (multimodal) indexing
│   │   │   ├── llm_service.py              # Orchestration: retrieval → routing → response (vision attachment)
│   │   │   ├── agent_service.py            # Tool-using research agent (mode="research")
│   │   │   ├── verification_service.py     # Figure-grounded verification (verify=True)
│   │   │   ├── query_engine.py             # Structured keyword search across indexed datasets
│   │   │   ├── pubmed_service.py           # NCBI E-utilities search + interaction extraction
│   │   │   ├── graph_service.py            # Causal propagation + intervention ranking
│   │   │   ├── comparative_service.py      # Multi-dimensional topic comparison
│   │   │   ├── hypothesis_service.py       # 5-strategy testable hypothesis generation
│   │   │   ├── dossier_service.py          # Persistent research workspace CRUD
│   │   │   └── ingestion_service.py        # PDF → text + figures + tables, CLIP-embedded
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
    │   ├── page.tsx                         # Main UI: 6 modes (incl. Research Agent), dual SSE, citation panel
    │   ├── layout.tsx                       # Root layout + optional auth provider
    │   └── api/                             # Next.js server-side proxy routes
    │       ├── query/stream/route.ts        #   SSE proxy → backend /query/stream
    │       ├── query/agent/route.ts         #   SSE proxy → backend /query/agent (research agent)
    │       ├── images/[hash]/route.ts       #   Streams figure rasters from /images/{hash}
    │       └── ...                          #   One route per backend endpoint
    ├── components/
    │   ├── StreamingResponse.tsx            # Token-by-token streaming + markdown rendering
    │   ├── AgentTrace.tsx                   # Research-agent planner-step / tool-call / verification trace
    │   ├── CitationPanel.tsx                # Sliding citation panel — renders figure thumbs + table previews
    │   ├── QueryInputBar.tsx                # Composer with mode switcher + pubmed/verify toggles
    │   ├── ResponseCard.tsx                 # Structured reasoning: entities, pathways, targets
    │   ├── CompareCard.tsx                  # Side-by-side topic comparison layout
    │   ├── HypothesisCard.tsx               # Testable hypothesis cards with experimental designs
    │   ├── DiseaseReportCard.tsx            # DMI mechanism report structured display
    │   └── TargetRiskCard.tsx               # Target risk assessment display
    ├── hooks/
    │   ├── useStreamingQuery.ts             # SSE hook for /query/stream
    │   └── useAgentStream.ts                # SSE hook for /query/agent (planner steps, tool calls, verification)
    └── lib/
        ├── api.ts                           # Typed API client (domain-agnostic field names)
        ├── backend.ts                       # URL resolver + server-side proxy helpers
        └── dmi-api.ts                       # DMI endpoint client (domain as free-text string)
```

---

## Multimodal Retrieval Pipeline

Every query passes through the following stages:

```
Query (+ optional probe image)
   ├── BM25 (lexical, BM25Okapi)                  ──┐
   ├── Dense (FAISS / all-MiniLM-L6-v2)            ──┤
   ├── CLIP text→image (FAISS / ViT-B/32)          ──┤  RRF(k=60) ─► CrossEncoder ─► top-8
   └── CLIP image→image (only if probe supplied)   ──┘                              propositions
                                                                                  (text + figures + tables)
                                                                                                 │
                                  Structured KB search (entities, pathways, therapeutics)        │
                                                                                                 │
                                        Causal graph (1-hop subgraph, signed edges)              │
                                                                                                 │
                              Inference Router: Tier I → Tier II → Tier III                      │
                              (escalates when confidence heuristic < 0.60)                       │
                              Retrieved figures + table rasters attached as vision blocks ◄──────┘
                                                                                                 │
                                          SSE stream / structured JSON response                  │
                                                                                                 │
                                       Optional figure-grounded verification ◄───────────────────┘
                                       (verify=True; Sonnet vision over cited figures)
```

The three retrieval legs execute in parallel. RRF merges ranked lists without score normalization — ordinal rank is invariant to score distribution shape, which matters since BM25, dense cosine, and CLIP cosine are not score-compatible. The CrossEncoder reranks the merged set; image-only candidates surfaced by CLIP carry their caption text into the reranker so the cross-encoder always has a textual side for the pair. Figures and table rasters in the top-K get attached to the LLM call as native Anthropic vision content blocks, so the model can read the actual pixels rather than only a caption paraphrase.

### Research Agent Path (opt-in, `mode="research"`)

```
  Question
     ▼
  Sonnet 4.6 planner (Anthropic native tool-use)
     │
     ├── search_knowledge_base   (the 3-leg hybrid retriever above, as a tool)
     ├── search_pubmed            (NCBI E-utilities)
     ├── causal_propagate         (signed-edge propagation)
     ├── rank_interventions       (upstream target ranking)
     ├── compare_topics           (side-by-side comparison)
     │
     ▼  max 5 iterations · 90s wall-clock · daily budget cap
  final_answer ─► SSE: planner_step / tool_call / tool_result / final / verification / done
```

The agent goes *on top of* the retriever — never instead of it. Replacing a strong hybrid retriever with LLM-driven search is strictly worse on every published benchmark.

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
| `GET` | `/query/stream?question=...` | **SSE streaming** — single-shot RAG: tokens + multimodal citations (text · figures · tables) delivered in real-time |
| `GET` | `/query/agent?question=...&verify=...` | **SSE streaming** — tool-using research agent: planner steps, tool calls, tool results, final answer, optional verification |
| `POST` | `/query` | Structured JSON response. `mode="research"` dispatches the agent; `verify=true` runs figure-grounded verification |
| `POST` | `/query/images` | Multimodal — probe image + question; CLIP image→image retrieval surfaces visually similar archival figures, all attached to vision call |
| `POST` | `/ingest/document` | PDF upload — text + figures (CLIP-embedded, disk-stored, dedup'd) + tables (pdfplumber, markdown + raster), all indexed |
| `GET` | `/images/{image_hash}` | Stream a stored figure / table raster by SHA-256 hash (immutable cache) |
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

### SSE Event Schema — `/query/stream`

```
start:     {"type": "start",     "question": "..."}
citations: {"type": "citations", "data": [
              {text, score, rerank_score, type, pmid, source,
               content_type ("text"|"image"|"table"),
               image_hash, image_url, page, table_markdown}, ...]}
token:     {"type": "token",     "text": "..."}
done:      {"type": "done",      "model": "...", "cost": 0.00042, "sources": [...]}
error:     {"type": "error",     "message": "..."}
```

Citations are emitted before the first token, allowing the frontend to populate the citation panel (with figure thumbnails and table previews inline) while the answer is still generating.

### SSE Event Schema — `/query/agent`

```
start:        {"type": "start", "question": "..."}
planner_step: {"type": "planner_step", "iteration": N, "thinking": "...", "tool_calls": ["..."]}
tool_call:    {"type": "tool_call", "iteration": N, "tool": "...", "args": {...}}
tool_result:  {"type": "tool_result", "iteration": N, "tool": "...", "result_preview": "..."}
final:        {"type": "final", "answer": "...", "image_hashes": ["..."]}
verification: {"type": "verification", "verdict": "...", "confidence": 0.x,
               "notes": "...", "revised_answer": "...", "images_inspected": N}
done:         {"type": "done", "iterations": N, "model": "...", "cost_usd": 0.x}
error:        {"type": "error", "message": "..."}
```

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

Cold-start note: `all-MiniLM-L6-v2` (~90 MB), `cross-encoder/ms-marco-MiniLM-L-6-v2` (~80 MB), and `clip-ViT-B-32` (~600 MB) are downloaded on first deploy. The CLIP model loads lazily on the first query that exercises the multimodal leg, so initial startup is unaffected by it. Subsequent starts use Railway's volume cache.

The image store lives at `./data/images/` (sharded by 2-char SHA-256 prefix). Mount a persistent Railway volume there if you want ingested figures to survive container restarts; otherwise the CLIP embeddings persist in SQLite and the figures will be re-extractable from re-ingested PDFs.

### Vercel (frontend)

Set *Root Directory* = `asclepius/frontend`. Vercel auto-detects Next.js 15, applies App Router build conventions, and manages the serverless function routes automatically.
