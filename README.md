# Asclepius Research Labs

> A domain-agnostic scientific research intelligence platform combining **truly multimodal** proposition-level retrieval (text + figures + tables fused in a shared CLIP space), causal graph reasoning, a tool-using research agent, figure-grounded verification, and confidence-gated multi-tier inference routing.

---

## Overview

Scientific literature synthesis is bottlenecked by three compounding problems: retrieval systems that treat documents as monolithic units lose precision at query time; text-only retrievers strip away the figures, tables, and quantitative panels where most of a paper's signal actually lives; and general-purpose language models hallucinate when their training distribution diverges from specialized scientific corpora.

Asclepius addresses all three. Documents are decomposed into atomic propositions before indexing — for figures and tables, propositions carry a content-addressed `image_hash` and a CLIP image embedding so a textual query can directly retrieve the relevant *visual* evidence, not just a captioned paraphrase. Lexical (BM25), semantic (MiniLM), and cross-modal (CLIP) retrieval are fused via Reciprocal Rank Fusion, then cross-encoder reranked. The single-shot RAG path stays fast for simple questions; an opt-in **tool-using research agent** handles multi-hop comparisons and orchestrates the retriever, PubMed, and the causal graph as native tools. An opt-in **figure-grounded verification** pass re-examines the actual cited images with Claude vision to mark unsupported quantitative claims `[unverified]` before the answer reaches the user.

The platform is domain-agnostic by design. Domain context (`vertical`) is a runtime string parameter — the retrieval pipeline and causal graph operate identically across immunology, oncology, neuroscience, or any scientific field. The primary built-in knowledge base covers immunological signaling (JAK-STAT, NF-κB, TNF pathways, cytokine networks), with architecture designed to accommodate any structured dataset.

---

## System Architecture

### Multimodal Retrieval & Reasoning Pipeline

```
                  ┌────────────────────────────────────────────────────────────────────┐
                  │                       Three-Leg Hybrid Retrieval                    │
  Query  ───────► │  BM25 (BM25Okapi) ───────────────────────────────────┐             │
  (+ probe image) │  Dense (FAISS / all-MiniLM-L6-v2) ────────────────────┤             │
                  │  CLIP text→image (FAISS / ViT-B/32, shared space) ────┤  RRF k=60   │
                  │  CLIP image→image  (only when probe image supplied) ──┤             │
                  │                                                       └─────────────│──► CrossEncoder
                  └────────────────────────────────────────────────────────────────────┘    reranker
                                                                                                 │
                                                                                          top-8 propositions
                                                                                  (text · figure · table)
                                                                                                 │
                                              ┌──────────────────────────────────────────────────┘
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
                              │  Retrieved figures + tables│
                              │  attached as vision blocks │
                              └───────────────────────────┘
                                              │
                              ┌───────────────┼────────────────────────────┐
                              ▼               ▼                            ▼
                        SSE token stream    Structured JSON       Figure-grounded
                                            response               verification
                                                                   (opt-in `verify=True`)
```

BM25, dense MiniLM, and the CLIP cross-modal leg execute in parallel. Their ranked lists are merged via Reciprocal Rank Fusion (rank-based, no score normalization required), then a CrossEncoder reranker produces the final ordered set of eight propositions. When the top results include figures or tables, their PNG rasters are attached to the LLM call as native Anthropic vision content blocks — so the model can ground quantitative claims in actual image pixels, not just captions.

### Ingestion Pipeline (PDF → multimodal propositions)

```
  PDF bytes
       │
       ├── PyMuPDF (reading-order text blocks)
       │      └── layout-aware sentence-bounded chunker (~1800 chars, page-bounded)
       │            └── Haiku proposition extractor → atomic text propositions
       │
       ├── PyMuPDF (embedded images, SHA-256 deduped, min 120×120 / 4KB)
       │      └── content-addressed disk store (./data/images/<shard>/<hash>.<ext>)
       │      └── CLIP ViT-B/32 image embedding (persisted as float32 blob)
       │      └── Haiku-vision caption → atomic figure propositions
       │
       └── pdfplumber (table detector → markdown + raw rows + bbox)
              └── PyMuPDF region raster (2× zoom PNG, for vision context)
              └── CLIP image embedding of the raster
              └── markdown indexed as text proposition; raster carried for the LLM

  → SQLite (propositions table) with content_type, image_hash, clip_embedding,
    table_markdown, bbox_json — backward-compatible ALTER TABLE migrations.
```

### Research Agent Path (opt-in via `mode="research"`)

