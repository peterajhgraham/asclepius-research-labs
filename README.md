# Asclepius Research Labs — Structured, Versioned Biological Data Layer

## What This Is

> You are building a structured, versioned data layer that makes biological experiments reproducible, queryable, and model-ready.

You are **not** discovering drugs.  
You are turning messy experimental outputs into clean, relational state graphs.

---

## Project Layout

```
asclepius-research-labs/
│
├── data/
│   ├── raw/            ← original, unmodified source files
│   └── processed/      ← outputs of ingestion / preprocessing
│
├── notebooks/
│   ├── 01_dataset_autopsy.ipynb    ← structural analysis of PBMC 3k
│   └── 02_schema_mapping.ipynb     ← map raw fields → Asclepius v1 schema
│
├── asclepius/
│   ├── schema.py       ← Experiment, Sample, CellState, ProcessingPipeline
│   ├── models.py       ← BiologicalStateGraph
│   ├── ingestion.py    ← load & validate scRNA-seq data
│   └── versioning.py   ← git-like dataset lineage tracking
│
├── docs/
│   ├── pain_points.md      ← concrete problems this project solves
│   ├── schema_v1.md        ← formal schema specification
│   └── landscape_map.md    ← tool landscape & where Asclepius fits
│
├── experiments/        ← ad-hoc experiment scripts (not notebooks)
│
└── README.md
```

---

## Core Concepts

### Schema (`asclepius/schema.py`)

Four entities form the biological state graph:

| Entity | Description |
|---|---|
| `Experiment` | Top-level container (organism, assay, date, pipeline version) |
| `Sample` | A sample within an experiment with perturbation metadata |
| `CellState` | Observed state of a single cell with data pointers |
| `ProcessingPipeline` | Versioned preprocessing pipeline definition |

### State Graph (`asclepius/models.py`)

`BiologicalStateGraph` assembles the four entities into a relational graph
with validation:

```python
from datetime import date
from asclepius import Experiment, ProcessingPipeline, Sample, CellState, BiologicalStateGraph

graph = BiologicalStateGraph(
    experiment=Experiment(id="GSE96315", organism="NCBITaxon:9606",
                          assay_type="EFO:0009899", date=date(2017, 1, 1)),
    pipeline=ProcessingPipeline(id="cellranger_v2", reference_genome="GRCh38",
                                normalization_method="log1p_CP10K"),
)
graph.add_sample(Sample(id="S1", experiment_id="GSE96315"))
print(graph.summary())
```

### Ingestion (`asclepius/ingestion.py`)

Validates and loads single-cell metadata and expression matrices:

```python
from asclepius import ingest

result = ingest("data/raw/pbmc3k_metadata.csv", "data/raw/pbmc3k_expression.csv")
print(f"Loaded {len(result.cells)} cells")
for w in result.warnings:
    print("WARNING:", w)
```

**Required metadata fields:** `cell_id`, `experiment_id`, `assay_type`, `organism`

Column names are automatically normalized to `snake_case`.

### Versioning (`asclepius/versioning.py`)

Git-like lineage tracking for processed datasets:

```python
from asclepius import VersionRegistry

reg = VersionRegistry()

v1 = reg.register("pbmc3k", {"norm": "log1p_CP10K", "genome": "GRCh38"})
v2 = reg.commit(v1, {"norm": "scran", "genome": "GRCh38"}, notes="Switch to scran normalisation")

branch = reg.branch(v1, "experiment-mito-filter", notes="Test tighter mito threshold")

print([h.processing_version for h in reg.history(v2)])
# ['1.0.0', '1.0.1']
```

---

## Dataset

Starting point: **10x PBMC 3k** (Zheng et al., 2017)

| Field | Value |
|---|---|
| GEO Accession | GSE96315 |
| Organism | *Homo sapiens* |
| Technology | 10x Chromium v2 |
| Approx. cells | 2,700 |
| Gene ID format | Ensembl IDs |

Download raw data from [GEO GSE96315](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE96315) into `data/raw/`.

---

## Quick Start

```bash
# Install
pip install -e .

# Run tests
python -m pytest tests/ -v
```

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/schema_v1.md`](docs/schema_v1.md) | Formal schema specification for v1 |
| [`docs/pain_points.md`](docs/pain_points.md) | Concrete problems this layer solves |
| [`docs/landscape_map.md`](docs/landscape_map.md) | Tool landscape & positioning |
