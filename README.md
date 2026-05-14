# Asclepius Research Labs

> A domain-agnostic scientific research intelligence platform combining proposition-level hybrid retrieval, causal graph reasoning, and confidence-gated multi-tier inference routing.

---

## Overview

Scientific literature synthesis is bottlenecked by two compounding problems: retrieval systems that treat documents as monolithic units lose precision at query time, and general-purpose language models hallucinate when their training distribution diverges from specialized scientific corpora. Asclepius addresses both by decomposing documents into atomic, self-contained propositions before indexing, fusing lexical and semantic retrieval with rank-based fusion, and routing each query through a cost-tiered inference hierarchy that escalates only when a confidence heuristic signals insufficient response quality.

The platform is domain-agnostic by design. Domain context (`vertical`) is a runtime string parameter — the retrieval pipeline and causal graph operate identically across immunology, oncology, neuroscience, or any scientific field. The primary built-in knowledge base covers immunological signaling (JAK-STAT, NF-κB, TNF pathways, cytokine networks), with architecture designed to accommodate any structured dataset.

---

## System Architecture

### Retrieval and Reasoning Pipeline

```
                  ┌─────────────────────────────────────────────────────────┐
  Query           │                   Hybrid Retrieval                       │
  ──────────────► │  BM25 (BM25Okapi)  ──────────────────────┐              │
                  │  Dense (FAISS/all-MiniLM-L6-v2)  ─────────┤  RRF k=60   │
                  │                                            └──────────── │──► CrossEncoder
                  └─────────────────────────────────────────────────────────┘    reranker
                                                                                      │
                                                                               top-8 propositions
                                                                                      │
                                              ┌───────────────────────────────────────┘
                                              │
                                              ▼
                                   Structured KB search
                           (cytokines · pathways · diseases · therapeutics)
                                              │
                                              ▼
                               Causal graph propagation
                             (signed edges · decay=0.85 · 1-hop subgraph)
                                              │
                                              ▼
                              ┌───────────────────────────┐
                              │    Inference Router        │
                              │  Tier I → Tier II → Tier III
                              │  (escalates if conf < 0.60)│
                              └───────────────────────────┘
                                              │
                              ┌───────────────┴──────────────┐
                              │                              │
                        SSE token stream          Structured JSON response
```

BM25 and FAISS execute in parallel. Their ranked lists are merged via Reciprocal Rank Fusion (rank-based, no score normalization required), then a CrossEncoder reranker produces a final ordered set of eight propositions, which are concatenated as grounded context for the language model.

### Multimodal Path

```
  Base64 image + question
         │
         ▼
  KB context retrieval  ← same hybrid pipeline above
         │
         ▼
  Vision model — image observations extracted,
  then grounded against retrieved propositions
         │
         ▼
  QueryResponse { image_analysis, answer, sources }
```

### Research Engine Modules

The root-level modules expose the full causal reasoning pipeline as a standalone library, independent of the web application:

| Module | Responsibility |
|--------|---------------|
| `data_ingestion/` | Pull interactions from PubMed, KEGG, Reactome, CRISPR screens into a uniform edge list |
| `graph/` | Build a typed knowledge graph (Gene, Protein, Cytokine, Receptor, TranscriptionFactor, CellType, Pathway) with Neo4j or in-memory backends |
| `embeddings/` | Train GNN or Node2Vec embeddings for similarity search and subgraph analysis |
| `causal/` | Probabilistic belief propagation with signed edge weights and configurable decay |
| `optimizer/` | Bayesian UCB active learning strategy to maximize information gain per experiment |