```
  Question
     │
     ▼
  Planner (Sonnet 4.6 + Anthropic tool-use)
     │
     ├── tool: search_knowledge_base   ── hybrid retriever (text + figure + table)
     ├── tool: search_pubmed           ── NCBI E-utilities (live literature)
     ├── tool: causal_propagate         ── signed-edge propagation on the KG
     ├── tool: rank_interventions       ── upstream target ranking
     ├── tool: compare_topics           ── side-by-side topic comparison
     │
     ▼  (max 5 iterations, 90s wall-clock budget, daily cost cap enforced)
  final_answer tool call ──► SSE stream of planner_step / tool_call / tool_result / final events
                                                │
                                                ▼
                                  Optional figure-grounded verification
```

The agent is gated behind `mode="research"` so the latency (3–10× single-shot) and cost (5–20×) only apply when callers explicitly opt in. The retriever is invoked *as a tool* — agents go on top of the retriever, not instead of it; replacing strong hybrid retrieval with LLM-driven search is strictly worse on every published benchmark.

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
| Retrieval | BM25Okapi + FAISS IndexFlatIP (×2 — dense + CLIP) + RRF (k=60) + CrossEncoder | Three-leg hybrid (lexical + semantic text + cross-modal) outperforms any subset on biomedical corpora; see design rationale below |
| Text embeddings | sentence-transformers/all-MiniLM-L6-v2 | 90 MB; strong STS performance; fits Railway free tier |
| Multimodal embeddings | sentence-transformers/clip-ViT-B-32 | 600 MB; CPU-only inference; embeds text and images into a shared 512-d space — no external embedding API at index time |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Listwise reranking without label data requirement |
| PDF parsing | PyMuPDF (text + embedded images, reading-order sorted, SHA-256 deduped) + pdfplumber (tables → markdown + bbox) + region rasterization | Three parallel streams; image / table propositions are first-class retrieval citizens |
| Chunking | Layout-aware sentence-bounded packer (~1800 chars, page-bounded, 1-sentence overlap) + Haiku proposition extraction | 5-10× fewer chunks than the prior sliding window with no recall loss; chunks never straddle pages or sections |
| Image storage | Content-addressed disk store (`./data/images/<shard>/<sha256>.<ext>`) | Dedupes recurring figures; images stream over HTTP with `Cache-Control: immutable`; DB stays slim |
| Research agent | Anthropic native tool-use loop (Sonnet 4.6 planner) | Multi-hop decomposition, PubMed + retriever + graph + comparator as tools; bounded by iterations + wall-clock + budget |
| Verification | Claude Sonnet vision against cited figures | Re-examines the actual image pixels, marks unsupported quantitative claims `[unverified]` |
| Inference Routing | 3-tier hierarchy with heuristic confidence estimation | Cost-aware; escalates only when necessary |
| Observability | structlog JSON + Prometheus counters/histograms + JSONL cost audit | Full auditability of spend and retrieval quality |
| Persistence | SQLAlchemy async ORM + aiosqlite | Non-blocking IO; drops to PostgreSQL via a single URL swap |
| Graph | In-memory causal graph with signed edge weights | Neo4j-compatible schema; switchable via backend setting |
| Deployment | Railway (backend) · Vercel (frontend) | Zero-configuration monorepo deployment |

---

## Design Rationale

### Three-Leg Hybrid Retrieval (BM25 + Dense + CLIP)

Biomedical queries exhibit three failure modes. BM25 excels at exact token matching for gene symbols (JAK1, STAT3, IL-6), drug names, and pathway identifiers — rare vocabulary where dense embedding models have limited discriminative power. Dense retrieval with all-MiniLM-L6-v2 captures semantic paraphrase: "how does tofacitinib work" retrieves JAK inhibitor documents without lexical overlap. **Neither leg can retrieve a figure that the captioner missed, paraphrased badly, or that contains a quantitative pattern (a Kaplan-Meier curve, a dose-response, a heatmap) the caption never named.** The CLIP leg closes that gap: image and short-text representations land in a shared 512-d space, so a textual query like "Kaplan-Meier survival curve for arm B at 24 months" directly retrieves the matching figure regardless of caption phrasing. The three legs are complementary, not redundant — BEIR-style ablations consistently show hybrid > any subset on biomedical corpora, and the cross-modal addition is what makes the system *truly* multimodal rather than text-only with optional image side-loading.

### Why CLIP (and not a hosted multimodal embedder)

