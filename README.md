# Asclepius Research Labs

> **AI-powered immune reasoning for autoimmune disease research**

Asclepian Research Labs is an intelligent research copilot that helps immunologists, drug discovery teams, and biotech researchers reason about immune signaling networks. Ask questions in natural language about disease mechanisms, cytokine pathways, or therapeutic targets — and get structured, source-backed answers grounded in curated immunological data.

---

## What It Does

- **Natural-language queries** — Ask about disease mechanisms, cytokine networks, immune pathways, or drug targets and receive structured reasoning with cited sources
- **Structured causal reasoning** — Trace signal propagation through immune networks (NF-κB, JAK-STAT, TNF) and rank intervention targets by predicted impact
- **Experiment suggestion** — Bayesian active learning recommends the highest-value perturbation experiments given your research objective and budget
- **Knowledge graph** — Built from PubMed, KEGG, Reactome, and CRISPR perturbation datasets with standardised HGNC/UniProt identifiers

---

## Product

The web application provides a chat-style interface backed by a FastAPI reasoning service and curated immunological datasets.

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 · TypeScript · TailwindCSS · Clerk auth |
| Backend | FastAPI · Pydantic · Uvicorn |
| Reasoning Engine | Python · NumPy · Neo4j (optional) |
| Data Sources | PubMed · KEGG · Reactome · CRISPR screens · curated JSON datasets |
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
│   ├── backend/                    #   FastAPI service + LLM integration
│   │   ├── app/
│   │   │   ├── main.py             #     App factory + CORS middleware
│   │   │   ├── api/routes.py       #     POST /query endpoint
│   │   │   ├── core/config.py      #     Environment configuration
│   │   │   ├── models/schema.py    #     Request/response schemas
│   │   │   ├── services/           #     LLM service, query engine, logging
│   │   │   └── data/datasets/      #     Curated JSON knowledge bases
│   │   └── requirements.txt
│   └── frontend/                   #   Next.js chat interface
│       ├── app/                    #     Pages + layout
│       └── components/             #     ResponseCard, AuthHeader
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
├── notebooks/immune_demo.ipynb     # Interactive demo walkthrough
└── requirements.txt                # Research engine dependencies
```

---

## Architecture

### Reasoning Pipeline

```
Query → Dataset Search → LLM Synthesis → Structured Response
                                           ├── answer + sources
                                           ├── key cells & cytokines
                                           ├── pathways involved
                                           ├── therapeutic targets
                                           └── open research questions
```

The backend searches across curated datasets (disease associations, immune pathways, cytokine networks, therapeutic targets) and synthesises answers using an LLM when available, with a capable local fallback when no API key is configured.

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

### Web Application — `POST /query`

```json
// Request
{ "question": "What drives JAK-STAT dysregulation in lupus?" }

// Response
{
  "answer": "Based on current immunological research ...",
  "sources": ["Firestein GS. Nature. 2003;423:356-361."],
  "reasoning": {
    "summary": "...",
    "key_cells": ["Th17", "Treg"],
    "key_cytokines": ["IL-6", "IL-21"],
    "pathways": ["JAK-STAT"],
    "therapeutic_targets": ["Tofacitinib", "Baricitinib"],
    "open_questions": ["..."],
    "genes": ["STAT3", "JAK1"],
    "disease_context": "Systemic Lupus Erythematosus"
  }
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
| `APP_NAME` | `Asclepian Research Labs` | Service display name |
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

- [x] Autoimmune disease focus (NF-κB, JAK-STAT, TNF pathways)
- [x] Production web application with chat interface
- [x] Curated immunological knowledge bases
- [x] LLM-powered answer synthesis with local fallback
- [x] Structured causal reasoning responses
- [x] Cloud deployment configuration (Railway + Vercel)
- [ ] Oncology immune network expansion
- [ ] spaCy + BioBERT NLP pipeline for automated literature extraction
- [ ] Interactive graph visualisation (Cytoscape.js)
- [ ] User feedback loop for answer quality improvement
- [ ] Multi-tenant workspaces with saved research sessions

---

## License

Proprietary. All rights reserved.