```python
from graph.graph_builder import ImmuneGraphBuilder
from causal.intervention_ranker import InterventionRanker
from optimizer.experiment_suggester import ExperimentSuggester

builder = ImmuneGraphBuilder(use_memory_backend=True)
builder.create_node("IL6", "Cytokine")
builder.create_node("STAT3", "TranscriptionFactor")
builder.create_node("JAK1", "Protein")
builder.create_edge("IL6", "JAK1", "activates", confidence_score=0.90)
builder.create_edge("JAK1", "STAT3", "activates", confidence_score=0.92)

edge_list = [(e["source"], e["target"], e["type"], e) for e in builder.get_edge_list()]
ranker = InterventionRanker()
rankings = ranker.rank_interventions("STAT3", edge_list, top_k=5)

suggester = ExperimentSuggester()
suggestions = suggester.suggest_experiments("STAT3", edge_list, budget=3)
```

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 15 (App Router) · TypeScript · TailwindCSS · Framer Motion | SSE-native streaming; App Router enables server-side proxy without a separate API gateway |
| Backend | FastAPI · Pydantic v2 · Uvicorn · asyncio | Async-first; Pydantic enforces strict IO contracts at every boundary |
| Retrieval | BM25Okapi + FAISS IndexFlatIP + RRF (k=60) + CrossEncoder | Hybrid outperforms either alone on biomedical corpora; see design rationale below |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | 90MB; strong performance on STS benchmarks; fits Railway free tier |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Listwise reranking without label data requirement |
| Chunking | PyMuPDF (text/image blocks) + proposition extraction + vision captioning | Proposition-level precision; per-figure captions indexed as first-class propositions |
| Inference Routing | 3-tier hierarchy with heuristic confidence estimation | Cost-aware; escalates only when necessary |
| Observability | structlog JSON + Prometheus counters/histograms + JSONL cost audit | Full auditability of spend and retrieval quality |
| Persistence | SQLAlchemy async ORM + aiosqlite | Non-blocking IO; drops to PostgreSQL via a single URL swap |
| Graph | In-memory causal graph with signed edge weights | Neo4j-compatible schema; switchable via backend setting |
| Deployment | Railway (backend) · Vercel (frontend) | Zero-configuration monorepo deployment |

---

## Design Rationale

### Hybrid BM25 + FAISS Retrieval

Biomedical queries exhibit two failure modes. BM25 excels at exact token matching for gene symbols (JAK1, STAT3, IL-6), drug names, and pathway identifiers — rare vocabulary where dense embedding models have limited discriminative power. Dense retrieval with all-MiniLM-L6-v2 captures semantic paraphrase: "how does tofacitinib work" retrieves JAK inhibitor documents without lexical overlap. Neither retriever alone achieves adequate recall across this vocabulary distribution. BEIR benchmark results consistently show hybrid approaches outperforming either retriever in isolation on biomedical corpora.

### RRF for Score Fusion

Learned score fusion requires labelled query-document relevance pairs that are unavailable for this corpus. Score interpolation between BM25 and FAISS is unreliable because their score distributions are structurally incompatible — BM25 TF-IDF scores scale with corpus statistics; cosine similarity is bounded to [−1, 1]. Reciprocal Rank Fusion operates on ordinal ranks rather than scores (`1/(k + rank)`), making it insensitive to score distribution shape. The k=60 parameter follows Cormack et al. (SIGIR 2009) and provides stable fusion without any tuning data.

### Proposition-Level Chunking

Sliding-window chunking bisects at fixed token boundaries regardless of semantic structure — a single abstract can assert three independent facts, which a window conflates into one noisy retrieval unit. Proposition extraction decomposes each passage into atomic, self-contained declarative sentences. Each indexed unit expresses exactly one verifiable claim, improving both retrieval precision (smaller chunks reduce noise) and citation quality (each citation maps to one specific assertion). A sliding-window fallback activates when no inference API key is configured.

### Confidence-Gated Inference Routing

The routing layer solves two problems simultaneously: (1) query-level cost optimization — trivially answerable queries should not incur Tier III inference costs; (2) quality assurance — a Tier I answer that fails a quality threshold should not be returned to the user. Implementation uses a two-stage approach: a regex complexity classifier pre-selects the starting tier based on query structural features; a heuristic confidence estimator post-processes each response — responses below 150 characters receive a score of 0.30, responses containing uncertainty phrases receive 0.40, otherwise 0.85. Confidence below 0.60 triggers escalation. A daily budget cap is enforced before every inference call, with all spend logged to JSONL for audit.

| Tier | Model | Input $/M | Output $/M | Trigger |
|------|-------|-----------|------------|---------|
| I | Rapid inference | $0.80 | $4.00 | Default; streaming |
| II | Balanced inference | $3.00 | $15.00 | Confidence < 0.60 |
| III | Deep inference | $15.00 | $75.00 | Confidence < 0.60 after Tier II |

