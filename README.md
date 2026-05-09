# Asclepius Research Labs

> **Hybrid retrieval + causal reasoning for scientific research.**

Domain-agnostic scientific research intelligence platform. The domain is a runtime parameter — query immunology, oncology, neuroscience, or any field. Goes beyond generic AI chat by combining hybrid BM25 + dense retrieval with proposition-level chunking, causal graph propagation, intervention ranking, and a 4-tier LLM routing layer with confidence-gated escalation.

Immunology (JAK-STAT, NF-κB, TNF pathways) is the primary built-in dataset. The retrieval and reasoning pipeline is field-neutral.

---

## What It Does

- **Hybrid retrieval** — BM25 + FAISS dense retrieval, fused via Reciprocal Rank Fusion and reranked by a CrossEncoder; returns top-8 propositions per query
- **Proposition-level chunking** — Claude Haiku decomposes source documents into atomic, self-contained claims; each retrieved unit expresses one verifiable fact
- **Live PubMed integration** — Real-time search via NCBI E-utilities with molecular interaction extraction from abstracts
- **Causal signal propagation** — Computes downstream effects of inhibiting a target over the graph, with signed edge weights and configurable decay (0.85)
- **Intervention ranking** — Ranks upstream therapeutic targets by predicted impact on a disease phenotype
- **4-tier LLM routing** — Queries start at Haiku; escalate to Sonnet or Opus when confidence < 0.60; daily budget cap enforced before every LLM call
- **SSE streaming** — Real-time token delivery with citations alongside the stream
- **Domain-agnostic DMI module** — Structured mechanism reports and target risk scoring; domain passed as a free-text string at query time
- **Multimodal image query** — Upload any scientific image (gel, flow cytometry, pathway diagram, microscopy) with a question; Claude Sonnet vision analyzes it grounded in retrieved KB propositions, returning a separate `image_analysis` field
- **PDF document ingestion** — Upload any PDF; text is proposition-chunked, figures are captioned by Haiku vision, and all content is indexed into the BM25+FAISS pipeline
- **Comparative analysis & hypothesis generation** — Side-by-side topic comparison; 5-strategy testable hypothesis generation with experimental designs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 · TypeScript · TailwindCSS · Framer Motion · Clerk auth (optional) |
| Backend | FastAPI · Pydantic · Uvicorn · asyncio |
| Retrieval | BM25 (rank-bm25 BM25Okapi) + FAISS IndexFlatIP (sentence-transformers/all-MiniLM-L6-v2) · RRF k=60 · CrossEncoder reranker (ms-marco-MiniLM-L-6-v2) |
| Chunking | Proposition extraction via Claude Haiku · PyMuPDF (fitz) PDF parser · Haiku vision figure captioning · sliding-window fallback |
| Multimodal | Claude Sonnet vision (claude-sonnet-4-5) — base64 image input grounded against KB propositions |
| LLM Routing | Anthropic (Haiku → Sonnet → Opus, confidence-gated escalation) · OpenAI fallback · daily budget cap |
| Observability | structlog JSON · Prometheus counters/histograms · JSONL cost audit log |
| Data Sources | Live PubMed (NCBI E-utilities) · curated JSON datasets · SQLite async proposition store (aiosqlite) |
| Graph | Causal belief propagation (decay=0.85) · intervention ranking · knowledge graph (Neo4j or in-memory) |
| Deployment | Railway (backend) · Vercel (frontend) |

---

## Architecture

### Retrieval + Reasoning Pipeline

```
Query ├─ BM25 (rank-bm25)            ─┐
      └─ Dense (FAISS / all-MiniLM)  ─┴─→ RRF (k=60) → CrossEncoder reranker → top-8 propositions
                                           ↓
                                Structured KB search (cytokines, pathways, diseases, therapeutics)
                                           ↓
                          Causal graph propagation (decay=0.85, 1-hop subgraph)
                                           ↓
                  LLM Router: Haiku → Sonnet → Opus (escalates if confidence < 0.60)
                                           ↓
                                SSE stream / structured JSON response
```

BM25 and FAISS run in parallel. Their ranked lists are merged by RRF (rank-based, no score comparison, no training data), then a CrossEncoder reranker produces the final top-8 propositions passed to the LLM as context.

**Multimodal path** (`POST /query/images`):

```
Base64 image + question
         ↓
  KB context retrieval (same hybrid pipeline)
         ↓
  Claude Sonnet vision — image observations extracted, then grounded against retrieved propositions
         ↓
  QueryResponse { image_analysis: "...", answer: "...", sources: [...] }
```

