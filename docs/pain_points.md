# Pain Points — Biological Data Infrastructure

This document records the concrete data problems that Asclepius Research Labs
is designed to solve.  Each pain point maps to a module or schema decision.

---

## 1. Inconsistent Metadata Encoding

**Problem:** The same biological concept is represented differently across
datasets, making automated integration impossible without manual curation.

| Concept | Dataset A | Dataset B | Dataset C |
|---|---|---|---|
| Organism | `"human"` | `"Mus musculus"` | `NCBITaxon:9606` |
| Cell type | `"CD4 T cell"` | `"T_CD4"` | `CL:0000624` |
| Tissue | `"blood"` | absent | `UBERON:0000178` |
| Assay | `"10x_v2"` | `"chromium"` | `EFO:0009899` |

**Solution:** Enforce ontology CURIEs at the schema level (planned for v2).

---

## 2. No Processing Lineage

**Problem:** Processed datasets often have no record of which pipeline
version, reference genome, or normalization method produced them.  Reproducing
results requires detective work.

**Solution:** `ProcessingPipeline` entity + `versioning.py` track every
parameter and bump a version string when anything changes.

---

## 3. Incompatible Normalization Methods

**Problem:** Datasets normalized with `log1p(CP10K)` cannot be directly
concatenated with datasets normalized with `scran` — the scales are
incompatible.

**Solution:** `CellState.raw_data_pointer` always points to **raw** counts,
enabling any normalization to be applied consistently downstream.

---

## 4. Missing Required Fields

**Problem:** Publicly released datasets routinely omit fields that downstream
models require.

Common offenders:
- `suspension_type` (cell vs nucleus) — absent in PBMC 3k and Tabula Muris
- `disease_ontology_term_id` — absent in healthy-only datasets
- `donor_id` — often withheld for privacy

**Solution:** `ingestion.py` validates required fields at load time and
emits explicit warnings for missing data.

---

## 5. No Versioning for Derived Datasets

**Problem:** When a filtered or re-processed version of a dataset is
created, there is typically no machine-readable record of what was changed
or which parent dataset it was derived from.

**Solution:** `VersionRegistry` in `versioning.py` tracks `derived_from_dataset_id`
and `derived_from_version`, supporting both linear commits and branches.

---

## 6. Gene ID Format Mismatch

**Problem:** Some datasets use Ensembl IDs (`ENSG00000139618`), others use
gene symbols (`BRCA2`), and others use MGI symbols (`Brca2`).  Merging
expression matrices requires a mapping step that is rarely documented.

**Solution (planned):** `ProcessingPipeline.reference_genome` provides the
anchor.  A gene ID normalization step will be added in v2.

---

## 7. Batch Effect Provenance Lost

**Problem:** Sequencing date, platform, flow cell ID, and library-kit lot
are rarely stored alongside expression data, making it impossible to
diagnose batch effects post-hoc.

**Solution (planned):** A `Batch` entity (extending the existing pipeline
model) will capture these fields in a future schema version.
