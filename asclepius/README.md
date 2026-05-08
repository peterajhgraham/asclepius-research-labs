# Asclepius Research Labs — Web Application

Domain-agnostic scientific research intelligence platform. Query any field — immunology, oncology, neuroscience, climate science, ML, or any scientific domain. Hybrid BM25 + dense retrieval pipeline, 4-tier LLM routing, SSE streaming, causal knowledge graph propagation, and structured scientific reasoning. Domain is a runtime parameter; no hardcoded domain focus.

## Stack

| Layer       | Technology |
|-------------|------------|
| Backend     | Python · FastAPI · Pydantic · Uvicorn |
| Retrieval   | BM25 (rank-bm25) + FAISS (sentence-transformers/all-MiniLM-L6-v2) + RRF k=60 + CrossEncoder (ms-marco-MiniLM-L-6-v2) |
| LLM Routing | Anthropic (Haiku → Sonnet → Opus auto-escalation) · OpenAI fallback |
| Graph       | Causal propagation (decay=0.85) · Intervention ranking |
| Frontend    | Next.js 15 (App Router) · TypeScript · TailwindCSS · Framer Motion · react-markdown |
| Deployment  | Railway (backend) · Vercel (frontend) |

---

## Project Structure

```
asclepius/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI app + retrieval warm-up on startup
│   │   ├── api/
│   │   │   └── routes.py                   # 15+ endpoints + GET /query/stream (SSE)
│   │   ├── core/
│   │   │   └── config.py                   # Settings: ANTHROPIC_API_KEY, DAILY_BUDGET_USD, DATABASE_URL
│   │   ├── retrieval/
│   │   │   ├── bm25_index.py               # BM25Okapi lexical index
│   │   │   ├── dense_index.py              # FAISS IndexFlatIP + sentence-transformers
│   │   │   ├── fusion.py                   # Reciprocal Rank Fusion (k=60)
│   │   │   ├── reranker.py                 # CrossEncoder ms-marco-MiniLM-L-6-v2
│   │   │   └── pipeline.py                 # Unified hybrid pipeline
│   │   ├── chunking/
│   │   │   ├── proposition_extractor.py    # Claude Haiku atomic claim extraction
│   │   │   └── sliding_window.py           # Word-level chunker with overlap
│   │   ├── routing/
│   │   │   ├── classifier.py               # Query complexity → starting tier
│   │   │   ├── cost_tracker.py             # JSONL audit log + daily budget cap
│   │   │   └── router.py                   # 4-tier Anthropic routing + streaming
│   │   ├── observability/
│   │   │   ├── metrics.py                  # Prometheus counters/histograms
│   │   │   └── logging.py                  # structlog JSON output
│   │   ├── db/
│   │   │   ├── models.py                   # SQLAlchemy async ORM (Proposition, Paper)
│   │   │   └── store.py                    # Async SQLite CRUD (aiosqlite)
│   │   ├── services/
│   │   │   ├── retrieval_service.py        # Pipeline singleton, KB + dataset indexing
│   │   │   ├── llm_service.py              # Anthropic routing → OpenAI fallback → local
│   │   │   ├── query_engine.py             # Structured keyword search across indexed datasets
│   │   │   ├── pubmed_service.py           # Live NCBI E-utilities search
│   │   │   ├── graph_service.py            # Causal propagation + intervention ranking
│   │   │   ├── comparative_service.py      # Topic vs topic comparison
│   │   │   ├── hypothesis_service.py       # Testable hypothesis generation
│   │   │   └── dossier_service.py          # Persistent research workspaces
│   │   ├── data/
│   │   │   ├── knowledge_base.py           # Curated KB entries (domain-specific data loaded here)
│   │   │   └── ingestion.py                # JSON dataset loaders (edges, pathways, entities, therapeutics)
│   │   ├── dmi/                            # Mechanism Intelligence module (domain = runtime param)
│   │   │   ├── disease_report.py           # Structured mechanism reports
│   │   │   └── target_risk.py              # Target druggability + risk scoring
│   │   └── models/
│   │       └── schema.py                   # Pydantic request/response schemas
│   ├── tests/
│   │   └── test_retrieval.py               # 33 tests covering BM25, RRF, chunking, routing, costs
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx                        # Main UI: streaming mode, citation panel, session mgmt
    │   ├── layout.tsx                      # ClerkProvider (optional), Inter font
    │   └── api/
    │       ├── query/stream/route.ts       # SSE proxy → FastAPI /query/stream
    │       └── ...                         # Other Next.js API proxy routes
    ├── components/
    │   ├── StreamingResponse.tsx           # Token-by-token streaming display + markdown
    │   ├── CitationPanel.tsx               # Sliding citation panel (retrieved propositions)
    │   ├── ResponseCard.tsx                # Structured reasoning display (cells, cytokines, pathways)
    │   ├── CompareCard.tsx                 # Side-by-side disease comparison
    │   ├── HypothesisCard.tsx              # Testable hypothesis cards
    │   ├── DiseaseReportCard.tsx           # Disease Mechanism Intelligence report
    │   └── TargetRiskCard.tsx              # Target risk assessment
    ├── hooks/
    │   └── useStreamingQuery.ts            # SSE streaming hook (AbortController, event parsing)
    └── lib/
        ├── api.ts                          # Typed API functions + StructuredReasoning (domain-agnostic fields)
        ├── backend.ts                      # Backend URL resolver + proxy helpers
        └── dmi-api.ts                      # DMI API functions (domain is a free-text string)
```

