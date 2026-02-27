"""
Normalize genomic variants to a canonical representation.

All downstream models consume ``NormalizedVariant`` objects so that variants
originating from ClinVar, gnomAD, or any future source are represented
consistently.

Canonical form
--------------
- Chromosome stripped of ``chr`` prefix (e.g. ``"12"`` not ``"chr12"``).
- Position as a 1-based integer (GRCh38).
- Reference and alternate alleles in upper-case.
- Stable key: ``"chrom:pos:ref:alt"`` (e.g. ``"12:40340400:G:A"``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils.helpers import build_variant_key, normalise_gene_symbol


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NormalizedVariant:
    """A variant in canonical representation.

    Attributes
    ----------
    key : str
        Stable identifier ``chrom:pos:ref:alt``.
    chrom : str
        Chromosome without ``chr`` prefix (e.g. ``"12"``).
    pos : int
        1-based genomic position (GRCh38).
    ref : str
        Upper-case reference allele.
    alt : str
        Upper-case alternate allele.
    gene_symbol : str
        Upper-case HGNC gene symbol.
    clinical_significance : str
        Clinical significance label (empty string if unknown).
    allele_frequency : float
        Population allele frequency (0–1).  ``0.0`` if not available.
    lof : str
        Loss-of-function annotation (``"HC"`` = high confidence, ``""`` = none).
    source : str
        Data source (e.g. ``"ClinVar"``, ``"gnomAD"``).
    extra : dict
        Source-specific fields preserved for downstream use.
    """

    key: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gene_symbol: str
    clinical_significance: str = ""
    allele_frequency: float = 0.0
    lof: str = ""
    source: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core normalisation function
# ---------------------------------------------------------------------------

def normalize_variant(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    *,
    gene_symbol: str = "",
    clinical_significance: str = "",
    allele_frequency: float = 0.0,
    lof: str = "",
    source: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> NormalizedVariant:
    """Create a :class:`NormalizedVariant` from raw field values.

    Parameters
    ----------
    chrom : str
        Raw chromosome string (e.g. ``"chr12"`` or ``"12"``).
    pos : int
        1-based genomic position.
    ref : str
        Reference allele (any case).
    alt : str
        Alternate allele (any case).
    gene_symbol : str
        Gene symbol (any case; will be upper-cased).
    clinical_significance : str
        ClinVar clinical significance string.
    allele_frequency : float
        Population allele frequency.
    lof : str
        LoF annotation string.
    source : str
        Name of the originating data source.
    extra : dict, optional
        Additional key-value metadata.

    Returns
    -------
    NormalizedVariant
    """
    key = build_variant_key(chrom, pos, ref, alt)
    chrom_lower = chrom.strip().lower()
    clean_chrom = chrom.strip()[3:] if chrom_lower.startswith("chr") else chrom.strip()

    return NormalizedVariant(
        key=key,
        chrom=clean_chrom,
        pos=pos,
        ref=ref.upper(),
        alt=alt.upper(),
        gene_symbol=normalise_gene_symbol(gene_symbol),
        clinical_significance=clinical_significance,
        allele_frequency=allele_frequency,
        lof=lof,
        source=source,
        extra=extra or {},
    )


# ---------------------------------------------------------------------------
# Batch normalisation helpers
# ---------------------------------------------------------------------------

def normalize_clinvar_records(records: list) -> List[NormalizedVariant]:
    """Convert a list of :class:`~data_ingestion.load_clinvar.ClinVarRecord`
    objects to :class:`NormalizedVariant` objects.

    Parameters
    ----------
    records : list of ClinVarRecord
        Raw ClinVar records from :func:`~data_ingestion.load_clinvar.load_clinvar_tsv`.

    Returns
    -------
    list of NormalizedVariant
    """
    return [
        normalize_variant(
            chrom=r.chrom,
            pos=r.pos,
            ref=r.ref,
            alt=r.alt,
            gene_symbol=r.gene_symbol,
            clinical_significance=r.clinical_significance,
            source="ClinVar",
            extra={
                "variant_id": r.variant_id,
                "condition": r.condition,
                "review_status": r.review_status,
                "phenotype_ids": r.phenotype_ids,
            },
        )
        for r in records
    ]


def normalize_gnomad_records(records: list) -> List[NormalizedVariant]:
    """Convert a list of :class:`~data_ingestion.load_gnomad.GnomadRecord`
    objects to :class:`NormalizedVariant` objects.

    Parameters
    ----------
    records : list of GnomadRecord
        Raw gnomAD records from :func:`~data_ingestion.load_gnomad.load_gnomad_tsv`
        or :func:`~data_ingestion.load_gnomad.fetch_gnomad_gene_variants`.

    Returns
    -------
    list of NormalizedVariant
    """
    return [
        normalize_variant(
            chrom=r.chrom,
            pos=r.pos,
            ref=r.ref,
            alt=r.alt,
            gene_symbol=r.gene_symbol,
            allele_frequency=r.allele_frequency,
            lof=r.lof,
            source="gnomAD",
            extra={
                "consequence": r.consequence,
                "allele_count": r.allele_count,
                "allele_number": r.allele_number,
            },
        )
        for r in records
    ]


def merge_variant_sources(
    *variant_lists: List[NormalizedVariant],
) -> List[NormalizedVariant]:
    """Merge multiple lists of :class:`NormalizedVariant`, deduplicating by key.

    When the same variant key appears in multiple sources, the first occurrence
    is kept and ``extra`` fields from later occurrences are merged in.

    Parameters
    ----------
    *variant_lists : list of NormalizedVariant
        One or more lists returned by :func:`normalize_clinvar_records` or
        :func:`normalize_gnomad_records`.

    Returns
    -------
    list of NormalizedVariant
        Deduplicated, merged list.
    """
    seen: Dict[str, NormalizedVariant] = {}
    for variants in variant_lists:
        for v in variants:
            if v.key not in seen:
                seen[v.key] = v
            else:
                # Merge extra fields from the duplicate
                seen[v.key].extra.update(v.extra)
    return list(seen.values())
