"""
Load biological pathway data from KEGG and Reactome.

Supported sources
-----------------
- **KEGG REST API** (https://rest.kegg.jp) – free, no authentication required.
- **Reactome REST API** (https://reactome.org/ContentService) – free.

Typical usage
-------------
>>> from data_ingestion.load_pathways import load_kegg_pathways
>>> pathways = load_kegg_pathways("hsa")           # human KEGG pathways
>>> print(pathways[0])

>>> from data_ingestion.load_pathways import load_reactome_pathways
>>> pathways = load_reactome_pathways("9606")       # human Reactome pathways
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Pathway:
    """A biological pathway record.

    Attributes
    ----------
    pathway_id : str
        Source-specific identifier (e.g. ``"hsa05012"`` for KEGG or
        ``"R-HSA-168928"`` for Reactome).
    name : str
        Human-readable pathway name.
    source : str
        Database of origin (``"KEGG"`` or ``"Reactome"``).
    gene_symbols : list of str
        HGNC gene symbols annotated to this pathway.
    description : str
        Optional free-text description.
    extra : dict
        Any additional metadata returned by the source API.
    """

    pathway_id: str
    name: str
    source: str
    gene_symbols: List[str] = field(default_factory=list)
    description: str = ""
    extra: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# KEGG loader
# ---------------------------------------------------------------------------

KEGG_BASE_URL = "https://rest.kegg.jp"


def load_kegg_pathways(
    organism: str = "hsa",
    *,
    fetch_genes: bool = True,
    timeout: int = 30,
    max_pathways: Optional[int] = None,
) -> List[Pathway]:
    """Retrieve KEGG pathway list and associated genes for an organism.

    Parameters
    ----------
    organism : str
        KEGG organism code (default ``"hsa"`` for *Homo sapiens*).
    fetch_genes : bool
        If ``True`` (default), make an additional request for each pathway
        to retrieve its gene set.  Set to ``False`` for a faster listing
        without gene membership data.
    timeout : int
        HTTP request timeout in seconds.
    max_pathways : int, optional
        Stop after loading this many pathways.  Useful for quick tests.

    Returns
    -------
    list of Pathway

    Raises
    ------
    ImportError
        If ``requests`` is not installed.
    """
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "requests is required for KEGG API queries: pip install requests"
        ) from exc

    # 1. Fetch pathway list
    list_url = f"{KEGG_BASE_URL}/list/pathway/{organism}"
    response = requests.get(list_url, timeout=timeout)
    response.raise_for_status()

    pathways: List[Pathway] = []
    for line in response.text.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t", 1)
        pathway_id = parts[0].strip()          # e.g. "path:hsa05012"
        name = parts[1].strip() if len(parts) > 1 else ""

        # Remove "path:" prefix for clean IDs
        clean_id = pathway_id.replace("path:", "")

        pathway = Pathway(pathway_id=clean_id, name=name, source="KEGG")
        pathways.append(pathway)

        if max_pathways is not None and len(pathways) >= max_pathways:
            break

    # 2. Optionally enrich with gene membership
    if fetch_genes:
        for pathway in pathways:
            _fetch_kegg_pathway_genes(pathway, organism=organism, timeout=timeout)

    return pathways


def _fetch_kegg_pathway_genes(
    pathway: Pathway,
    *,
    organism: str = "hsa",
    timeout: int = 30,
) -> None:
    """Populate ``pathway.gene_symbols`` by querying the KEGG entry endpoint.

    This function mutates *pathway* in-place.
    """
    try:
        import requests
    except ImportError:
        return

    url = f"{KEGG_BASE_URL}/get/{pathway.pathway_id}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return

    gene_symbols: List[str] = []
    in_gene_section = False
    for line in response.text.splitlines():
        if line.startswith("GENE"):
            in_gene_section = True
        elif in_gene_section:
            if line.startswith(" "):
                # Format: "  ENSGXXX  SYMBOL; ..."
                tokens = line.split()
                if len(tokens) >= 2:
                    symbol = tokens[1].rstrip(";")
                    gene_symbols.append(symbol)
            else:
                break

    pathway.gene_symbols = gene_symbols


# ---------------------------------------------------------------------------
# Reactome loader
# ---------------------------------------------------------------------------

REACTOME_BASE_URL = "https://reactome.org/ContentService"


def load_reactome_pathways(
    species_taxon: str = "9606",
    *,
    timeout: int = 30,
    max_pathways: Optional[int] = None,
) -> List[Pathway]:
    """Retrieve top-level Reactome pathways for a species.

    Parameters
    ----------
    species_taxon : str
        NCBI taxonomy ID (default ``"9606"`` for *Homo sapiens*).
    timeout : int
        HTTP request timeout in seconds.
    max_pathways : int, optional
        Stop after loading this many pathways.

    Returns
    -------
    list of Pathway

    Raises
    ------
    ImportError
        If ``requests`` is not installed.
    """
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "requests is required for Reactome API queries: pip install requests"
        ) from exc

    url = f"{REACTOME_BASE_URL}/data/pathways/top/{species_taxon}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    raw_pathways = response.json()
    pathways: List[Pathway] = []

    for item in raw_pathways:
        pathway = Pathway(
            pathway_id=item.get("stId", ""),
            name=item.get("displayName", ""),
            source="Reactome",
            description=item.get("name", ""),
        )
        pathways.append(pathway)

        if max_pathways is not None and len(pathways) >= max_pathways:
            break

    return pathways


def fetch_reactome_pathway_genes(
    pathway_id: str,
    *,
    timeout: int = 30,
) -> List[str]:
    """Return the list of gene symbols in a Reactome pathway.

    Parameters
    ----------
    pathway_id : str
        Reactome stable identifier (e.g. ``"R-HSA-168928"``).
    timeout : int
        HTTP request timeout in seconds.

    Returns
    -------
    list of str
        HGNC gene symbols participating in the pathway.
    """
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "requests is required for Reactome API queries: pip install requests"
        ) from exc

    url = f"{REACTOME_BASE_URL}/data/pathway/{pathway_id}/participatingMolecules"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    participants = response.json()
    gene_symbols: List[str] = []
    for p in participants:
        # Each participant may have a geneNames list
        for gene in p.get("geneNames", []):
            if gene and gene not in gene_symbols:
                gene_symbols.append(gene)

    return gene_symbols
