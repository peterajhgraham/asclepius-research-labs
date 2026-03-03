# Asclepius Research Labs

> **Structure immune complexity into actionable insight.**

Asclepius Research Labs is a structured autoimmune intelligence engine for biotech researchers and translational immunologists. It goes beyond generic AI chat by providing computable immune reasoning — live PubMed integration, knowledge graph traversal, causal signal propagation, intervention ranking, comparative disease analysis, and testable hypothesis generation with experimental designs.

---

## What It Does

- **Structured immune reasoning** — Every query returns a structured breakdown: disease context, dysregulated pathways, key immune cells, cytokines involved, therapeutic targets, genetic risk loci, and open research gaps
- **Live PubMed integration** — Real-time search via NCBI E-utilities with autoimmune-enriched queries, molecular interaction extraction from abstracts
- **Computable knowledge graph** — Traversable immune signaling graph built from curated datasets with confidence-scored edges, subgraph extraction, hub analysis, and path finding
- **Causal signal propagation** — "If I inhibit Target X, what downstream effects propagate through the immune network?" Computed over graph structure, not hallucinated
- **Intervention ranking** — Systematically rank upstream therapeutic targets by predicted impact on a disease phenotype
- **Comparative disease analysis** — Side-by-side comparison of two autoimmune diseases across pathways, cytokines, cell types, genetics, and therapeutics with overlap quantification
- **Hypothesis generator** — Structured, testable research hypotheses with experimental designs, biomarkers, confounders, and confidence levels across 5 strategies (target discovery, drug repurposing, network mechanism, genetic mechanism, combination therapy)
- **Disease dossiers** — Persistent research workspaces that accumulate structured insights across queries, with notes and aggregated analysis

---

## Product

The web application provides a multi-mode research interface backed by a FastAPI reasoning service, curated immunological datasets, and live PubMed data.

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 · TypeScript · TailwindCSS · Clerk auth (optional) |
| Backend | FastAPI · Pydantic · Uvicorn |
| Reasoning Engine | Python · NumPy · Knowledge graph · Causal propagation |
| Data Sources | Live PubMed (NCBI E-utilities) · Curated JSON datasets (diseases, pathways, cytokines, therapeutics) |
| Deployment | Railway (backend) · Vercel (frontend) |

### Try it locally

```bash
# Backend
cd autoimmune_intelligence/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (in a separate terminal)
cd autoimmune_intelligence/frontend
npm install
npm run dev
```

Backend API docs: `http://localhost:8000/docs` — Frontend: `http://localhost:3000`

---

## Repository Structure

```
├── autoimmune_intelligence/        # Production web application
│   ├── backend/                    #   FastAPI service + reasoning pipeline
│   │   ├── app/
│   │   │   ├── main.py             #     App factory + CORS middleware
│   │   │   ├── api/routes.py       #     15+ API endpoints (query, compare, hypotheses, PubMed, graph, dossiers)
│   │   │   ├── core/config.py      #     Environment configuration
│   │   │   ├── models/schema.py    #     Request/response schemas for all endpoints
│   │   │   ├── services/
│   │   │   │   ├── llm_service.py          # LLM synthesis with PubMed + graph context
│   │   │   │   ├── query_engine.py         # Multi-dataset search engine
│   │   │   │   ├── pubmed_service.py       # Live NCBI E-utilities integration
│   │   │   │   ├── graph_service.py        # Knowledge graph operations + causal propagation
│   │   │   │   ├── comparative_service.py  # Disease vs disease analysis
│   │   │   │   ├── hypothesis_service.py   # Testable hypothesis generation
│   │   │   │   ├── dossier_service.py      # Research workspace persistence
│   │   │   │   └── logger_service.py       # Query logging
│   │   │   └── data/datasets/      #     Curated JSON knowledge bases
│   │   └── requirements.txt
│   └── frontend/                   #   Next.js research interface
│       ├── app/                    #     Pages + API proxy routes
│       ├── components/             #     ResponseCard, CompareCard, HypothesisCard, PubMedPanel
│       └── lib/                    #     API client + backend proxy utility
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
│   ├── propagation.py              #   Probabilistic belief propagation
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
└── requirements.txt                # Research engine dependencies
```

---

## Architecture

### Reasoning Pipeline

```
Query → Dataset Search → PubMed Search → Graph Context → LLM Synthesis → Structured Response
                                                                          ├── answer + sources
                                                                          ├── key cells & cytokines
                                                                          ├── pathways involved
                                                                          ├── therapeutic targets
                                                                          ├── causal network impact
                                                                          ├── live PubMed articles
                                                                          └── open research gaps
```

The backend searches across curated datasets (disease associations, immune pathways, cytokine networks, therapeutic targets), queries PubMed in real-time, extracts knowledge graph context with causal propagation scores, and synthesises answers using an LLM when available — with a capable local fallback when no API key is configured.

### Research Engine

The research engine provides programmatic access to the full causal reasoning pipeline:

1. **Data Ingestion** — Pull interactions from PubMed, KEGG, Reactome, and CRISPR screens into a uniform edge list
2. **Graph Construction** — Build a typed knowledge graph (Gene, Protein, Cytokine, Receptor, TranscriptionFactor, CellType, Pathway) with Neo4j or in-memory backends
3. **Representation Learning** — Train GNN or Node2Vec embeddings for similarity search and subgraph analysis
4. **Causal Propagation** — Probabilistic belief propagation with signed edge weights and configurable decay
5. **Intervention Ranking** — Score and rank upstream nodes by predicted impact on a target
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