> This is upload-and-analyze, not image retrieval — no CLIP/ColPali image index. Image similarity search is on the roadmap.

The retrieval pipeline indexes ~1,000+ documents at startup (warm-up in a background thread; ~30s on cold start with ML model downloads).

### Research Engine Modules

The root-level modules provide programmatic access to the full causal reasoning pipeline:

1. **Data Ingestion** — Pull interactions from PubMed, KEGG, Reactome, and CRISPR screens into a uniform edge list
2. **Graph Construction** — Build a typed knowledge graph (Gene, Protein, Cytokine, Receptor, TranscriptionFactor, CellType, Pathway) with Neo4j or in-memory backends
3. **Representation Learning** — Train GNN or Node2Vec embeddings for similarity search and subgraph analysis
4. **Causal Propagation** — Probabilistic belief propagation with signed edge weights and configurable decay
5. **Intervention Ranking** — Score and rank upstream nodes by predicted impact on a target phenotype
6. **Experiment Suggestion** — Bayesian UCB strategy to maximise information gain per experiment

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

## Design Decisions

### Hybrid BM25 + FAISS retrieval

Biomedical queries split into two failure modes. BM25 reliably surfaces exact token matches for gene symbols (JAK1, STAT3, IL-6), drug names, and pathway identifiers where embedding models have limited discriminative power on rare biomedical vocabulary. Dense retrieval with all-MiniLM-L6-v2 captures semantic paraphrase — "how does tofacitinib work" matches documents about JAK inhibitors without lexical overlap. Neither alone is sufficient. BEIR benchmark results consistently show hybrid retrieval outperforming either on biomedical corpora.

### RRF (k=60) for fusion

Learned fusion requires labelled query-document relevance pairs that don't exist for this corpus. Score interpolation between BM25 and FAISS is problematic because their score distributions aren't comparable — BM25 scales with corpus statistics, cosine similarity is bounded [0,1]. RRF operates on ranks rather than scores (`1/(k + rank)`), making it insensitive to score distribution differences and requiring no training data. k=60 is the standard value from Cormack et al. 2009 (SIGIR).

### Proposition-level chunking

Sliding-window chunking cuts at fixed token boundaries regardless of semantic structure — a single abstract can assert three independent facts that a window conflates into one noisy chunk. Proposition extraction (via Claude Haiku) decomposes each passage into atomic, self-contained declarative sentences. Each retrieval unit expresses exactly one verifiable claim, improving both retrieval precision and citation quality. Haiku is used for cost efficiency; extraction is bounded at 5 chunks per document. Sliding window remains as fallback when no Anthropic key is set.

### 4-tier routing with confidence-gated escalation

Always routing to Opus at $15/M input tokens is unviable at any meaningful query volume. The system uses two-stage routing: (1) a lightweight regex complexity classifier pre-selects the starting tier — simple/medium queries start at Haiku, complex queries (≥2 complexity pattern hits or >20 words) start at Sonnet; (2) after each response, a heuristic confidence estimator checks response length (<150 chars → 0.30) and uncertainty phrases against a 0.60 threshold — below threshold, the query escalates to the next tier. Cost scales with actual query complexity. The daily budget cap (`DAILY_BUDGET_USD`, default $10) is enforced before each LLM call, with all spend logged to JSONL.

| Tier | Model | Input $/M | Output $/M | Use case |
|------|-------|-----------|------------|----------|
| 1 | claude-haiku-4-5-20251001 | $0.80 | $4.00 | Default, streaming |
| 2 | claude-sonnet-4-6 | $3.00 | $15.00 | Escalated (confidence < 0.60) |
| 3 | claude-opus-4-7 | $15.00 | $75.00 | Maximum quality |

---

## Repository Structure

