# Asclepius Research Labs

> **Structured causal reasoning over immune signaling networks**

immunograph is a modular, extensible reasoning engine for immune signaling
research.  It provides a full pipeline from public data ingestion through
knowledge-graph construction, node embedding, causal reasoning, and
experiment suggestion — with an initial focus on autoimmune diseases and a
design that supports future expansion into oncology and vaccines.

---

## Repository Structure

```
immunograph/
├── data_ingestion/
│   ├── pubmed_parser.py           # PubMed abstract search & interaction extraction
│   ├── pathway_loader.py          # KEGG & Reactome pathway loading
│   ├── perturbation_loader.py     # CRISPR / cytokine perturbation datasets
│   └── entity_normalizer.py       # HGNC / UniProt ID normalisation
├── graph/
│   ├── schema.py                  # Node & edge type definitions
│   ├── graph_builder.py           # Build Neo4j or in-memory graph
│   └── graph_queries.py           # Query & explore relationships
├── embeddings/
│   ├── train_gnn.py               # Graph neural network trainer
│   ├── node2vec_baseline.py       # Node2Vec baseline
│   └── inference.py               # Embedding inference & similarity
├── causal/
│   ├── propagation.py             # Probabilistic causal signal propagation
│   ├── intervention_ranker.py     # Rank nodes for intervention impact
│   └── scoring_utils.py           # Scoring utility functions
├── optimizer/
│   ├── active_learning.py         # Upper-confidence-bound experiment selection
│   └── experiment_suggester.py    # End-to-end experiment suggestion
├── notebooks/
│   └── immune_demo.ipynb          # Demo: target ranking & experiment simulation
├── api/
│   └── app.py                     # Flask REST API wrapper
├── README.md
└── requirements.txt
```

---

## Architecture Overview

### 1. Data Ingestion
| Module | Description |
|---|---|
| `pubmed_parser.py` | Queries NCBI E-utilities and extracts `(source, target, edge_type)` triples via regex / NLP |
| `pathway_loader.py` | Downloads KGML from KEGG REST API; parses Reactome event hierarchies |
| `perturbation_loader.py` | Loads CRISPR screen CSVs and cytokine perturbation tables |
| `entity_normalizer.py` | Maps aliases to canonical HGNC symbols via a local table + optional MyGene.info API |

All loaders output a uniform edge list:
```python
[(source_id, target_id, edge_type, metadata_dict), ...]
```

### 2. Graph Construction
- **Nodes**: `Gene`, `Protein`, `Cytokine`, `Receptor`, `TranscriptionFactor`, `CellType`, `Pathway`
- **Edges**: `activates`, `inhibits`, `binds`, `expressed_in`, `downstream_of`, `part_of_pathway`
- **Backend**: Neo4j (production) or in-memory Python dicts (development / testing)

### 3. Representation Learning
- `GNNTrainer` — message-passing GNN with NumPy (drop-in PyTorch Geometric replacement)
- `Node2VecBaseline` — biased random walk + skip-gram with negative sampling
- `EmbeddingInference` — cosine similarity, most-similar lookup, subgraph aggregation

### 4. Causal Reasoning
- `CausalPropagator` — probabilistic belief propagation with signed edge weights, configurable decay
- `InterventionRanker` — combines propagation scores with structural degree for intervention ranking
- `scoring_utils` — normalisation helpers (`minmax`, `zscore`, `softmax`), composite influence scores

### 5. Experiment Suggestion
- `ActiveLearner` — Bayesian upper-confidence-bound strategy over perturbation candidates
- `ExperimentSuggester` — orchestrates causal ranking → prior initialisation → UCB selection

### 6. API & Notebooks
- `api/app.py` — Flask REST endpoints for graph management, causal reasoning, and suggestions
- `notebooks/immune_demo.ipynb` — interactive demo walkthrough

---

## Quick Start

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the demo notebook
```bash
jupyter notebook notebooks/immune_demo.ipynb
```

### Start the REST API
```bash
python api/app.py
```

### Minimal Python example
```python
from graph.graph_builder import ImmuneGraphBuilder
from graph.graph_queries import GraphQueryEngine
from causal.propagation import CausalPropagator
from causal.intervention_ranker import InterventionRanker
from optimizer.experiment_suggester import ExperimentSuggester

# Build in-memory graph
builder = ImmuneGraphBuilder(use_memory_backend=True)
builder.create_node("IL6",    "Cytokine")
builder.create_node("STAT3",  "TranscriptionFactor")
builder.create_node("JAK1",   "Protein")
builder.create_node("IL6R",   "Receptor")

builder.create_edge("IL6",  "IL6R",  "binds",     confidence_score=0.95)
builder.create_edge("IL6R", "JAK1",  "activates", confidence_score=0.90)
builder.create_edge("JAK1", "STAT3", "activates", confidence_score=0.92)

# Rank interventions upstream of STAT3
edge_list = [(e["source"], e["target"], e["type"], e)
             for e in builder.get_edge_list()]

ranker = InterventionRanker()
rankings = ranker.rank_interventions("STAT3", edge_list, top_k=5)
for r in rankings:
    print(r["node_id"], f"{r['score']:.3f}")

# Suggest experiments
suggester = ExperimentSuggester()
suggestions = suggester.suggest_experiments("STAT3", edge_list, budget=3)
for s in suggestions:
    print(s["rank"], s["node_id"], s["rationale"])
```

---

## Neo4j Backend

Set `use_memory_backend=False` (the default) and provide connection details:

```python
builder = ImmuneGraphBuilder(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your_password",
)
```

Make sure Neo4j is running and the `neo4j` Python package is installed.

---

## Roadmap

- [x] Autoimmune disease focus (NF-κB, JAK-STAT pathways)
- [ ] Oncology immune network expansion
- [ ] Vaccine / infectious disease module
- [ ] spaCy + BioBERT NLP pipeline for pubmed_parser
- [ ] PyTorch Geometric GNN backend
- [ ] Immune cell atlas integration (CellTypist, scArches)
- [ ] Interactive Cytoscape.js graph visualisation

---

