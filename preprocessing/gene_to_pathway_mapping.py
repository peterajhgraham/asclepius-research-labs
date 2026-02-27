"""
Map gene symbols to biological pathways (KEGG and Reactome).

This module builds and queries an in-memory gene → pathway index constructed
from :class:`~data_ingestion.load_pathways.Pathway` objects loaded by the
ingestion layer.

Typical usage
-------------
>>> from data_ingestion.load_pathways import load_kegg_pathways
>>> from preprocessing.gene_to_pathway_mapping import build_gene_pathway_map

>>> pathways = load_kegg_pathways("hsa", fetch_genes=True)
>>> gene_map = build_gene_pathway_map(pathways)
>>> print(lookup_pathways_for_gene(gene_map, "LRRK2"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from utils.helpers import normalise_gene_symbol


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GenePathwayMap:
    """Bidirectional index mapping genes ↔ pathways.

    Attributes
    ----------
    gene_to_pathways : dict
        ``{gene_symbol: [pathway_id, ...]}``.
    pathway_to_genes : dict
        ``{pathway_id: [gene_symbol, ...]}``.
    pathway_names : dict
        ``{pathway_id: pathway_name}`` for display purposes.
    """

    gene_to_pathways: Dict[str, List[str]] = field(default_factory=dict)
    pathway_to_genes: Dict[str, List[str]] = field(default_factory=dict)
    pathway_names: Dict[str, str] = field(default_factory=dict)

    @property
    def gene_count(self) -> int:
        """Number of unique genes in the map."""
        return len(self.gene_to_pathways)

    @property
    def pathway_count(self) -> int:
        """Number of unique pathways in the map."""
        return len(self.pathway_to_genes)


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

def build_gene_pathway_map(pathways: list) -> GenePathwayMap:
    """Build a :class:`GenePathwayMap` from a list of pathway objects.

    Parameters
    ----------
    pathways : list of Pathway
        Pathway records returned by
        :func:`~data_ingestion.load_pathways.load_kegg_pathways` or
        :func:`~data_ingestion.load_pathways.load_reactome_pathways`.
        Each pathway must have a populated ``gene_symbols`` list.

    Returns
    -------
    GenePathwayMap
    """
    gene_to_pathways: Dict[str, Set[str]] = {}
    pathway_to_genes: Dict[str, List[str]] = {}
    pathway_names: Dict[str, str] = {}

    for pathway in pathways:
        pid = pathway.pathway_id
        pathway_names[pid] = pathway.name

        clean_genes: List[str] = [
            normalise_gene_symbol(g) for g in pathway.gene_symbols if g
        ]
        pathway_to_genes[pid] = clean_genes

        for gene in clean_genes:
            gene_to_pathways.setdefault(gene, set()).add(pid)

    return GenePathwayMap(
        gene_to_pathways={g: sorted(pids) for g, pids in gene_to_pathways.items()},
        pathway_to_genes=pathway_to_genes,
        pathway_names=pathway_names,
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def lookup_pathways_for_gene(
    gene_map: GenePathwayMap,
    gene_symbol: str,
) -> List[str]:
    """Return pathway IDs associated with *gene_symbol*.

    Parameters
    ----------
    gene_map : GenePathwayMap
        Index built by :func:`build_gene_pathway_map`.
    gene_symbol : str
        HGNC gene symbol (case-insensitive).

    Returns
    -------
    list of str
        Sorted pathway IDs, or an empty list if the gene is not in the index.
    """
    clean = normalise_gene_symbol(gene_symbol)
    return gene_map.gene_to_pathways.get(clean, [])


def lookup_genes_for_pathway(
    gene_map: GenePathwayMap,
    pathway_id: str,
) -> List[str]:
    """Return gene symbols in *pathway_id*.

    Parameters
    ----------
    gene_map : GenePathwayMap
        Index built by :func:`build_gene_pathway_map`.
    pathway_id : str
        Pathway identifier (e.g. ``"hsa05012"`` or ``"R-HSA-168928"``).

    Returns
    -------
    list of str
        Gene symbols in the pathway, or an empty list if not found.
    """
    return gene_map.pathway_to_genes.get(pathway_id, [])