We index with `sentence-transformers/clip-ViT-B-32` rather than a hosted API (Voyage multimodal-3, OpenAI image embeddings) for three reasons: no external dependency at ingestion time (Railway-friendly), zero per-call cost at index or query time, and deterministic embeddings across runs (important for reproducible retrieval benchmarks). CLIP embeddings are precomputed at ingestion and persisted as float32 blobs in SQLite so restart never re-encodes; the CLIP model itself loads lazily on first query.

### RRF for Score Fusion

Learned score fusion requires labelled query-document relevance pairs that are unavailable for this corpus. Score interpolation between BM25, dense cosine similarity, and CLIP cosine similarity is unreliable because their score distributions are structurally incompatible — BM25 TF-IDF scores scale with corpus statistics; cosine similarities are bounded to [−1, 1] but with different practical ranges per modality. Reciprocal Rank Fusion operates on ordinal ranks rather than scores (`1/(k + rank)`), making it insensitive to score distribution shape. The k=60 parameter follows Cormack et al. (SIGIR 2009) and provides stable fusion without any tuning data, even as we added a third (and conditionally fourth — image→image) leg.

### Layout-Aware Chunking

The earlier sliding-window chunker bisected at fixed word boundaries regardless of semantic or page structure — a single abstract could assert three independent facts that a window conflated into one noisy retrieval unit, and chunks straddling unrelated sections poisoned both BM25 term overlap and dense embeddings. The current layout chunker groups text blocks by page, sentence-splits each page, then greedy-packs into ~1800-character chunks with a 1-sentence overlap. This produces 5–10× fewer chunks per document with the same recall, never cuts mid-sentence, and never glues two sections together. A Haiku proposition extractor then decomposes each chunk into atomic declarative claims; a sliding-window fallback activates when no inference API key is configured.

### Tool-Using Research Agent (opt-in)

Single-shot RAG is the right answer for simple factual questions — fast, cheap, deterministic, easy to debug. It is structurally inadequate for multi-hop questions ("compare X vs Y across efficacy, safety, biomarkers" is three retrievals), for queries that need to route between live PubMed and the indexed corpus, and for cases where the first retrieval misses key terms and needs reformulation. The research agent (gated behind `mode="research"`) handles those: a Sonnet 4.6 planner iteratively calls `search_knowledge_base`, `search_pubmed`, `causal_propagate`, `rank_interventions`, or `compare_topics` until it has enough evidence to emit `final_answer`. The loop is bounded by 5 iterations, a 90-second wall-clock, and the same daily budget cap as the single-shot path. Crucially, the retriever is invoked *as a tool* — agents go on top of the strong hybrid retriever, not in place of it.

### Figure-Grounded Verification (opt-in)

