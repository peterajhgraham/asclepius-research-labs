# Asclepius Biological State Graph — Schema v1

## Overview

This document defines the first formal schema for Asclepius Research Labs.
The goal is a minimal, enforceable relational structure that makes biological
experiments reproducible, queryable, and model-ready.

---

## Core Entities

### 1. Experiment

Represents the top-level container for a single biological experiment.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique experiment identifier (e.g. GEO accession) |
| `organism` | string | NCBI Taxonomy CURIE (e.g. `NCBITaxon:9606`) |
| `assay_type` | string | EFO ontology CURIE (e.g. `EFO:0009899` for 10x v2) |
| `date` | date | Experiment date (ISO 8601) |
| `lab` | string | Originating laboratory |
| `pipeline_version` | string | Semver of the processing pipeline used |

---

### 2. Sample

A biological sample collected within an experiment, with perturbation metadata.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique sample identifier |
| `experiment_id` | string | Foreign key → Experiment.id |
| `perturbation_type` | string | Type of perturbation (e.g. `"CRISPR"`, `"compound"`, `"none"`) |
| `perturbation_target` | string | Gene symbol or compound name |
| `dose` | float or null | Dose applied (units depend on perturbation type) |
| `timepoint` | float or null | Time after perturbation (hours) |

---

### 3. CellState

The observed state of a single cell, linking raw and processed data with
provenance pointers.

| Field | Type | Description |
|---|---|---|
| `id` | string | Cell barcode or unique cell identifier |
| `sample_id` | string | Foreign key → Sample.id |
| `raw_data_pointer` | string | Path or URI to the raw count vector |
| `processed_data_pointer` | string | Path or URI to the normalised count vector |
| `embedding_pointer` | string | Path or URI to the low-dimensional embedding (e.g. UMAP) |
| `annotation_label` | string | Cell type label (free-text or ontology CURIE) |
| `processing_version` | string | Semver of the pipeline that produced this cell state |

---

### 4. ProcessingPipeline

A versioned preprocessing pipeline definition.  Changing any field here
should trigger a version bump in all downstream `CellState` records.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique pipeline identifier |
| `reference_genome` | string | Reference genome assembly (e.g. `GRCh38`) |
| `normalization_method` | string | e.g. `log1p_CP10K`, `scran` |
| `batch_correction_method` | string | e.g. `Harmony`, `ComBat`, `none` |
| `software_version` | string | Semver of the software package |

---

## Entity Relationships

```
Experiment
    └── Sample (many)
            └── CellState (many)

ProcessingPipeline
    └── CellState (many, via processing_version)
```

---

## Versioning Rules

- Every `CellState` carries a `processing_version` that matches the
  `ProcessingPipeline.software_version` used to produce it.
- If any pipeline parameter changes, `processing_version` must be bumped.
- Lineage is tracked via `DatasetVersion` in `asclepius/versioning.py`.

---

## Future Extensions (v2 candidates)

- `organism_ontology_term_id` — enforce `NCBITaxon:` CURIE prefix
- `tissue_ontology_term_id` — enforce `UBERON:` CURIE prefix
- `cell_type_ontology_term_id` — enforce `CL:` CURIE prefix
- `disease_ontology_term_id` — enforce `MONDO:` or `PATO:` CURIE prefix
- `suspension_type` — `"cell"` | `"nucleus"` | `"bulk"`
- QC scalars: `n_counts`, `n_genes`, `pct_counts_mito`, `doublet_score`
