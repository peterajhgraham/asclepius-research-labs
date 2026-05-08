"""Unified data ingestion layer.

Loads all JSON datasets from the ``datasets/`` directory at import time
and exposes them through typed containers that the query engine can search.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATASET_DIR = Path(__file__).resolve().parent / "datasets"


# ---------------------------------------------------------------------------
# Typed containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CytokineEdge:
    source: str
    target: str
    edge_type: str
    source_type: str
    target_type: str
    pathway: str
    diseases: list[str]
    confidence: float
    pmid: str
    description: str


@dataclass(frozen=True)
class PathwayRecord:
    pathway_id: str
    pathway_name: str
    database: str
    description: str
    disease_relevance: list[str]
    key_nodes: list[dict[str, str]]
    edges: list[dict[str, Any]]
    therapeutic_targets: list[dict[str, Any]]
    key_references: list[str]


@dataclass(frozen=True)
class DiseaseRecord:
    disease_id: str
    disease_name: str
    description: str
    prevalence: str
    pathogenic_mechanisms: list[str]
    key_cell_types: list[str]
    associated_genes: list[dict[str, Any]]
    hla_associations: list[str]
    autoantibodies: list[str]
    approved_therapies: list[dict[str, Any]]
    key_references: list[str]


@dataclass(frozen=True)
class TherapeuticRecord:
    drug_name: str
    brand_name: str
    drug_class: str
    target: str
    target_type: str
    mechanism: str
    molecular_type: str
    approved_indications: list[dict[str, Any]]
    pivotal_trials: list[dict[str, Any]]
    safety_signals: list[str]


# ---------------------------------------------------------------------------
# Global stores — populated at import time
# ---------------------------------------------------------------------------

@dataclass
class DataStore:
    """Container holding all loaded datasets."""

    cytokine_edges: list[CytokineEdge] = field(default_factory=list)
    pathways: list[PathwayRecord] = field(default_factory=list)
    diseases: list[DiseaseRecord] = field(default_factory=list)
    therapeutics: list[TherapeuticRecord] = field(default_factory=list)
    loaded_files: list[str] = field(default_factory=list)


def _safe_load(filepath: Path) -> dict | list | None:
    """Load a JSON file, returning *None* on any error."""
    try:
        with open(filepath, encoding="utf-8") as fh:
            data = json.load(fh)
        logger.info("Loaded dataset %s (%d bytes)", filepath.name, filepath.stat().st_size)
        return data
    except FileNotFoundError:
        logger.debug("Dataset file not found: %s", filepath)
    except Exception:
        logger.warning("Failed to load %s", filepath, exc_info=True)
    return None


def _load_cytokine_network(store: DataStore) -> None:
    data = _safe_load(_DATASET_DIR / "cytokine_network.json")
    if not data:
        return
    store.loaded_files.append("cytokine_network.json")
    for rec in data.get("records", []):
        try:
            store.cytokine_edges.append(CytokineEdge(
                source=rec["source"],
                target=rec["target"],
                edge_type=rec.get("edge_type", ""),
                source_type=rec.get("source_type", ""),
                target_type=rec.get("target_type", ""),
                pathway=rec.get("pathway", ""),
                diseases=rec.get("diseases", []),
                confidence=rec.get("confidence", 0.0),
                pmid=rec.get("pmid", ""),
                description=rec.get("description", ""),
            ))
        except Exception:
            logger.debug("Skipping malformed cytokine record: %s", rec)


def _load_pathways(store: DataStore) -> None:
    data = _safe_load(_DATASET_DIR / "immune_pathways.json")
    if not data:
        return
    store.loaded_files.append("immune_pathways.json")
    for rec in data.get("pathways", []):
        try:
            store.pathways.append(PathwayRecord(
                pathway_id=rec.get("pathway_id", ""),
                pathway_name=rec.get("pathway_name", ""),
                database=rec.get("database", ""),
                description=rec.get("description", ""),
                disease_relevance=rec.get("disease_relevance", []),
                key_nodes=rec.get("key_nodes", []),
                edges=rec.get("edges", []),
                therapeutic_targets=rec.get("therapeutic_targets", []),
                key_references=rec.get("key_references", []),
            ))
        except Exception:
            logger.debug("Skipping malformed pathway record: %s", rec)


def _load_diseases(store: DataStore) -> None:
    data = _safe_load(_DATASET_DIR / "disease_associations.json")
    if not data:
        return
    store.loaded_files.append("disease_associations.json")
    for rec in data.get("diseases", []):
        try:
            store.diseases.append(DiseaseRecord(
                disease_id=rec.get("disease_id", ""),
                disease_name=rec.get("disease_name", ""),
                description=rec.get("description", ""),
                prevalence=rec.get("prevalence", ""),
                pathogenic_mechanisms=rec.get("pathogenic_mechanisms", []),
                key_cell_types=rec.get("key_cell_types", []),
                associated_genes=rec.get("associated_genes", []),
                hla_associations=rec.get("hla_associations", []),
                autoantibodies=rec.get("autoantibodies", []),
                approved_therapies=rec.get("approved_therapies", []),
                key_references=rec.get("key_references", []),
            ))
        except Exception:
            logger.debug("Skipping malformed disease record: %s", rec)


def _load_therapeutics(store: DataStore) -> None:
    data = _safe_load(_DATASET_DIR / "therapeutic_targets.json")
    if not data:
        return
    store.loaded_files.append("therapeutic_targets.json")
    for rec in data.get("therapeutics", []):
        try:
            store.therapeutics.append(TherapeuticRecord(
                drug_name=rec.get("drug_name", ""),
                brand_name=rec.get("brand_name", ""),
                drug_class=rec.get("drug_class", ""),
                target=rec.get("target", ""),
                target_type=rec.get("target_type", ""),
                mechanism=rec.get("mechanism", ""),
                molecular_type=rec.get("molecular_type", ""),
                approved_indications=rec.get("approved_indications", []),
                pivotal_trials=rec.get("pivotal_trials", []),
                safety_signals=rec.get("safety_signals", []),
            ))
        except Exception:
            logger.debug("Skipping malformed therapeutic record: %s", rec)


def load_all() -> DataStore:
    """Load every available dataset and return a populated ``DataStore``."""
    store = DataStore()
    _load_cytokine_network(store)
    _load_pathways(store)
    _load_diseases(store)
    _load_therapeutics(store)
    logger.info(
        "DataStore ready: %d cytokine edges, %d pathways, %d diseases, %d therapeutics (files: %s)",
        len(store.cytokine_edges),
        len(store.pathways),
        len(store.diseases),
        len(store.therapeutics),
        ", ".join(store.loaded_files) or "none",
    )
    return store


# Singleton store — loaded once at import time.
STORE = load_all()
