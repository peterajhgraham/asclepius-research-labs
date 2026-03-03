# Asclepius Research Labs — Web Application

Production full-stack AI web app for autoimmune disease research. Multi-mode research interface with structured immune reasoning, live PubMed integration, comparative disease analysis, hypothesis generation, and persistent research workspaces.

## Stack

| Layer    | Technology                         |
|----------|------------------------------------|
| Backend  | Python · FastAPI · Pydantic · Uvicorn · Requests |
| Frontend | Next.js 15 (App Router) · TypeScript · TailwindCSS · Axios |

---

## Project Structure

```
autoimmune_intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI application factory, CORS middleware
│   │   ├── api/
│   │   │   └── routes.py                   # 15+ endpoints (query, compare, hypotheses, PubMed, graph, dossiers)
│   │   ├── core/
│   │   │   └── config.py                   # BaseSettings environment configuration
│   │   ├── services/
│   │   │   ├── llm_service.py              # LLM synthesis with PubMed + graph context integration
│   │   │   ├── query_engine.py             # Multi-dataset keyword search engine
│   │   │   ├── pubmed_service.py           # Live NCBI E-utilities (esearch, efetch, interaction extraction)
│   │   │   ├── graph_service.py            # Knowledge graph operations, causal propagation, intervention ranking
│   │   │   ├── comparative_service.py      # Disease vs disease comparison across all dimensions
│   │   │   ├── hypothesis_service.py       # 5-strategy hypothesis generator with experimental designs
│   │   │   ├── dossier_service.py          # In-memory research workspace persistence
│   │   │   └── logger_service.py           # Query logging for analytics
│   │   ├── models/
│   │   │   └── schema.py                   # Pydantic schemas for all endpoints
│   │   └── data/
│   │       ├── ingestion.py                # Dataset loading + in-memory store
│   │       └── datasets/                   # Curated JSON knowledge bases
│   │           ├── immune_knowledge_base.json
│   │           ├── cytokine_network.json
│   │           ├── immune_pathways.json
│   │           ├── disease_gene_associations.json
│   │           └── therapeutic_targets.json
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx                      # Root layout with optional Clerk auth
    │   ├── page.tsx                        # Main page: sidebar, mode switcher, query interface
    │   ├── globals.css                     # TailwindCSS base styles
    │   └── api/                            # Next.js API proxy routes
    │       ├── query/route.ts
    │       ├── compare/route.ts
    │       ├── hypotheses/route.ts
    │       ├── pubmed/search/route.ts
    │       ├── diseases/route.ts
    │       └── dossiers/route.ts
    ├── components/
    │   ├── ResponseCard.tsx                # Structured reasoning display with causal network viz
    │   ├── CompareCard.tsx                 # Side-by-side disease comparison with overlap analysis
    │   ├── HypothesisCard.tsx              # Expandable hypothesis cards with experimental designs
    │   ├── PubMedPanel.tsx                 # Live PubMed article display with links
    │   └── AuthHeader.tsx                  # Optional Clerk auth header
    ├── lib/
    │   ├── api.ts                          # Typed API client for all endpoints
    │   └── backend.ts                      # Backend proxy utility
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── next.config.js
    └── .env.local.example
```

---

## Quick Start

### 1. Backend

```bash
cd autoimmune_intelligence/backend

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Configure environment variables
cp .env.example .env            # edit OPENAI_API_KEY etc.

# Start the development server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd autoimmune_intelligence/frontend

# Install dependencies
npm install

# Configure the API URL
cp .env.local.example .env.local   # edit NEXT_PUBLIC_API_URL if needed

# Start the development server
npm run dev
```

The UI will be available at `http://localhost:3000`.

---

## Features

### Query Modes

| Mode | Description |
|------|-------------|
| **Analyze** | Structured immune reasoning with disease context, pathways, cells, cytokines, targets, genes, and open hypotheses |
| **Compare** | Side-by-side comparison of two autoimmune diseases across all dimensions with similarity scoring |
| **Hypothesize** | Generate testable research hypotheses with experimental designs, biomarkers, and confounders |

### Additional Capabilities

- **Live PubMed** — Toggle to include real-time PubMed results via NCBI E-utilities
- **Knowledge Graph** — In-memory immune signaling graph built from all datasets at startup, with causal propagation scores in query responses
- **Session Sidebar** — Save and revisit research sessions (localStorage-backed)
- **Disease Dossiers** — Accumulate structured insights across queries with notes

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/query` | POST | Structured immune reasoning query |
| `/compare` | POST | Disease vs disease comparison |
| `/hypotheses` | POST | Hypothesis generation |
| `/pubmed/search` | POST | Live PubMed search |
| `/diseases` | GET | List available diseases |
| `/graph/stats` | GET | Graph statistics |
| `/graph/subgraph` | POST | Extract subgraph |
| `/graph/hubs` | GET | Top hub nodes |
| `/graph/propagate` | POST | Causal propagation |
| `/graph/interventions` | POST | Intervention ranking |
| `/dossiers` | GET/POST | List/create dossiers |
| `/dossiers/{id}` | GET/DELETE | Get/delete dossier |
| `/dossiers/{id}/entries` | POST | Add entry to dossier |
| `/dossiers/{id}/insights` | GET | Aggregated dossier insights |
| `/health` | GET | Health check |

---

## Environment Variables

### Backend (`.env`)

| Variable        | Default                   | Description                     |
|-----------------|---------------------------|---------------------------------|
| `APP_NAME`      | `Asclepius Research Labs` | Service display name            |
| `OPENAI_API_KEY`| *(empty)*                 | OpenAI API key for LLM synthesis |
| `LLM_MODEL`     | `gpt-4o`                  | Model identifier                |
| `CORS_ORIGINS`  | `["*"]`                   | Allowed CORS origins            |
| `LOG_LEVEL`     | `INFO`                    | Python logging level            |

### Frontend (`.env.local`)

| Variable               | Default                   | Description          |
|------------------------|---------------------------|----------------------|
| `NEXT_PUBLIC_API_URL`  | `http://localhost:8000`   | Backend API base URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | *(empty)* | Clerk auth key (optional) |
