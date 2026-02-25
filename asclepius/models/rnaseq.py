"""
RNA-seq experiment and sample data models.

Captures how RNA-seq data is stored and versioned, including
the metadata needed to reproduce and compare experiments across labs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class LibraryStrategy(str, Enum):
    """Sequencing library preparation strategy."""

    POLY_A = "poly_A"
    TOTAL_RNA = "total_RNA"
    SINGLE_CELL = "single_cell"
    SMART_SEQ2 = "smart_seq2"


class StrandednessProtocol(str, Enum):
    """RNA-seq strandedness protocol."""

    UNSTRANDED = "unstranded"
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass
class Sample:
    """
    A single biological sample sequenced in an RNA-seq experiment.

    Captures the minimal metadata required to interpret count data:
    tissue source, organism, library parameters, and batch assignment.
    """

    sample_id: str
    organism: str                                   # e.g. "Homo sapiens"
    tissue: str                                     # e.g. "liver", "PBMC"
    library_strategy: LibraryStrategy
    strandedness: StrandednessProtocol
    batch_id: str
    perturbation_ids: List[str] = field(default_factory=list)
    cell_line: Optional[str] = None                 # e.g. "K562", "HepG2"
    disease_ontology_term: Optional[str] = None    # e.g. "DOID:9352"
    cell_type_ontology_term: Optional[str] = None  # e.g. "CL:0000236"
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sample_id": self.sample_id,
            "organism": self.organism,
            "tissue": self.tissue,
            "library_strategy": self.library_strategy.value,
            "strandedness": self.strandedness.value,
            "batch_id": self.batch_id,
            "perturbation_ids": self.perturbation_ids,
            "cell_line": self.cell_line,
            "disease_ontology_term": self.disease_ontology_term,
            "cell_type_ontology_term": self.cell_type_ontology_term,
            "extra_metadata": self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Sample":
        data = dict(data)
        data["library_strategy"] = LibraryStrategy(data["library_strategy"])
        data["strandedness"] = StrandednessProtocol(data["strandedness"])
        return cls(**data)


@dataclass
class RNASeqExperiment:
    """
    A versioned RNA-seq experiment.

    Versioning is achieved by hashing the canonical JSON representation
    of the experiment metadata and sample list.  Every mutation that
    changes scientific content produces a new version digest, giving
    a lightweight audit trail without a dedicated version-control backend.
    """

    experiment_id: str
    name: str
    description: str
    created_at: datetime
    samples: List[Sample] = field(default_factory=list)
    genome_assembly: str = "GRCh38"
    annotation_version: str = "Ensembl_110"
    pipeline_version: str = "1.0.0"
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Versioning                                                           #
    # ------------------------------------------------------------------ #

    def content_hash(self) -> str:
        """
        Return a SHA-256 digest of the experiment's scientific content.

        Identical metadata + samples always produce the same digest,
        making it easy to detect unintended modifications.
        """
        payload = {
            "experiment_id": self.experiment_id,
            "genome_assembly": self.genome_assembly,
            "annotation_version": self.annotation_version,
            "pipeline_version": self.pipeline_version,
            "samples": sorted(
                [s.to_dict() for s in self.samples],
                key=lambda s: s["sample_id"],
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def add_sample(self, sample: Sample) -> None:
        """Add a sample to the experiment."""
        ids = {s.sample_id for s in self.samples}
        if sample.sample_id in ids:
            raise ValueError(
                f"Sample '{sample.sample_id}' already exists in experiment "
                f"'{self.experiment_id}'."
            )
        self.samples.append(sample)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "genome_assembly": self.genome_assembly,
            "annotation_version": self.annotation_version,
            "pipeline_version": self.pipeline_version,
            "extra_metadata": self.extra_metadata,
            "content_hash": self.content_hash(),
            "samples": [s.to_dict() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RNASeqExperiment":
        data = dict(data)
        data.pop("content_hash", None)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["samples"] = [Sample.from_dict(s) for s in data.get("samples", [])]
        return cls(**data)
