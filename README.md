# Asclepius Research Labs

> **Hybrid retrieval + causal reasoning for scientific research.**

Asclepius Research Labs is a domain-agnostic scientific research intelligence platform. The domain is a runtime parameter — query immunology, oncology, neuroscience, or any scientific field. The system goes beyond generic AI chat by combining hybrid BM25 + dense retrieval with proposition-level chunking, causal graph propagation, intervention ranking, and a 4-tier LLM routing layer with confidence-gated escalation.

Immunology (JAK-STAT, NF-κB, TNF pathways) is the primary built-in dataset. The retrieval and reasoning pipeline is field-neutral.

---

## What It Does

- **Hybrid retrieval** — BM25 (exact-match) + FAISS dense (semantic) retrieval, fused via Reciprocal Rank Fusion and reranked by a CrossEncoder, returning the top-8 most relevant propositions per query
- **Proposition-level chunking** — Claude Haiku decomposes each source document into atomic, self-contained claims; each retrieved unit expresses one verifiable fact
- **Live PubMed integration** — Real-time search via NCBI E-utilities with molecular interaction extraction from abstracts
- **Causal signal propagation** — "If I inhibit Target X, what downstream effects propagate through the network?" Computed over graph structure with signed edge weights and configurable decay (0.85)
- **Intervention ranking** — Systematically rank upstream therapeutic targets by predicted impact on a disease phenotype
- **4-tier LLM routing** — Queries start at Haiku; escalate to Sonnet or Opus when confidence falls below 0.60. Daily budget cap enforced before every LLM call
- **SSE streaming** — Tokens delivered in real-time via Server-Sent Events; citations arrive alongside the stream
- **Domain-agnostic DMI module** — Structured mechanism reports and target risk scoring; domain passed as a free-text string at query time
- **Multimodal image query** — Upload any scientific image (gel, flow cytometry plot, pathway diagram, microscopy) with a research question; Claude Sonnet vision analyzes the image and grounds its interpretation in retrieved KB propositions, returning a separate `image_analysis` field alongside the standard structured answer
- **Comparative analysis & hypothesis generation** — Side-by-side topic comparison across pathways, cytokines, cell types, therapeutics; 5-strategy testable hypothesis generation with experimental designs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 · TypeScript · TailwindCSS · Framer Motion · Clerk auth (optional) |
| Backend | FastAPI · Pydantic · Uvicorn · asyncio |
| Retrieval | BM25 (rank-bm25 BM25Okapi) + FAISS IndexFlatIP (sentence-transformers/all-MiniLM-L6-v2) · RRF k=60 · CrossEncoder reranker (ms-marco-MiniLM-L-6-v2) |
| Chunking | Proposition extraction via Claude Haiku · sliding-window fallback |
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

Both BM25 and FAISS run in parallel at query time. Their ranked lists are merged by RRF (no score comparison, no training data required), then a CrossEncoder reranker rescores the merged set to produce the final top-8 propositions passed to the LLM as context.

**Multimodal path** (image queries via `POST /query/images`):

```
Base64 image + question
         ↓
  KB context retrieval (same hybrid pipeline)
         ↓
  Claude Sonnet vision — image observations extracted first,
  then grounded against retrieved propositions
         ↓
  QueryResponse { image_analysis: "...", answer: "...", sources: [...] }
```

Note: this is upload-and-analyze, not image retrieval. The system does not maintain an image index or perform similarity search over image embeddings (no CLIP, ColPali, or PDF figure extraction). Document parsing (PDF, OCR) is not currently implemented — images must be provided as base64 by the client.

The retrieval pipeline indexes ~1,000+ documents from the configured knowledge base and datasets at startup (warm-up runs in a background thread; ~30s on cold start with ML model downloads).

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

### Hybrid BM25 + FAISS retrieval instead of either alone

Biomedical queries split into two failure modes that each retriever handles differently. BM25 is a term-frequency model — it reliably surfaces documents containing exact token matches for gene symbols (JAK1, STAT3, IL-6), drug names (tofacitinib, baricitinib), and pathway identifiers where the embedding model has limited discriminative power due to sparse training signal on rare biomedical vocabulary. Dense retrieval with all-MiniLM-L6-v2 captures semantic paraphrase — "how does tofacitinib work" matches documents about JAK inhibitors without lexical overlap. Neither retriever alone is sufficient: BM25 misses paraphrase, dense misses rare exact-match entities. BEIR benchmark results consistently show hybrid retrieval outperforming either individually on biomedical corpora. The pipeline runs both in parallel and fuses at the rank level.

### RRF (k=60) for fusion instead of learned score interpolation

Learned fusion (linear score blending, learning-to-rank, late-fusion networks) requires labelled query-document relevance pairs to calibrate weights. No such labelled dataset exists for this retrieval corpus. Score interpolation between BM25 and FAISS cosine similarity is also problematic because the two score distributions are not comparable in magnitude — BM25 scores scale with corpus statistics, cosine similarities are bounded [0,1]. RRF sidesteps both problems by operating on ranks rather than scores: each document contributes `1/(k + rank)` to the fused score, making it insensitive to score distribution differences and requiring no training data. The k=60 constant is the standard value from Cormack et al. 2009 (SIGIR), which showed RRF outperforming learned methods on held-out queries.

### Proposition-level chunking instead of sliding window

