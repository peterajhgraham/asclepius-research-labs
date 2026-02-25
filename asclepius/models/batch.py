"""
Batch metadata models.

Batch effects are one of the most common sources of technical noise in
RNA-seq data.  Recording batch provenance — who ran the samples, on which
instrument, with which reagent lots — is the first step toward detecting
and correcting for batch-introduced variance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional


@dataclass
class Batch:
    """
    A batch of samples processed together under shared technical conditions.

    A 'batch' here corresponds to samples that share the same:
    - Sequencing run (flow cell / lane)
    - Library preparation date and operator
    - Reagent kit lot numbers

    Capturing these fields enables downstream batch-correction algorithms
    (e.g. ComBat, Harmony, scVI) to model technical covariation.
    """

    batch_id: str
    experiment_id: str                              # Parent experiment
    sequencing_date: date
    sequencing_platform: str                       # e.g. "Illumina NovaSeq 6000"
    flow_cell_id: Optional[str] = None
    lane: Optional[str] = None                     # e.g. "L001"
    library_kit: Optional[str] = None              # e.g. "Illumina TruSeq Stranded mRNA"
    library_kit_lot: Optional[str] = None
    rna_extraction_date: Optional[date] = None
    rna_extraction_kit: Optional[str] = None
    rna_extraction_lot: Optional[str] = None
    operator: Optional[str] = None                 # Lab member responsible
    facility: Optional[str] = None                 # Core facility name
    notes: Optional[str] = None
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "experiment_id": self.experiment_id,
            "sequencing_date": self.sequencing_date.isoformat(),
            "sequencing_platform": self.sequencing_platform,
            "flow_cell_id": self.flow_cell_id,
            "lane": self.lane,
            "library_kit": self.library_kit,
            "library_kit_lot": self.library_kit_lot,
            "rna_extraction_date": (
                self.rna_extraction_date.isoformat()
                if self.rna_extraction_date
                else None
            ),
            "rna_extraction_kit": self.rna_extraction_kit,
            "rna_extraction_lot": self.rna_extraction_lot,
            "operator": self.operator,
            "facility": self.facility,
            "notes": self.notes,
            "extra_metadata": self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Batch":
        data = dict(data)
        data["sequencing_date"] = date.fromisoformat(data["sequencing_date"])
        if data.get("rna_extraction_date"):
            data["rna_extraction_date"] = date.fromisoformat(
                data["rna_extraction_date"]
            )
        return cls(**data)