```
asclepius-research-labs/
│
├── asclepius/                      # Production web application
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py                         # FastAPI app + retrieval warm-up on startup
│   │   │   ├── api/routes.py                   # 15+ endpoints + GET /query/stream (SSE)
│   │   │   ├── core/config.py                  # Settings: ANTHROPIC_API_KEY, DAILY_BUDGET_USD, DATABASE_URL
│   │   │   ├── retrieval/
│   │   │   │   ├── bm25_index.py               #   BM25Okapi lexical index
│   │   │   │   ├── dense_index.py              #   FAISS IndexFlatIP + sentence-transformers
│   │   │   │   ├── fusion.py                   #   Reciprocal Rank Fusion (k=60)
│   │   │   │   ├── reranker.py                 #   CrossEncoder ms-marco-MiniLM-L-6-v2
│   │   │   │   └── pipeline.py                 #   Unified hybrid pipeline
│   │   │   ├── chunking/
│   │   │   │   ├── document_parser.py          #   PyMuPDF PDF → text blocks + image blocks
│   │   │   │   ├── image_captioner.py          #   Haiku vision → figure caption propositions
│   │   │   │   ├── proposition_extractor.py    #   Haiku text → atomic claims
│   │   │   │   └── sliding_window.py           #   Word-level chunker (fallback)
│   │   │   ├── routing/
│   │   │   │   ├── classifier.py               #   Query complexity → starting tier
│   │   │   │   ├── cost_tracker.py             #   JSONL audit log + daily budget cap
│   │   │   │   └── router.py                   #   4-tier Anthropic routing + streaming
│   │   │   ├── observability/
│   │   │   │   ├── metrics.py                  #   Prometheus counters/histograms
│   │   │   │   └── logging.py                  #   structlog JSON output
│   │   │   ├── db/
│   │   │   │   ├── models.py                   #   SQLAlchemy async ORM (Proposition, Paper)
│   │   │   │   └── store.py                    #   Async SQLite CRUD (aiosqlite)
│   │   │   ├── dmi/                            #   Mechanism Intelligence (domain = runtime param)
│   │   │   │   ├── disease_report.py           #     Structured mechanism reports
│   │   │   │   └── target_risk.py              #     Target druggability + risk scoring
│   │   │   ├── services/
│   │   │   │   ├── retrieval_service.py        #   Pipeline singleton, KB + dataset indexing
│   │   │   │   ├── llm_service.py              #   Anthropic routing → OpenAI fallback → local
│   │   │   │   ├── query_engine.py             #   Structured keyword search across datasets
│   │   │   │   ├── pubmed_service.py           #   Live NCBI E-utilities search
│   │   │   │   ├── graph_service.py            #   Causal propagation + intervention ranking
│   │   │   │   ├── comparative_service.py      #   Topic vs topic comparison
│   │   │   │   ├── hypothesis_service.py       #   Testable hypothesis generation
│   │   │   │   ├── dossier_service.py          #   Persistent research workspaces
│   │   │   │   └── ingestion_service.py        #   PDF ingestion orchestration (parse → chunk → caption → index)
│   │   │   ├── data/
│   │   │   │   ├── knowledge_base.py           #   Curated KB entries (domain-specific data)
│   │   │   │   └── ingestion.py                #   JSON dataset loaders
│   │   │   └── models/schema.py                #   Pydantic request/response schemas
│   │   ├── tests/test_retrieval.py             # 33 tests: BM25, RRF, chunking, routing, costs
│   │   ├── scripts/setup_dev.sh               # One-shot venv + deps + .env setup
│   │   └── requirements.txt
│   └── frontend/
│       ├── app/
│       │   ├── page.tsx                        # Main UI: streaming mode, citation panel
│       │   └── api/                            # Next.js API proxy routes → FastAPI
│       ├── components/
│       │   ├── StreamingResponse.tsx           # Token-by-token display + markdown
│       │   ├── CitationPanel.tsx               # Sliding citation panel (retrieved propositions)
│       │   ├── ResponseCard.tsx                # Structured reasoning display
│       │   ├── CompareCard.tsx                 # Side-by-side comparison
│       │   ├── HypothesisCard.tsx              # Testable hypothesis cards
│       │   ├── DiseaseReportCard.tsx           # DMI mechanism report
│       │   └── TargetRiskCard.tsx              # Target risk assessment
│       └── lib/
│           ├── api.ts                          # Typed API client (domain-agnostic fields)
│           ├── backend.ts                      # URL resolver + proxy helpers
│           └── dmi-api.ts                      # DMI API (domain is a free-text string)
│
├── data_ingestion/                 # Public data loaders
│   ├── pubmed_parser.py            #   PubMed abstract search & extraction
│   ├── pathway_loader.py           #   KEGG & Reactome pathway loading
│   ├── perturbation_loader.py      #   CRISPR / cytokine perturbation data
│   └── entity_normalizer.py        #   HGNC / UniProt ID normalisation
│
├── graph/                          # Knowledge graph construction
│   ├── schema.py                   #   Node & edge type definitions
│   ├── graph_builder.py            #   Neo4j or in-memory backend
│   └── graph_queries.py            #   Query & explore relationships
│
├── embeddings/                     # Representation learning
│   ├── train_gnn.py                #   Message-passing GNN (NumPy)
│   ├── node2vec_baseline.py        #   Node2Vec baseline
│   └── inference.py                #   Similarity & subgraph aggregation
│
├── causal/                         # Causal reasoning
│   ├── propagation.py              #   Probabilistic belief propagation (decay=0.85)
│   ├── intervention_ranker.py      #   Rank nodes for intervention impact
│   └── scoring_utils.py            #   Normalisation helpers
│
├── optimizer/                      # Experiment suggestion
│   ├── active_learning.py          #   Upper-confidence-bound selection
│   └── experiment_suggester.py     #   End-to-end experiment orchestration
│
├── api/app.py                      # Flask REST API (research engine)
├── docs/                           # Strategy & planning documents
├── notebooks/immune_demo.ipynb     # Interactive demo walkthrough
├── nixpacks.toml                   # Railway build config (points to asclepius/backend)
└── requirements.txt                # Research engine dependencies
```

