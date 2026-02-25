"""
Ontology term models.

Biological ontologies (Gene Ontology, Disease Ontology, Cell Ontology,
UBERON, etc.) give controlled vocabularies for annotating data.  In
practice, ontology coverage is incomplete, terms get deprecated, and
different databases use different identifiers for the same concept.
These models capture the term together with its provenance so that
broken ontology links can be detected and repaired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class OntologyNamespace(str, Enum):
    """Supported biological ontology namespaces."""

    GO = "GO"           # Gene Ontology (molecular function / biological process / cellular component)
    DOID = "DOID"       # Disease Ontology
    CL = "CL"           # Cell Ontology
    UBERON = "UBERON"   # Uber-anatomy ontology (tissues / organs)
    CHEBI = "CHEBI"     # Chemical Entities of Biological Interest
    HP = "HP"           # Human Phenotype Ontology
    EFO = "EFO"         # Experimental Factor Ontology
    NCBITaxon = "NCBITaxon"  # NCBI Taxonomy


@dataclass
class OntologyTerm:
    """
    A single term from a biological ontology.

    Stores the term identifier, its human-readable label, and a flag
    indicating whether the term is current (not deprecated).  Deprecated
    terms often still exist in databases; tracking their status surfaces
    data-quality issues early.
    """

    term_id: str                                    # e.g. "GO:0008150"
    namespace: OntologyNamespace
    label: str                                      # e.g. "biological_process"
    definition: Optional[str] = None
    is_deprecated: bool = False
    deprecated_in_favor_of: Optional[str] = None   # Replacement term ID
    synonyms: List[str] = field(default_factory=list)
    parent_term_ids: List[str] = field(default_factory=list)
    source_version: Optional[str] = None           # Ontology release version
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @property
    def curie(self) -> str:
        """Return the compact URI, e.g. 'GO:0008150'."""
        return self.term_id

    def is_valid(self) -> bool:
        """
        Return True if the term is present and not deprecated.

        A common failure mode is annotating samples with a term that was
        valid at analysis time but has since been deprecated or split.
        """
        return not self.is_deprecated

    def resolve(self) -> Optional[str]:
        """
        Return the preferred replacement term ID if this term is deprecated,
        otherwise return this term's own ID.
        """
        if self.is_deprecated and self.deprecated_in_favor_of:
            return self.deprecated_in_favor_of
        return self.term_id if not self.is_deprecated else None

    def to_dict(self) -> dict:
        return {
            "term_id": self.term_id,
            "namespace": self.namespace.value,
            "label": self.label,
            "definition": self.definition,
            "is_deprecated": self.is_deprecated,
            "deprecated_in_favor_of": self.deprecated_in_favor_of,
            "synonyms": self.synonyms,
            "parent_term_ids": self.parent_term_ids,
            "source_version": self.source_version,
            "extra_metadata": self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OntologyTerm":
        data = dict(data)
        data["namespace"] = OntologyNamespace(data["namespace"])
        return cls(**data)
