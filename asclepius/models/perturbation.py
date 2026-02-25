"""
Perturbation metadata models.

Perturbations are experimental interventions applied to biological samples:
small-molecule treatments, genetic knockouts/knockdowns, CRISPR edits, etc.
Recording them precisely is essential for downstream analysis and
cross-lab reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PerturbationType(str, Enum):
    """High-level category of experimental perturbation."""

    SMALL_MOLECULE = "small_molecule"   # Drug / compound treatment
    CRISPR_KO = "crispr_knockout"       # CRISPR-Cas9 gene knockout
    CRISPR_KD = "crispr_knockdown"      # CRISPRi / siRNA knockdown
    OVEREXPRESSION = "overexpression"   # cDNA / ORF overexpression
    CYTOKINE = "cytokine"               # Cytokine / growth-factor treatment
    CONTROL = "control"                 # Negative control (DMSO, scramble, etc.)


@dataclass
class Perturbation:
    """
    A single experimental perturbation applied to one or more samples.

    Fields follow the LINCS / JUMP-CP metadata conventions to facilitate
    cross-dataset comparisons:
    https://clue.io/lincs-metadata
    """

    perturbation_id: str
    name: str                                       # Human-readable label
    perturbation_type: PerturbationType
    target_gene_symbol: Optional[str] = None       # e.g. "BRCA1"
    target_gene_id: Optional[str] = None           # Entrez/Ensembl ID
    compound_name: Optional[str] = None            # e.g. "Imatinib"
    compound_pubchem_cid: Optional[str] = None     # PubChem CID
    dose_value: Optional[float] = None             # Numeric dose
    dose_unit: Optional[str] = None                # e.g. "uM", "nM"
    duration_hours: Optional[float] = None        # Treatment duration
    vehicle: Optional[str] = None                  # e.g. "DMSO", "PBS"
    moa_terms: List[str] = field(default_factory=list)  # Mechanism-of-action ontology terms
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def is_control(self) -> bool:
        """Return True if this perturbation is a negative control."""
        return self.perturbation_type == PerturbationType.CONTROL

    def to_dict(self) -> dict:
        return {
            "perturbation_id": self.perturbation_id,
            "name": self.name,
            "perturbation_type": self.perturbation_type.value,
            "target_gene_symbol": self.target_gene_symbol,
            "target_gene_id": self.target_gene_id,
            "compound_name": self.compound_name,
            "compound_pubchem_cid": self.compound_pubchem_cid,
            "dose_value": self.dose_value,
            "dose_unit": self.dose_unit,
            "duration_hours": self.duration_hours,
            "vehicle": self.vehicle,
            "moa_terms": self.moa_terms,
            "extra_metadata": self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Perturbation":
        data = dict(data)
        data["perturbation_type"] = PerturbationType(data["perturbation_type"])
        return cls(**data)
