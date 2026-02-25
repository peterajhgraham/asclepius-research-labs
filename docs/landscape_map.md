# Biological Data Infrastructure — Landscape Map

A survey of the tools and frameworks that operate in the same space as
Asclepius Research Labs, and how Asclepius differs from each.

---

## Tier 1 — Raw Data Repositories

| Tool / Resource | Purpose | Gap Asclepius Fills |
|---|---|---|
| **GEO** (NCBI Gene Expression Omnibus) | Public repository for raw expression data | No enforced schema; metadata is free-text |
| **ArrayExpress / BioStudies** | European counterpart to GEO | Same free-text metadata problem |
| **CELLxGENE Data Portal** | Curated single-cell datasets with schema | Schema is fixed; cannot extend for custom experiments |

---

## Tier 2 — Processing Frameworks

| Tool | Purpose | Gap Asclepius Fills |
|---|---|---|
| **Seurat** (R) | Single-cell analysis suite | No versioning; outputs are not lineage-tracked |
| **Scanpy** (Python) | Python equivalent of Seurat | Same versioning gap |
| **Cell Ranger** (10x Genomics) | FASTQ → count matrix | Outputs are not directly tied to a schema |
| **STARsolo** | FASTQ → count matrix | Same as Cell Ranger |

---

## Tier 3 — Data Schema / Standards

| Standard | Purpose | Gap Asclepius Fills |
|---|---|---|
| **CELLxGENE Schema** | Per-cell metadata standard | Targets public release, not lab-internal iteration |
| **MINSEQE** | Minimum info for seq experiments | High-level guideline, not code-enforced |
| **FAIR Data Principles** | Findable, Accessible, Interoperable, Reusable | Principles only; no implementation |

---

## Tier 4 — Versioning & Lineage Tools

| Tool | Purpose | Gap Asclepius Fills |
|---|---|---|
| **DVC** (Data Version Control) | Git-like versioning for large files | File-level only; no biological semantics |
| **Pachyderm** | Data pipeline versioning | Complex infrastructure; overkill for single-lab use |
| **lakeFS** | Git for data lakes | Storage-focused; no biological schema |
| **MLflow** | ML experiment tracking | Model-centric; not designed for wet-lab experiments |

---

## Where Asclepius Sits

```
Raw Data (GEO / CELLxGENE)
         │
         ▼
  [asclepius/ingestion.py]   ← validate, normalize, structure
         │
         ▼
  [asclepius/schema.py]      ← Experiment / Sample / CellState
         │
         ▼
  [asclepius/models.py]      ← BiologicalStateGraph
         │
         ▼
  [asclepius/versioning.py]  ← lineage tracking, branching
         │
         ▼
  Downstream Analysis (Scanpy / Seurat / Foundation Models)
```

Asclepius is the **thin, versioned data layer** between raw public data and
downstream modelling — the piece that is currently missing from most labs'
workflows.

---

## Key Differentiators

1. **Code-enforced schema** — required fields are validated at ingest time,
   not as documentation suggestions.
2. **Versioning with biological semantics** — versions are tied to
   `processing_version` strings that encode *what changed*, not just *when*.
3. **Lineage tracking** — every derived dataset records its parent, enabling
   full reproducibility audits.
4. **Python-native** — no external services required; runs in any Python
   environment alongside Scanpy or Seurat via rpy2.