Sliding-window chunking splits text at fixed token boundaries regardless of semantic structure, routinely cutting mid-sentence or straddling multiple distinct claims. For biomedical abstracts this is particularly damaging: a single abstract may assert "IL-6 activates JAK1", "JAK1 phosphorylates STAT3", and "STAT3 drives inflammatory gene expression" — three independent, retrievable facts that a sliding window conflates into a single noisy chunk. Proposition extraction (via Claude Haiku) decomposes each passage into atomic, self-contained declarative sentences. The result is that each retrieval unit expresses exactly one verifiable claim, which improves both retrieval precision (each proposition matches a narrower query surface) and citation quality (the cited unit directly supports the claim being cited). Haiku is used for cost efficiency; extraction is bounded at 5 chunks per document. Sliding window remains as a fallback when the Anthropic key is unavailable.

### 4-tier routing with confidence-gated escalation instead of always routing to the best model

Routing every query to Opus at $15/M input tokens is economically unviable at any meaningful query volume. The system uses a two-stage routing strategy: (1) a lightweight regex complexity classifier pre-selects the starting tier — simple and medium queries start at Haiku, complex queries (≥2 complexity pattern hits or >20 words) start at Sonnet, skipping the Haiku round-trip; (2) after each response, a heuristic confidence estimator checks response length (<150 chars → 0.30) and uncertainty phrases ("I don't know", "insufficient information", etc. → 0.40) against a 0.60 threshold — below threshold, the query escalates to the next tier. This means cost scales with actual query complexity rather than applying a flat premium. The daily budget cap (`DAILY_BUDGET_USD`, default $10) provides a hard ceiling enforced before each LLM call, with all spend logged to JSONL for auditability.

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
├── autoimmune_intelligence/        # Production web application
│   │                               # NOTE: legacy folder name — see "Naming Note" below
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
│   │   │   │   ├── proposition_extractor.py    #   Claude Haiku atomic claim extraction
│   │   │   │   └── sliding_window.py           #   Word-level chunker with overlap (fallback)
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
│   │   │   │   └── dossier_service.py          #   Persistent research workspaces
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
├── nixpacks.toml                   # Railway build config (points to autoimmune_intelligence/backend)
└── requirements.txt                # Research engine dependencies
```

### Naming Note

The `autoimmune_intelligence/` folder is a legacy name from when the product was scoped to autoimmune disease only. The system is now fully domain-agnostic — the domain is a runtime parameter and no code assumes immunology. The folder rename is tracked as a separate refactor (it requires updating import paths, deployment config, and git history) and has not been done yet. Contributors should not infer from the folder name that the product is limited to autoimmune disease.

---

## Local Development

```bash
# One-shot setup (creates venv, installs deps, copies .env.example → .env)
cd autoimmune_intelligence/backend
bash scripts/setup_dev.sh

# Backend
cp .env.example .env   # fill in ANTHROPIC_API_KEY at minimum
venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app

# Tests
venv/bin/pytest tests/test_retrieval.py -v

# Frontend (separate terminal)
cd autoimmune_intelligence/frontend
cp .env.local.example .env.local
npm install && npm run dev
```

Backend API docs: `http://localhost:8000/docs` — Frontend: `http://localhost:3000`

> **macOS venv note**: the shell alias `python` may resolve to system Python 3.9 even inside an activated virtualenv. Always use `venv/bin/python` and `venv/bin/uvicorn` explicitly, or rely on `scripts/setup_dev.sh`.

---

## Environment Variables

### Backend (`autoimmune_intelligence/backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | Primary LLM key — Haiku/Sonnet/Opus routing |
| `DAILY_BUDGET_USD` | | `10.00` | Hard daily spend cap (enforced before each LLM call) |
| `DATABASE_URL` | | `sqlite+aiosqlite:///./data/asclepius.db` | Async SQLite for proposition store |
| `NCBI_API_KEY` | | — | Boosts PubMed rate limits |
| `OPENAI_API_KEY` | | — | Fallback LLM if no Anthropic key is set |
| `CORS_ORIGINS` | | `["*"]` | Allowed CORS origins |

### Frontend (`autoimmune_intelligence/frontend/.env.local`)

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

### Domain Configuration

The `domain` (API field: `vertical`) is a free-text runtime parameter:

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

- **Backend** → Railway via `nixpacks.toml` (FastAPI + Uvicorn)
- **Frontend** → Vercel via `vercel.json` in `autoimmune_intelligence/frontend/`
- Cold start note: sentence-transformers downloads `all-MiniLM-L6-v2` (~90MB) on first deploy. Subsequent starts use Railway's volume cache.

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

### In Progress / Next

- [ ] Interactive graph visualization (Cytoscape.js or D3-force)
- [ ] bioRxiv/medRxiv preprint search
- [ ] User accounts with persistent cloud workspaces (replace localStorage)
- [ ] CSV/TSV upload for user data (gene lists, expression data, CRISPR hits)
- [ ] User data overlay on knowledge graph
- [ ] Export capabilities (PowerPoint, PDF, CSV)

### Future

- [ ] Image retrieval pipeline — CLIP or ColPali embeddings over figure corpora, enabling similarity search over scientific images rather than upload-only analysis
- [ ] PDF / document parsing — PyMuPDF or Unstructured figure extraction, feeding extracted images into the multimodal pipeline automatically
- [ ] Oncology immune network expansion
- [ ] spaCy + BioBERT NLP pipeline for automated literature extraction
- [ ] Team collaboration features (shared workspaces, comments)
- [ ] API access for programmatic integration
- [ ] Multi-tenant workspaces with enterprise SSO
- [ ] User feedback loop for answer quality improvement
- [ ] Rename `autoimmune_intelligence/` to a domain-neutral path (import path + deployment config refactor)

---

## License

Proprietary. All rights reserved.