## API Reference

### Web Application Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/query` | POST | Structured immune reasoning with optional PubMed integration |
| `/compare` | POST | Side-by-side disease comparison |
| `/hypotheses` | POST | Generate testable research hypotheses |
| `/pubmed/search` | POST | Live PubMed search with interaction extraction |
| `/diseases` | GET | List available diseases for comparison |
| `/graph/stats` | GET | Knowledge graph summary statistics |
| `/graph/subgraph` | POST | Extract subgraph around seed nodes |
| `/graph/hubs` | GET | Most connected nodes in the graph |
| `/graph/propagate` | POST | Causal signal propagation |
| `/graph/interventions` | POST | Rank intervention targets |
| `/dossiers` | GET/POST | List or create disease dossiers |
| `/dossiers/{id}` | GET/DELETE | Get or delete a dossier |
| `/dossiers/{id}/entries` | POST | Add query result to dossier |
| `/dossiers/{id}/insights` | GET | Accumulated insights from dossier |
| `/health` | GET | Health check |

### Example: Structured Query

```json
// Request
{
  "question": "What drives JAK-STAT dysregulation in lupus?",
  "include_pubmed": true
}

// Response
{
  "answer": "Based on current immunological research ...",
  "sources": ["Firestein GS. Nature. 2003;423:356-361.", "PMID:38291045"],
  "reasoning": {
    "summary": "...",
    "key_cells": ["Th17", "Treg", "B cells"],
    "key_cytokines": ["IL-6", "IL-21", "IFN-α"],
    "pathways": ["JAK-STAT signaling"],
    "therapeutic_targets": ["Tofacitinib", "Baricitinib"],
    "open_questions": ["..."],
    "genes": ["STAT3", "JAK1", "STAT4"],
    "disease_context": "Systemic Lupus Erythematosus"
  },
  "pubmed_articles": [...],
  "graph_context": { "nodes": [...], "edges": [...], "causal_downstream": [...] }
}
```

### Research Engine — Flask API

| Endpoint | Method | Description |
|---|---|---|
| `/graph/nodes` | GET | List all graph nodes |
| `/graph/edges` | GET | List all graph edges |
| `/graph/node` | POST | Create a node |
| `/graph/edge` | POST | Create an edge |
| `/graph/neighbours/<id>` | GET | Get node neighbours |
| `/causal/propagate` | POST | Run causal signal propagation |
| `/causal/rank_interventions` | POST | Rank upstream intervention targets |
| `/optimizer/suggest` | POST | Suggest experiments |
| `/normalize` | POST | Normalise entity names (HGNC/UniProt) |
| `/health` | GET | Health check |

---

## Environment Variables

### Backend (`autoimmune_intelligence/backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Asclepius Research Labs` | Service display name |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key for LLM synthesis |
| `LLM_MODEL` | `gpt-4o` | Model identifier |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |

### Frontend (`autoimmune_intelligence/frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | *(empty)* | Clerk auth key (optional) |

---

## Deployment

The repository is pre-configured for cloud deployment:

- **Backend** → Railway via `nixpacks.toml` (FastAPI + Uvicorn)
- **Frontend** → Vercel via `vercel.json` (Next.js)

---

## Roadmap

### Completed

- [x] Autoimmune disease focus (NF-κB, JAK-STAT, TNF pathways)
- [x] Production web application with multi-mode research interface
- [x] Curated immunological knowledge bases (16 KB entries, 4 JSON datasets)
- [x] LLM-powered answer synthesis with local fallback
- [x] Structured immune reasoning responses (cells, cytokines, pathways, targets, genes, hypotheses)
- [x] Cloud deployment configuration (Railway + Vercel)
- [x] Live PubMed integration (NCBI E-utilities with autoimmune query enrichment)
- [x] Knowledge graph wired into query pipeline (subgraph extraction, hub analysis, path finding)
- [x] Causal signal propagation integrated into query responses
- [x] Intervention ranking endpoint
- [x] Comparative disease analysis mode (disease vs disease across all dimensions)
- [x] Hypothesis generator mode (5 strategies with experimental designs)
- [x] Disease dossier system (persistent research workspaces)
- [x] Sidebar with session persistence (localStorage)
- [x] Rod of Asclepius branding

### In Progress / Next

- [ ] Interactive graph visualization (Cytoscape.js or D3-force)
- [ ] Semantic search using vector embeddings (replace keyword matching)
- [ ] bioRxiv/medRxiv preprint search
- [ ] User accounts with persistent cloud workspaces (replace localStorage)
- [ ] CSV/TSV upload for user data (gene lists, expression data, CRISPR hits)
- [ ] User data overlay on knowledge graph
- [ ] Export capabilities (PowerPoint, PDF, CSV)

### Future

- [ ] Oncology immune network expansion
- [ ] spaCy + BioBERT NLP pipeline for automated literature extraction
- [ ] Team collaboration features (shared workspaces, comments)
- [ ] API access for programmatic integration
- [ ] Multi-tenant workspaces with enterprise SSO
- [ ] User feedback loop for answer quality improvement

---

## License

Proprietary. All rights reserved.
