"""
Load ClinVar variant data for monogenic neurology analysis.

ClinVar (https://www.ncbi.nlm.nih.gov/clinvar/) provides variant–disease
associations with clinical significance ratings.

This module supports loading from the public ClinVar tab-delimited release:
  variant_summary.txt.gz  (downloaded from NCBI FTP)
  ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz

Typical usage
-------------
>>> from data_ingestion.load_clinvar import load_clinvar_tsv
>>> records = load_clinvar_tsv("data/raw/variant_summary.txt.gz")
>>> print(len(records), "neurology variants loaded")
"""

from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ClinVarRecord:
    """A single ClinVar variant record.

    Attributes
    ----------
    variant_id : str
        ClinVar Variation ID (numeric string).
    gene_symbol : str
        HGNC gene symbol (e.g. ``LRRK2``).
    chrom : str
        Chromosome (e.g. ``12``).
    pos : int
        1-based start position (GRCh38 by default).
    ref : str
        Reference allele.
    alt : str
        Alternate allele.
    clinical_significance : str
        ClinVar clinical significance string (e.g. ``Pathogenic``).
    condition : str
        Semicolon-separated list of associated phenotypes.
    review_status : str
        ClinVar review status (e.g. ``criteria provided, single submitter``).
    phenotype_ids : list of str
        Ontology IDs for associated phenotypes (e.g. ``MedGen:C0270850``).
    extra : dict
        Any additional columns from the source file.
    """

    variant_id: str
    gene_symbol: str
    chrom: str
    pos: int
    ref: str
    alt: str
    clinical_significance: str
    condition: str
    review_status: str
    phenotype_ids: List[str] = field(default_factory=list)
    extra: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Neurology filter
# ---------------------------------------------------------------------------

#: Substrings used to identify neurological phenotypes in free-text fields.
NEUROLOGY_TERMS: frozenset[str] = frozenset({
    "neurolog",
    "epilep",
    "parkins",
    "alzheimer",
    "huntington",
    "ataxia",
    "neuropath",
    "dementia",
    "dystonia",
    "spastic",
    "muscular dystrophy",
    "sclerosis",
    "cerebellar",
    "spinal muscular",
    "leukodystrophy",
    "channelopathy",
    "encephalopathy",
    "myopathy",
    "rett",
    "tuberous sclerosis",
})


def is_neurology_related(phenotype: str) -> bool:
    """Return ``True`` if *phenotype* relates to a neurological condition.

    Parameters
    ----------
    phenotype : str
        Free-text phenotype or condition string.

    Returns
    -------
    bool
    """
    lower = phenotype.lower()
    return any(term in lower for term in NEUROLOGY_TERMS)


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

#: Mapping from ClinVar column names to ClinVarRecord field names.
_COL_MAP: Dict[str, str] = {
    "VariationID": "variant_id",
    "GeneSymbol": "gene_symbol",
    "Chromosome": "chrom",
    "Start": "pos",
    "ReferenceAllele": "ref",
    "AlternateAllele": "alt",
    "ClinicalSignificance": "clinical_significance",
    "PhenotypeList": "condition",
    "ReviewStatus": "review_status",
    "PhenotypeIDS": "phenotype_ids",
}

_KNOWN_COLS: frozenset[str] = frozenset(_COL_MAP.keys())


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_clinvar_tsv(
    path: str | Path,
    *,
    neurology_only: bool = True,
    assembly: str = "GRCh38",
    max_records: Optional[int] = None,
) -> List[ClinVarRecord]:
    """Load ClinVar ``variant_summary.txt`` (or ``.txt.gz``) into records.

    Parameters
    ----------
    path : str or Path
        Path to the ClinVar ``variant_summary.txt`` or
        ``variant_summary.txt.gz`` file.
    neurology_only : bool
        If ``True`` (default), discard records whose ``PhenotypeList`` does
        not contain at least one neurology-related term.
    assembly : str
        Genome assembly filter (default ``"GRCh38"``).  Rows whose
        ``Assembly`` column does not match this value are skipped.  Pass
        ``""`` to keep all assemblies.
    max_records : int, optional
        Stop after loading this many records.  Useful for unit tests and
        quick exploratory runs.

    Returns
    -------
    list of ClinVarRecord
    """
    path = Path(path)
    records: List[ClinVarRecord] = []

    opener = (
        gzip.open(path, "rt", encoding="utf-8")
        if path.suffix == ".gz"
        else open(path, encoding="utf-8")
    )
    with opener as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            # Assembly filter
            if assembly and row.get("Assembly", "") != assembly:
                continue

            # Neurology filter
            phenotype_text = row.get("PhenotypeList", "")
            if neurology_only and not is_neurology_related(phenotype_text):
                continue

            # Parse phenotype IDs
            phenotype_ids = [
                p.strip()
                for p in row.get("PhenotypeIDS", "").split(";")
                if p.strip()
            ]

            # Collect extra fields
            extra = {k: v for k, v in row.items() if k not in _KNOWN_COLS}

            try:
                record = ClinVarRecord(
                    variant_id=row.get("VariationID", ""),
                    gene_symbol=row.get("GeneSymbol", ""),
                    chrom=row.get("Chromosome", ""),
                    pos=int(row.get("Start") or 0),
                    ref=row.get("ReferenceAllele", ""),
                    alt=row.get("AlternateAllele", ""),
                    clinical_significance=row.get("ClinicalSignificance", ""),
                    condition=phenotype_text,
                    review_status=row.get("ReviewStatus", ""),
                    phenotype_ids=phenotype_ids,
                    extra=extra,
                )
            except (ValueError, KeyError):
                continue

            records.append(record)

            if max_records is not None and len(records) >= max_records:
                break

    return records