---

## Local Development

```bash
# One-shot setup (creates venv, installs deps, copies .env.example → .env)
cd asclepius/backend
bash scripts/setup_dev.sh

# Backend
cp .env.example .env   # fill in ANTHROPIC_API_KEY at minimum
venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app

# Tests
venv/bin/pytest tests/test_retrieval.py -v

# Frontend (separate terminal)
cd asclepius/frontend
cp .env.local.example .env.local
npm install && npm run dev
```

Backend API docs: `http://localhost:8000/docs` — Frontend: `http://localhost:3000`

> **macOS venv note:** `python` may resolve to system Python 3.9 even inside an activated venv. Use `venv/bin/python` and `venv/bin/uvicorn` explicitly, or rely on `scripts/setup_dev.sh`.

---

## Environment Variables

### Backend (`asclepius/backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | Primary LLM key — Haiku/Sonnet/Opus routing |
| `DAILY_BUDGET_USD` | | `10.00` | Hard daily spend cap (enforced before each LLM call) |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./data/asclepius.db` | Async SQLite for proposition store |
| `NCBI_API_KEY` | | — | Boosts PubMed rate limits |
| `OPENAI_API_KEY` | | — | Fallback LLM if no Anthropic key is set |
| `CORS_ORIGINS` | | `["*"]` | Allowed CORS origins |

### Frontend (`asclepius/frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `API_URL` | ✅ | Railway backend URL (server-side proxy) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | | Clerk auth (optional) |
| `CLERK_SECRET_KEY` | | Clerk auth (optional) |

---

## API Reference

### Web Application Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/query/stream?question=...` | **SSE streaming** — tokens + citations in real-time |
| `POST` | `/query` | Standard structured JSON response |
| `POST` | `/query/images` | **Multimodal** — base64 image + question, KB-grounded vision analysis |
| `POST` | `/ingest/document` | Upload a PDF — extracts text + figures, captions via Haiku vision, indexes into BM25+FAISS |
| `POST` | `/compare` | Side-by-side topic comparison |
| `POST` | `/hypotheses` | Testable hypothesis generation (5 strategies) |
| `POST` | `/pubmed/search` | Live PubMed article search + interaction extraction |
| `GET` | `/graph/stats` | Knowledge graph summary statistics |
| `POST` | `/graph/subgraph` | Extract subgraph around seed nodes |
| `GET` | `/graph/hubs` | Most connected nodes in the graph |
| `POST` | `/graph/propagate` | Causal signal propagation |
| `POST` | `/graph/interventions` | Rank upstream intervention targets |
| `POST` | `/dmi/disease-report` | Structured mechanism report (domain = runtime param) |
| `POST` | `/dmi/target-risk` | Target risk scoring (domain = runtime param) |
| `GET` | `/metrics` | Cost + pipeline health (Prometheus) |
| `GET` | `/health` | Service health + retrieval status |
| `POST/GET` | `/dossiers/*` | Research dossier CRUD |

#### `POST /ingest/document` — `DocumentIngestResponse`

```json
{
  "filename": "smith_2024_jak_stat.pdf",
  "propositions_added": 142,
  "figures_captioned": 7,
  "pages": 18,
  "message": "Document ingested successfully"
}
```

### Domain Configuration

`domain` (API field: `vertical`) is a free-text runtime parameter:

```json
{ "disease_name": "Alzheimer's disease", "vertical": "neuroscience" }
{ "disease_name": "Non-small cell lung cancer", "target_name": "EGFR", "vertical": "oncology" }
{ "question": "How does tau aggregation drive neurodegeneration?" }
```

Built-in prompt templates: `immunology`, `oncology`, `neuroscience`. Any other value uses a general scientific extraction prompt.

### Research Engine — Flask API