---

## Repository Structure

```
asclepius-research-labs/
│
├── asclepius/                          # Production web application
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py                 # FastAPI app + background retrieval warm-up
│   │   │   ├── api/routes.py           # 15+ endpoints + SSE streaming
│   │   │   ├── core/config.py          # Pydantic-settings: API keys, budget, DB URL
│   │   │   ├── retrieval/
│   │   │   │   ├── bm25_index.py       #   BM25Okapi lexical index (in-memory)
│   │   │   │   ├── dense_index.py      #   FAISS IndexFlatIP + sentence-transformers
│   │   │   │   ├── fusion.py           #   Reciprocal Rank Fusion (k=60)
│   │   │   │   ├── reranker.py         #   CrossEncoder ms-marco-MiniLM-L-6-v2
│   │   │   │   └── pipeline.py         #   Unified hybrid pipeline singleton
│   │   │   ├── chunking/
│   │   │   │   ├── document_parser.py  #   PyMuPDF → text blocks + image blocks
│   │   │   │   ├── image_captioner.py  #   Vision model → figure caption propositions
│   │   │   │   ├── proposition_extractor.py  # Atomic claim extraction
│   │   │   │   └── sliding_window.py   #   Word-level chunker (no-API fallback)
│   │   │   ├── routing/
│   │   │   │   ├── classifier.py       #   Query complexity → starting tier
│   │   │   │   ├── cost_tracker.py     #   JSONL audit log + daily budget enforcement
│   │   │   │   └── router.py           #   3-tier routing + streaming with metadata sentinel
│   │   │   ├── observability/
│   │   │   │   ├── metrics.py          #   Prometheus counters + histograms
│   │   │   │   └── logging.py          #   structlog JSON structured output
│   │   │   ├── db/
│   │   │   │   ├── models.py           #   SQLAlchemy async ORM (Proposition, Paper)
│   │   │   │   └── store.py            #   Async SQLite CRUD (aiosqlite)
│   │   │   ├── dmi/                    #   Disease/Mechanism Intelligence module
│   │   │   │   ├── disease_report.py   #     Structured mechanism reports
│   │   │   │   └── target_risk.py      #     Target druggability + risk scoring
│   │   │   ├── services/
│   │   │   │   ├── retrieval_service.py   # Pipeline singleton, KB + dataset indexing
│   │   │   │   ├── llm_service.py         # Orchestration: retrieval → routing → response
│   │   │   │   ├── query_engine.py        # Structured keyword search across datasets
│   │   │   │   ├── pubmed_service.py      # NCBI E-utilities + interaction extraction
│   │   │   │   ├── graph_service.py       # Causal propagation + intervention ranking
│   │   │   │   ├── comparative_service.py # Multi-dimensional topic comparison
│   │   │   │   ├── hypothesis_service.py  # 5-strategy testable hypothesis generation
│   │   │   │   ├── dossier_service.py     # Persistent research workspace CRUD
│   │   │   │   └── ingestion_service.py   # PDF ingestion orchestration
│   │   │   ├── data/
│   │   │   │   ├── knowledge_base.py      # Curated KB entries (domain-configurable)
│   │   │   │   └── ingestion.py           # JSON dataset loaders
│   │   │   └── models/schema.py           # Pydantic schemas for all request/response types
│   │   ├── tests/test_retrieval.py        # 33 unit + integration tests
│   │   ├── scripts/setup_dev.sh           # One-shot venv + deps + .env bootstrap
│   │   └── requirements.txt
│   └── frontend/
│       ├── app/
│       │   ├── page.tsx                   # Main UI: 5 modes, SSE streaming, citation panel
│       │   └── api/                       # Next.js API proxy routes → FastAPI
│       ├── components/
│       │   ├── StreamingResponse.tsx      # Token-by-token streaming display + markdown
│       │   ├── CitationPanel.tsx          # Sliding citation panel (retrieved propositions)
│       │   ├── ResponseCard.tsx           # Structured reasoning: entities, pathways, targets
│       │   ├── CompareCard.tsx            # Side-by-side topic comparison
│       │   ├── HypothesisCard.tsx         # Testable hypothesis cards with experimental designs
│       │   ├── DiseaseReportCard.tsx      # DMI mechanism report display
│       │   └── TargetRiskCard.tsx         # Target risk assessment display
│       ├── hooks/useStreamingQuery.ts     # SSE hook: AbortController + event parsing
│       └── lib/
│           ├── api.ts                     # Typed API client (domain-agnostic field names)
│           ├── backend.ts                 # URL resolver + server-side proxy helpers
│           └── dmi-api.ts                 # DMI endpoint client (domain as free-text string)
│
├── data_ingestion/                    # Public data loaders
│   ├── pubmed_parser.py               #   PubMed abstract fetch and interaction extraction
│   ├── pathway_loader.py              #   KEGG and Reactome pathway loading
│   ├── perturbation_loader.py         #   CRISPR / cytokine perturbation data
│   └── entity_normalizer.py           #   HGNC / UniProt ID normalization
│
├── graph/                             # Knowledge graph construction
│   ├── schema.py                      #   Node and edge type definitions
│   ├── graph_builder.py               #   Neo4j or in-memory backend (switchable)
│   └── graph_queries.py               #   Graph traversal and relationship queries
│
├── embeddings/                        # Representation learning
│   ├── train_gnn.py                   #   Message-passing GNN (NumPy)
│   ├── node2vec_baseline.py           #   Node2Vec baseline
│   └── inference.py                   #   Similarity search and subgraph aggregation
│
├── causal/                            # Causal reasoning
│   ├── propagation.py                 #   Probabilistic belief propagation (decay=0.85)
│   ├── intervention_ranker.py         #   Upstream node ranking by predicted impact
│   └── scoring_utils.py               #   Score normalization utilities
│
├── optimizer/                         # Experiment suggestion
│   ├── active_learning.py             #   Upper-confidence-bound selection
│   └── experiment_suggester.py        #   End-to-end experiment orchestration
│
├── api/app.py                         # Flask REST API (research engine)
├── docs/                              # Strategy and planning documents
├── notebooks/immune_demo.ipynb        # Interactive pipeline walkthrough
├── nixpacks.toml                      # Railway build configuration
└── requirements.txt                   # Research engine dependencies
```

