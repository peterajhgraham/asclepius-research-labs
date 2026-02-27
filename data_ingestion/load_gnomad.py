"""
Load gnomAD population variant frequency data for neurology analysis.

gnomAD (https://gnomad.broadinstitute.org/) provides population allele
frequencies and functional annotations for human genetic variants.

Two ingestion pathways are supported:

1. **Local TSV** – parsed from a gnomAD sites TSV export
   (e.g. ``gnomad.exomes.v4.sites.tsv.gz``).
2. **gnomAD GraphQL API** – live query by gene symbol using the public
   endpoint at ``https://gnomad.broadinstitute.org/api``.

Typical usage
-------------
>>> from data_ingestion.load_gnomad import load_gnomad_tsv
>>> records = load_gnomad_tsv("data/raw/gnomad_lrrk2.tsv")

>>> from data_ingestion.load_gnomad import fetch_gnomad_gene_variants
>>> records = fetch_gnomad_gene_variants("LRRK2", dataset="gnomad_r4")
"""

from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GnomadRecord:
    """A single gnomAD variant record.

    Attributes
    ----------
    chrom : str
        Chromosome (e.g. ``"12"``).
    pos : int
        1-based position (GRCh38).
    ref : str
        Reference allele.
    alt : str
        Alternate allele.
    gene_symbol : str
        HGNC gene symbol.
    consequence : str
        Variant consequence annotation (e.g. ``"missense_variant"``).
    allele_frequency : float
        Overall allele frequency across all populations (0–1).
    allele_count : int
        Number of observed alternate alleles.
    allele_number : int
        Total number of alleles with coverage.
    lof : str
        Loss-of-function annotation (``"HC"`` = high-confidence, ``""`` = none).
    extra : dict
        Any additional fields from the source.
    """

    chrom: str
    pos: int
    ref: str
    alt: str
    gene_symbol: str
    consequence: str
    allele_frequency: float
    allele_count: int
    allele_number: int
    lof: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Column mapping for TSV files
# ---------------------------------------------------------------------------

#: Expected TSV column names → GnomadRecord field names.
_TSV_COL_MAP: Dict[str, str] = {
    "chrom": "chrom",
    "pos": "pos",
    "ref": "ref",
    "alt": "alt",
    "gene_symbol": "gene_symbol",
    "consequence": "consequence",
    "AF": "allele_frequency",
    "AC": "allele_count",
    "AN": "allele_number",
    "lof": "lof",
}

_KNOWN_TSV_COLS: frozenset[str] = frozenset(_TSV_COL_MAP.keys())


# ---------------------------------------------------------------------------
# TSV loader
# ---------------------------------------------------------------------------

def load_gnomad_tsv(
    path: str | Path,
    *,
    max_records: Optional[int] = None,
) -> List[GnomadRecord]:
    """Load a gnomAD sites TSV (or ``.tsv.gz``) export into records.

    The file is expected to have tab-separated columns with at least:
    ``chrom``, ``pos``, ``ref``, ``alt``, ``AF``, ``AC``, ``AN``.

    Parameters
    ----------
    path : str or Path
        Path to a gnomAD TSV or ``.tsv.gz`` file.
    max_records : int, optional
        Stop after loading this many records.

    Returns
    -------
    list of GnomadRecord
    """
    path = Path(path)
    records: List[GnomadRecord] = []

    opener = (
        gzip.open(path, "rt", encoding="utf-8")
        if path.suffix == ".gz"
        else open(path, encoding="utf-8")
    )
    with opener as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            extra = {k: v for k, v in row.items() if k not in _KNOWN_TSV_COLS}
            try:
                record = GnomadRecord(
                    chrom=row.get("chrom", ""),
                    pos=int(row.get("pos") or 0),
                    ref=row.get("ref", ""),
                    alt=row.get("alt", ""),
                    gene_symbol=row.get("gene_symbol", ""),
                    consequence=row.get("consequence", ""),
                    allele_frequency=float(row.get("AF") or 0.0),
                    allele_count=int(row.get("AC") or 0),
                    allele_number=int(row.get("AN") or 0),
                    lof=row.get("lof", ""),
                    extra=extra,
                )
            except (ValueError, KeyError):
                continue

            records.append(record)

            if max_records is not None and len(records) >= max_records:
                break

    return records


# ---------------------------------------------------------------------------
# GraphQL API loader
# ---------------------------------------------------------------------------

#: gnomAD public GraphQL endpoint.
GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

_GENE_VARIANTS_QUERY = """
query GeneVariants($geneSymbol: String!, $dataset: DatasetId!) {
  gene(gene_symbol: $geneSymbol, reference_genome: GRCh38) {
    variants(dataset: $dataset) {
      variant_id
      chrom
      pos
      ref
      alt
      consequence
      lof
      exome {
        ac
        an
        af
      }
    }
  }
}
"""


def fetch_gnomad_gene_variants(
    gene_symbol: str,
    *,
    dataset: str = "gnomad_r4",
    timeout: int = 30,
) -> List[GnomadRecord]:
    """Fetch all gnomAD variants for a gene via the public GraphQL API.

    Requires internet access and the ``requests`` package.

    Parameters
    ----------
    gene_symbol : str
        HGNC gene symbol (e.g. ``"LRRK2"``).
    dataset : str
        gnomAD dataset identifier (e.g. ``"gnomad_r4"``).
    timeout : int
        HTTP request timeout in seconds.

    Returns
    -------
    list of GnomadRecord

    Raises
    ------
    ImportError
        If ``requests`` is not installed.
    RuntimeError
        If the API returns errors or an unexpected response structure.
    """
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "requests is required for live gnomAD API queries: pip install requests"
        ) from exc

    payload = {
        "query": _GENE_VARIANTS_QUERY,
        "variables": {"geneSymbol": gene_symbol, "dataset": dataset},
    }
    response = requests.post(GNOMAD_API_URL, json=payload, timeout=timeout)
    response.raise_for_status()

    body = response.json()
    errors = body.get("errors")
    if errors:
        raise RuntimeError(f"gnomAD API errors for gene {gene_symbol!r}: {errors}")

    raw_variants = (
        body.get("data", {})
        .get("gene", {})
        .get("variants", [])
    )
    if raw_variants is None:
        return []

    records: List[GnomadRecord] = []
    for v in raw_variants:
        exome = v.get("exome") or {}
        records.append(
            GnomadRecord(
                chrom=str(v.get("chrom", "")),
                pos=int(v.get("pos") or 0),
                ref=v.get("ref", ""),
                alt=v.get("alt", ""),
                gene_symbol=gene_symbol,
                consequence=v.get("consequence", ""),
                allele_frequency=float(exome.get("af") or 0.0),
                allele_count=int(exome.get("ac") or 0),
                allele_number=int(exome.get("an") or 0),
                lof=v.get("lof") or "",
            )
        )

    return records
