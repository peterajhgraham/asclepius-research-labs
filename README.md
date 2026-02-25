# Asclepius Research Labs – Biological Data Infrastructure

A starter Python application for managing biological research data: RNA-seq experiments, perturbation metadata, batch provenance, and ontology terms.

## Overview

This project addresses the foundational data-infrastructure needs of a modern biology lab:

| Concern | Module |
|---|---|
| RNA-seq data storage & versioning | `asclepius/models/rnaseq.py` |
| Perturbation metadata | `asclepius/models/perturbation.py` |
| Batch effect provenance | `asclepius/models/batch.py` |
| Biological ontologies | `asclepius/models/ontology.py` |
| Persistent storage | `asclepius/storage/database.py` |
| Command-line interface | `asclepius/cli.py` |

## Quick Start

```bash
# Install
pip install -e .

# Initialise a new database
python -m asclepius init

# List all experiments
python -m asclepius experiments list

# Show version history for an experiment
python -m asclepius experiments versions EXP_001

# List batches for an experiment
python -m asclepius batches list --experiment EXP_001

# List perturbations
python -m asclepius perturbations list

# Browse ontology terms
python -m asclepius ontology list --namespace GO --no-deprecated
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Key Concepts

### RNA-seq Versioning
`RNASeqExperiment.content_hash()` computes a SHA-256 digest over the
experiment's scientific content (assembly, annotation, pipeline version,
and sample list). Any modification that changes the biology produces a
new hash, which is recorded in the `version_log` table on every save.

### Perturbation Metadata
`Perturbation` follows LINCS / JUMP-CP metadata conventions, capturing
compound identity, dose, duration, target gene, and vehicle — everything
needed to compare perturbation responses across datasets.

### Batch Provenance
`Batch` records sequencing date, platform, flow cell, library-kit lot,
and RNA-extraction lot. These fields feed directly into batch-correction
algorithms (ComBat, Harmony, scVI).

### Ontology Terms
`OntologyTerm` tracks whether a term is current or deprecated and, if
deprecated, which term replaces it. This surfaces broken ontology links
before they propagate through downstream analysis.

## Project Layout

```
asclepius/
    models/
        rnaseq.py          # RNASeqExperiment, Sample
        perturbation.py    # Perturbation, PerturbationType
        batch.py           # Batch
        ontology.py        # OntologyTerm, OntologyNamespace
    storage/
        database.py        # SQLite-backed Database
    cli.py                 # Command-line interface
tests/
    test_models.py
    test_storage.py
pyproject.toml
requirements.txt
```