| Method | Path | Description |
|---|---|---|
| `GET` | `/graph/nodes` | List all graph nodes |
| `GET` | `/graph/edges` | List all graph edges |
| `POST` | `/graph/node` | Create a node |
| `POST` | `/graph/edge` | Create an edge |
| `GET` | `/graph/neighbours/<id>` | Get node neighbours |
| `POST` | `/causal/propagate` | Run causal signal propagation |
| `POST` | `/causal/rank_interventions` | Rank upstream intervention targets |
| `POST` | `/optimizer/suggest` | Suggest experiments (Bayesian UCB) |
| `POST` | `/normalize` | Normalise entity names (HGNC/UniProt) |
| `GET` | `/health` | Health check |

---

## Deployment

Monorepo: FastAPI backend in `asclepius/backend/`, Next.js 15 frontend in `asclepius/frontend/`. Both platforms support deploying a subdirectory via a dashboard *Root Directory* setting or root-level config files — pick one approach and don't mix them.

### Vercel (frontend)

- **Recommended:** Set Project Settings → *Root Directory* = `asclepius/frontend`. Vercel auto-detects Next.js, reads the in-folder `vercel.json`, and ignores the repo-root one.
- **Alternate:** Leave Root Directory as `./`. Vercel reads the root `vercel.json`, which `cd`s into `asclepius/frontend` for install/build.

> The legacy `builds` API in `vercel.json` does not support Next.js 13+ App Router — both configs above use the modern framework integration.

### Railway (backend)

- **Recommended:** Set Service Settings → *Root Directory* = `asclepius/backend`. Railway auto-detects Python via the in-folder `requirements.txt` + `.python-version`.
- **Alternate:** Leave Root Directory as `/`. Railway reads the repo-root `nixpacks.toml` + `railway.json`, which install and start from `asclepius/backend`.

Cold-start note: sentence-transformers downloads `all-MiniLM-L6-v2` (~90 MB) on first deploy. Subsequent starts use Railway's volume cache.

---

## Roadmap

### Completed

- [x] Domain-agnostic scientific research platform (domain as runtime parameter)
- [x] Hybrid BM25 + FAISS retrieval pipeline with RRF fusion and CrossEncoder reranking
- [x] Proposition-level chunking with Claude Haiku extraction
- [x] 4-tier Anthropic LLM routing with confidence-gated escalation and daily budget cap
- [x] SSE streaming endpoint with real-time token delivery
- [x] Prometheus observability + structlog JSON logging
- [x] Async SQLite proposition store (aiosqlite)
- [x] DMI (Disease/Mechanism Intelligence) module with domain-agnostic runtime parameter
- [x] Multimodal image query (Claude Sonnet vision grounded against KB propositions)
- [x] Production web application with multi-mode research interface
- [x] Curated immunological knowledge bases (diseases, pathways, cytokines, therapeutics)
- [x] Cloud deployment configuration (Railway + Vercel)
- [x] Live PubMed integration (NCBI E-utilities)
- [x] Knowledge graph wired into query pipeline (subgraph extraction, hub analysis, path finding)
- [x] Causal signal propagation integrated into query responses
- [x] Intervention ranking endpoint
- [x] Comparative analysis mode (topic vs topic across all dimensions)
- [x] Hypothesis generator mode (5 strategies with experimental designs)
- [x] Disease dossier system (persistent research workspaces)
- [x] Sidebar with session persistence (localStorage)
- [x] PDF document ingestion with PyMuPDF text extraction + Haiku vision figure captioning

### In Progress / Next

- [ ] Interactive graph visualization (Cytoscape.js or D3-force)
- [ ] bioRxiv/medRxiv preprint search
- [ ] User accounts with persistent cloud workspaces (replace localStorage)
- [ ] CSV/TSV upload for user data (gene lists, expression data, CRISPR hits)
- [ ] User data overlay on knowledge graph
- [ ] Export capabilities (PowerPoint, PDF, CSV)

### Future

- [ ] Image retrieval pipeline — CLIP or ColPali embeddings over figure corpora for similarity search over scientific images
- [ ] Oncology immune network expansion
- [ ] spaCy + BioBERT NLP pipeline for automated literature extraction
- [ ] Team collaboration features (shared workspaces, comments)
- [ ] API access for programmatic integration
- [ ] Multi-tenant workspaces with enterprise SSO
- [ ] User feedback loop for answer quality improvement

---

## License

Copyright (c) 2026 Peter Graham. All rights reserved.

This software is proprietary and may not be copied, modified, distributed, or used without explicit written permission from the author.