---

## Domain Configuration

The `domain` (called `vertical` in the API) is a **runtime parameter** — pass any string:

```json
// Disease/Mechanism Report
{ "disease_name": "Alzheimer's disease", "vertical": "neuroscience" }

// Target Risk
{ "disease_name": "Non-small cell lung cancer", "target_name": "EGFR", "vertical": "oncology" }

// Standard query — domain inferred from question
{ "question": "How does tau aggregation drive neurodegeneration?" }
```

Built-in domain focus templates: `immunology`, `oncology`, `neuroscience`. Any other value uses a general scientific extraction prompt.

---

## Environment Variables

### Backend (Railway)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | — | Haiku/Sonnet/Opus routing |
| `DAILY_BUDGET_USD` | | `10.00` | Hard daily spend cap |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./data/asclepius.db` | Async SQLite for proposition store |
| `OPENAI_API_KEY` | | — | Fallback if no Anthropic key |
| `NCBI_API_KEY` | | — | Boosts PubMed rate limits |

### Frontend (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | | Clerk auth (optional) |
| `CLERK_SECRET_KEY` | | Clerk auth (optional) |
| `API_URL` | ✅ | Railway backend URL |

---

## Retrieval Pipeline

Every query flows through:

```
Query → BM25 (rank-bm25)     ─┐
        Dense (FAISS/MiniLM)  ─┼→ RRF(k=60) → CrossEncoder reranker → top-8 propositions
                                ┘
             ↓
        Structured KB search (cytokines, pathways, diseases, therapeutics)
             ↓
        Causal graph propagation (decay=0.85, 1-hop subgraph)
             ↓
        LLM Router: Haiku → Sonnet → Opus (escalates if confidence < 0.60)
             ↓
        SSE stream to frontend / JSON response
```

The retrieval pipeline indexes ~1,000+ documents from the configured knowledge base and datasets at startup (warm-up runs in a background thread, ~30s on cold start with ML model downloads). Index content is domain-agnostic — swap in datasets for any scientific field.

---

## LLM Routing

| Tier | Model | Input $/M | Output $/M | Use case |
|------|-------|-----------|------------|----------|
| 1 | claude-haiku-4-5-20251001 | $0.80 | $4.00 | Default, streaming |
| 2 | claude-sonnet-4-6 | $3.00 | $15.00 | Escalated (confidence < 0.60) |
| 3 | claude-opus-4-7 | $15.00 | $75.00 | Maximum quality |

Cost per query is logged to `data/routing_logs/YYYY-MM-DD.jsonl`. Daily budget cap enforced before each LLM call.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/query/stream?question=...` | **SSE streaming** — tokens + citations in real-time |
| `POST` | `/query` | Standard JSON query response |
| `POST` | `/compare` | Side-by-side topic comparison |
| `POST` | `/hypotheses` | Testable hypothesis generation |
| `POST` | `/pubmed/search` | Live PubMed article search |
| `GET` | `/graph/stats` | Knowledge graph statistics |
| `POST` | `/graph/subgraph` | Extract subgraph around seed nodes |
| `POST` | `/graph/propagate` | Run causal signal propagation |
| `POST` | `/graph/interventions` | Rank upstream intervention targets |
| `GET` | `/metrics` | Cost + pipeline health |
| `GET` | `/health` | Service health + retrieval status |
| `POST/GET` | `/dossiers/*` | Research dossier CRUD |
| `POST` | `/dmi/disease-report` | Structured mechanism report (domain = runtime param) |
| `POST` | `/dmi/target-risk` | Target risk scoring (domain = runtime param) |

---

## Development

> **macOS venv note**: the shell alias `python` may resolve to system Python 3.9
> even inside an activated virtualenv. Always use `venv/bin/python` and
> `venv/bin/uvicorn` explicitly, or run `scripts/setup_dev.sh` which handles
> this automatically.

```bash
# One-shot setup (creates venv, installs deps, copies .env.example → .env)
bash scripts/setup_dev.sh

# Backend (from asclepius/backend/)
cp .env.example .env          # fill in ANTHROPIC_API_KEY etc.
venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app

# Tests
venv/bin/pytest tests/test_retrieval.py -v

# Frontend
cd asclepius/frontend
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL if needed
npm install
npm run dev
```

---

## Deployment

- **Backend**: Railway, `nixpacks.toml` at repo root  
- **Frontend**: Vercel, `vercel.json` in `frontend/`
- Cold start note: sentence-transformers downloads `all-MiniLM-L6-v2` (~90MB) on first deploy. Subsequent starts use Railway's volume cache.