---

## API Reference

### Web Application (FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/query/stream?question=...` | **SSE streaming** — tokens + citations delivered in real-time |
| `POST` | `/query` | Standard structured JSON response |
| `POST` | `/query/images` | Multimodal — base64 image + question, KB-grounded visual analysis |
| `POST` | `/ingest/document` | PDF upload — text extraction + proposition chunking + figure captioning + index rebuild |
| `POST` | `/compare` | Multi-dimensional side-by-side topic comparison |
| `POST` | `/hypotheses` | Testable hypothesis generation (5 strategies with experimental designs) |
| `POST` | `/pubmed/search` | Live PubMed search + molecular interaction extraction |
| `GET` | `/graph/stats` | Knowledge graph summary statistics |
| `POST` | `/graph/subgraph` | Extract 1-hop subgraph around seed nodes |
| `GET` | `/graph/hubs` | Highest-degree nodes in the graph |
| `POST` | `/graph/propagate` | Causal signal propagation (signed edges, configurable decay) |
| `POST` | `/graph/interventions` | Rank upstream intervention candidates by predicted phenotypic impact |
| `POST` | `/dmi/disease-report` | Structured mechanism report (domain = runtime parameter) |
| `POST` | `/dmi/target-risk` | Target druggability and risk scoring (domain = runtime parameter) |
| `GET` | `/metrics` | Cost tracking + pipeline health (Prometheus exposition format) |
| `GET` | `/health` | Service health + retrieval index status |
| `POST/GET/PUT/DELETE` | `/dossiers/*` | Research dossier CRUD |

#### SSE Event Schema (`GET /query/stream`)

```
start:     {"type": "start", "question": "..."}
citations: {"type": "citations", "data": [{text, score, rerank_score, type, pmid, source}, ...]}
token:     {"type": "token", "text": "..."}
done:      {"type": "done", "model": "...", "cost": 0.00042, "sources": [...]}
error:     {"type": "error", "message": "..."}
```

Citations are emitted before the first token — the frontend renders the citation panel while the answer streams.