Even with grounded retrieval, the LLM can confidently fabricate a quantitative claim that the cited figure does not actually show — the captioner can paraphrase a panel inaccurately, or the model can interpolate beyond what the image supports. The verification pass (gated behind `verify=True`) addresses this by re-fetching every figure / table raster cited in the retrieval results and asking Sonnet vision to mark each claim in the generated answer as supported, unclear, or unsupported. Unsupported claims are tagged inline as `[unverified]` before the answer reaches the user. This is the single highest-leverage trust pass for a scientific RAG tool, and only applies when the caller opts in — neither latency nor cost is paid on the 80% of queries that don't need it.

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
│   │   │   │   ├── clip_index.py       #   CLIP ViT-B/32 text↔image FAISS index
│   │   │   │   ├── fusion.py           #   Reciprocal Rank Fusion (k=60)
│   │   │   │   ├── reranker.py         #   CrossEncoder ms-marco-MiniLM-L-6-v2
│   │   │   │   └── pipeline.py         #   3-leg hybrid pipeline (BM25 + dense + CLIP)
│   │   │   ├── chunking/
│   │   │   │   ├── document_parser.py  #   PyMuPDF text + image blocks (dedup, reading-order)
│   │   │   │   ├── table_extractor.py  #   pdfplumber tables → markdown + bbox + raster
│   │   │   │   ├── layout_chunker.py   #   Sentence-bounded, page-aware chunk packer
│   │   │   │   ├── image_captioner.py  #   Haiku vision → caption + CLIP embedding
│   │   │   │   ├── proposition_extractor.py  # Atomic claim extraction
│   │   │   │   └── sliding_window.py   #   Word-level chunker (no-API fallback)
│   │   │   ├── storage/
│   │   │   │   └── image_store.py      #   Content-addressed disk store (SHA-256 sharded)
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
│   │   │   │   ├── retrieval_service.py   # Pipeline singleton, KB + dataset + DB indexing
│   │   │   │   ├── llm_service.py         # Orchestration: retrieval → routing → response
│   │   │   │   ├── agent_service.py       # Tool-using research agent (mode="research")
│   │   │   │   ├── verification_service.py# Figure-grounded answer verification (verify=True)
│   │   │   │   ├── query_engine.py        # Structured keyword search across datasets
│   │   │   │   ├── pubmed_service.py      # NCBI E-utilities + interaction extraction
│   │   │   │   ├── graph_service.py       # Causal propagation + intervention ranking
│   │   │   │   ├── comparative_service.py # Multi-dimensional topic comparison
│   │   │   │   ├── hypothesis_service.py  # 5-strategy testable hypothesis generation
│   │   │   │   ├── dossier_service.py     # Persistent research workspace CRUD
│   │   │   │   └── ingestion_service.py   # PDF → text+figures+tables, multimodal indexing
│   │   │   ├── data/
│   │   │   │   ├── knowledge_base.py      # Curated KB entries (domain-configurable)
│   │   │   │   └── ingestion.py           # JSON dataset loaders
│   │   │   └── models/schema.py           # Pydantic schemas for all request/response types
│   │   ├── tests/test_retrieval.py        # 33 unit + integration tests
│   │   ├── scripts/setup_dev.sh           # One-shot venv + deps + .env bootstrap
│   │   └── requirements.txt
│   └── frontend/
│       ├── app/
│       │   ├── page.tsx                   # Main UI: 6 modes, dual SSE (stream + agent), citation panel
│       │   └── api/                       # Next.js API proxy routes → FastAPI
│       │       ├── query/stream/          #   SSE proxy for /query/stream
│       │       ├── query/agent/           #   SSE proxy for /query/agent (research agent)
│       │       └── images/[hash]/         #   Proxy for /images/{hash} figure streaming
│       ├── components/
│       │   ├── StreamingResponse.tsx      # Token-by-token streaming display + markdown
│       │   ├── AgentTrace.tsx             # Live planner-step / tool-call / final / verification trace
│       │   ├── CitationPanel.tsx          # Sliding citation panel — renders figure thumbs + table previews
│       │   ├── ResponseCard.tsx           # Structured reasoning: entities, pathways, targets
│       │   ├── CompareCard.tsx            # Side-by-side topic comparison
│       │   ├── HypothesisCard.tsx         # Testable hypothesis cards with experimental designs
│       │   ├── DiseaseReportCard.tsx      # DMI mechanism report display
│       │   └── TargetRiskCard.tsx         # Target risk assessment display
│       ├── hooks/
│       │   ├── useStreamingQuery.ts       # SSE hook for /query/stream
│       │   └── useAgentStream.ts          # SSE hook for /query/agent
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
| `GET` | `/query/stream?question=...` | **SSE streaming** — tokens + citations (text · figures · tables) delivered in real-time |
| `POST` | `/query` | Standard structured JSON response. `mode="research"` dispatches the tool-using agent; `verify=true` runs figure-grounded verification |
| `GET` | `/query/agent?question=...&verify=...` | **SSE streaming** — tool-using research agent: emits `planner_step`, `tool_call`, `tool_result`, `final`, `verification`, `done` events |
| `POST` | `/query/images` | Multimodal — base64 probe image + question; CLIP image→image retrieval surfaces similar archival figures, all attached to vision call |
| `POST` | `/ingest/document` | PDF upload — text + figures (CLIP-embedded, disk-stored) + tables (pdfplumber, markdown + raster), all indexed for retrieval |
| `GET` | `/images/{image_hash}` | Stream a stored figure or table raster by SHA-256 hash. Used by the frontend to render retrieved figures inline |
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
citations: {"type": "citations", "data": [
              {text, score, rerank_score, type, pmid, source,
               content_type ("text"|"image"|"table"),
               image_hash, image_url, page, table_markdown}, ...]}
token:     {"type": "token", "text": "..."}
done:      {"type": "done", "model": "...", "cost": 0.00042, "sources": [...]}
error:     {"type": "error", "message": "..."}
```

Citations are emitted before the first token — the frontend renders the citation panel (with figure thumbnails and table previews inline) while the answer streams.

#### SSE Event Schema (`GET /query/agent`)

```
start:        {"type": "start", "question": "..."}
planner_step: {"type": "planner_step", "iteration": N, "thinking": "...", "tool_calls": ["..."]}
tool_call:    {"type": "tool_call", "iteration": N, "tool": "...", "args": {...}}
tool_result:  {"type": "tool_result", "iteration": N, "tool": "...", "result_preview": "..."}
final:        {"type": "final", "answer": "...", "image_hashes": ["..."]}
verification: {"type": "verification", "verdict": "...", "confidence": 0.x, "notes": "...",
               "revised_answer": "...", "images_inspected": N}