#### Domain Configuration

`domain` (API field: `vertical`) is a free-text runtime string. No redeployment is required to switch domains.

```json
{ "disease_name": "Alzheimer's disease", "vertical": "neuroscience" }
{ "disease_name": "Non-small cell lung cancer", "target_name": "EGFR", "vertical": "oncology" }
{ "question": "How does tau aggregation drive neurodegeneration?" }
```

Built-in prompt templates: `immunology`, `oncology`, `neuroscience`. Any other value resolves to a general scientific extraction prompt.

### Research Engine (Flask)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/graph/nodes` | List all graph nodes |
| `GET` | `/graph/edges` | List all graph edges |
| `POST` | `/graph/node` | Create a node |
| `POST` | `/graph/edge` | Create a typed, signed edge |
| `GET` | `/graph/neighbours/<id>` | Node neighbourhood traversal |
| `POST` | `/causal/propagate` | Belief propagation from seed scores |
| `POST` | `/causal/rank_interventions` | Rank upstream candidates by impact |
| `POST` | `/optimizer/suggest` | Bayesian UCB experiment suggestion |
| `POST` | `/normalize` | Entity name normalization (HGNC / UniProt) |
| `GET` | `/health` | Health check |

---

## Environment Variables

### Backend (`asclepius/backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | — | Primary inference key — 3-tier routing |
| `DAILY_BUDGET_USD` | | `10.00` | Hard spend cap enforced before each inference call |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./data/asclepius.db` | Async proposition store; swap URL for PostgreSQL |
| `NCBI_API_KEY` | | — | Raises PubMed rate limit from 3 to 10 req/s |
| `OPENAI_API_KEY` | | — | Fallback inference provider if primary key is absent |
| `CORS_ORIGINS` | | `["*"]` | Allowed CORS origins |

### Frontend (`asclepius/frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `API_URL` | ✅ | Railway backend base URL (server-side proxy) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | | Clerk auth (optional) |
| `CLERK_SECRET_KEY` | | Clerk auth (optional) |

---

## Local Development

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

Swagger UI available at `http://localhost:8000/docs`. Frontend at `http://localhost:3000`.

> **macOS note:** `python` may resolve to system Python 3.9 even inside an activated virtualenv. Use `venv/bin/python` and `venv/bin/uvicorn` explicitly, or rely on `scripts/setup_dev.sh`.

---

## Deployment

### Vercel (frontend)

Set *Root Directory* = `asclepius/frontend`. Vercel auto-detects Next.js 15, applies App Router conventions, and ignores the repo-root `vercel.json`.

### Railway (backend)

Set *Root Directory* = `asclepius/backend`. Railway auto-detects Python via `requirements.txt` + `.python-version`, resolves the Procfile, and starts Uvicorn.

Cold-start note: `all-MiniLM-L6-v2` (~90 MB) is downloaded on first deploy. Subsequent starts use Railway's volume cache, reducing cold start from ~30s to ~5s.

---

## Completed Capabilities

- Domain-agnostic platform with domain as a runtime string parameter
- Hybrid BM25 + FAISS retrieval with RRF fusion and CrossEncoder reranking
- Proposition-level document chunking with vision-based figure captioning
- 3-tier confidence-gated inference routing with daily budget enforcement
- SSE streaming with citations emitted before the first response token
- Prometheus observability and structlog JSON logging
- Async SQLite proposition store (aiosqlite + SQLAlchemy ORM)
- Disease/Mechanism Intelligence (DMI) module — mechanism reports and target risk scoring
- Multimodal image query grounded against retrieved KB propositions
- PDF ingestion pipeline: text extraction → proposition chunking → figure captioning → index rebuild
- Comparative analysis across multiple indexed dimensions
- 5-strategy testable hypothesis generation with experimental designs
- Disease dossier system — persistent research workspaces with CRUD
- Live PubMed integration with molecular interaction extraction
- Causal knowledge graph with signal propagation and intervention ranking
- Session persistence via browser localStorage with multi-session sidebar

---

## License

Copyright © 2026 Peter Graham. All rights reserved.

This software is proprietary. Reproduction, distribution, or use without explicit written permission from the author is prohibited.