done:         {"type": "done", "iterations": N, "model": "...", "cost_usd": 0.x}
error:        {"type": "error", "message": "..."}
```

The agent emits live reasoning progress so the UI can show planner steps and tool dispatches rather than a 15-second silent spinner.

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

Cold-start note: `all-MiniLM-L6-v2` (~90 MB) and `clip-ViT-B-32` (~600 MB) are downloaded on first deploy. The CLIP model loads lazily on the first query that exercises the multimodal leg, so initial startup is unchanged. Subsequent starts use Railway's volume cache.

The image store lives at `./data/images/` (sharded by 2-char SHA-256 prefix). Mount a persistent Railway volume there if you want figures to survive container restarts.

---

## Frontend Modes & Toggles

The composer in `app/page.tsx` exposes six modes via `ModeSwitcher`:

| Mode | Path | Notes |
|------|------|-------|
| **Mechanism Report** | `POST /dmi/disease-report` | Structured DMI mechanism report (domain = runtime string) |
| **Target Risk** | `POST /dmi/target-risk` | Druggability + clinical/genetic risk scoring |
| **Analyze** | `GET /query/stream` (SSE) | Single-shot RAG — fast, token-streaming, citations + figure thumbnails appear before the first token |
| **Research Agent** | `GET /query/agent` (SSE) | Tool-using planner. The `AgentTrace` component shows live planner steps, tool dispatches (`search_knowledge_base`, `search_pubmed`, `causal_propagate`, `rank_interventions`, `compare_topics`), and tool result previews — so the user sees reasoning happening rather than a silent spinner |
| **Compare** | `POST /compare` | Side-by-side disease comparison with similarity scoring |
| **Hypothesize** | `POST /hypotheses` | 5-strategy testable hypothesis generator |

Two toggles next to the mode switcher (only when Analyze or Research is active):

- **pubmed** — for Analyze mode; includes live PubMed in the retrieval context.
- **verify** — for Analyze or Research; runs the figure-grounded verification pass after generation. A coloured banner in the citation panel / agent trace reports verdict (`supported` / `partially_supported` / `unsupported` / `no_images`), confidence, image count, and the verifier's notes; the answer is rewritten inline with `[unverified]` and `[uncertain]` markers when the verifier dissents.

---

## Completed Capabilities

- Domain-agnostic platform with domain as a runtime string parameter
- **Truly multimodal retrieval** — three-leg hybrid: BM25 (lexical) + dense MiniLM (semantic text) + CLIP ViT-B/32 (cross-modal text↔image), fused via RRF and CrossEncoder-reranked
- **First-class figure and table propositions** — figures dedup'd by SHA-256 and stored on disk; tables extracted via pdfplumber as markdown + raw rows + bbox, with the table region rasterized for vision context
- **Retrieved figures auto-attached to the LLM** as native Anthropic vision content blocks, so the model grounds quantitative claims in actual image pixels
- **Layout-aware sentence-bounded chunker** — page-bounded, never cuts mid-sentence, 5–10× fewer chunks than the prior sliding window
- **CLIP image→image retrieval** when the user uploads a probe figure (`/query/images`)
- **Tool-using research agent** (`mode="research"`) — Sonnet 4.6 planner with hybrid retriever, PubMed, causal graph, and topic comparator as native tools; bounded by iterations + wall-clock + daily budget
- **Figure-grounded verification pass** (`verify=true`) — Sonnet vision re-checks cited figures and tags unsupported claims `[unverified]` inline
- **Content-addressed image API** — `/images/{hash}` streams stored figures with `Cache-Control: immutable`; frontend renders thumbnails inline in the citation panel
- 3-tier confidence-gated inference routing with daily budget enforcement
- SSE streaming for both single-shot RAG (`/query/stream`) and the agent (`/query/agent`), with a dedicated `AgentTrace` UI that surfaces planner steps and tool dispatches live
- **Research Agent mode** in the composer plus a **verify** toggle that wires the figure-grounded verification pass into both Analyze and Research modes
- Prometheus observability and structlog JSON logging
- Async SQLite proposition store (aiosqlite + SQLAlchemy ORM) with backward-compatible `ALTER TABLE` migrations for the multimodal columns
- Disease/Mechanism Intelligence (DMI) module — mechanism reports and target risk scoring
- PDF ingestion pipeline: text + figures + tables → multimodal propositions with CLIP embeddings persisted as float32 blobs
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
