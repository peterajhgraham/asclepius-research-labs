"""
Core data model for variant → pathway inference.

A :class:`VariantPathwayGraph` connects :class:`NormalizedVariant` objects to
the biological pathways their host genes participate in, forming the backbone
of the variant → pathway MVP.

Design
------
- One variant can link to multiple pathways (via its gene).
- One pathway can be linked to by many variants.
- Each link is represented by a :class:`VariantPathwayLink`.
- The graph also stores pathway names and gene membership counts for
  downstream scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from preprocessing.normalize_variants import NormalizedVariant
from preprocessing.gene_to_pathway_mapping import GenePathwayMap, lookup_pathways_for_gene


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class VariantPathwayLink:
    """A single edge connecting a variant to a pathway via a gene.

    Attributes
    ----------
    variant_key : str
        Canonical variant identifier (``chrom:pos:ref:alt``).
    gene_symbol : str
        HGNC gene symbol shared by the variant and pathway.
    pathway_id : str
        Target pathway identifier (KEGG or Reactome).
    pathway_name : str
        Human-readable pathway name.
    clinical_significance : str
        Clinical significance of the variant (from ClinVar, if available).
    allele_frequency : float
        Population allele frequency (0–1).
    lof : str
        Loss-of-function annotation (``"HC"`` = high-confidence LoF).
    source : str
        Originating data source (``"ClinVar"``, ``"gnomAD"``, etc.).
    """

    variant_key: str
    gene_symbol: str
    pathway_id: str
    pathway_name: str
    clinical_significance: str = ""
    allele_frequency: float = 0.0
    lof: str = ""
    source: str = ""


@dataclass
class VariantPathwayGraph:
    """Bipartite graph of variants ↔ pathways, mediated by genes.

    Attributes
    ----------
    links : list of VariantPathwayLink
        All variant–pathway edges in the graph.
    variants : dict
        ``{variant_key: NormalizedVariant}`` lookup.
    pathway_gene_counts : dict
        ``{pathway_id: int}`` – total number of genes annotated to each pathway
        in the reference gene set.  Used for burden normalisation.
    """

    links: List[VariantPathwayLink] = field(default_factory=list)
    variants: Dict[str, NormalizedVariant] = field(default_factory=dict)
    pathway_gene_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def variant_count(self) -> int:
        """Number of unique variants in the graph."""
        return len(self.variants)

    @property
    def pathway_count(self) -> int:
        """Number of unique pathways with at least one linked variant."""
        return len({link.pathway_id for link in self.links})

    def links_for_variant(self, variant_key: str) -> List[VariantPathwayLink]:
        """Return all pathway links for a specific variant.

        Parameters
        ----------
        variant_key : str
            Canonical ``chrom:pos:ref:alt`` key.

        Returns
        -------
        list of VariantPathwayLink
        """
        return [link for link in self.links if link.variant_key == variant_key]

    def links_for_pathway(self, pathway_id: str) -> List[VariantPathwayLink]:
        """Return all variant links for a specific pathway.

        Parameters
        ----------
        pathway_id : str
            Pathway identifier (KEGG or Reactome).

        Returns
        -------
        list of VariantPathwayLink
        """
        return [link for link in self.links if link.pathway_id == pathway_id]


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_variant_pathway_graph(
    variants: List[NormalizedVariant],
    gene_map: GenePathwayMap,
) -> VariantPathwayGraph:
    """Construct a :class:`VariantPathwayGraph` by joining variants to pathways.

    For each variant, the variant's ``gene_symbol`` is looked up in
    *gene_map*.  A :class:`VariantPathwayLink` is created for every pathway
    the gene participates in.

    Parameters
    ----------
    variants : list of NormalizedVariant
        Normalised variants from :mod:`preprocessing.normalize_variants`.
    gene_map : GenePathwayMap
        Gene → pathway index from
        :func:`~preprocessing.gene_to_pathway_mapping.build_gene_pathway_map`.

    Returns
    -------
    VariantPathwayGraph
    """
    links: List[VariantPathwayLink] = []
    variant_lookup: Dict[str, NormalizedVariant] = {}

    for variant in variants:
        variant_lookup[variant.key] = variant
        pathway_ids = lookup_pathways_for_gene(gene_map, variant.gene_symbol)

        for pid in pathway_ids:
            links.append(
                VariantPathwayLink(
                    variant_key=variant.key,
                    gene_symbol=variant.gene_symbol,
                    pathway_id=pid,
                    pathway_name=gene_map.pathway_names.get(pid, ""),
                    clinical_significance=variant.clinical_significance,
                    allele_frequency=variant.allele_frequency,
                    lof=variant.lof,
                    source=variant.source,
                )
            )

    # Populate pathway gene counts for burden normalisation
    pathway_gene_counts = {
        pid: len(genes)
        for pid, genes in gene_map.pathway_to_genes.items()
    }

    return VariantPathwayGraph(
        links=links,
        variants=variant_lookup,
        pathway_gene_counts=pathway_gene_counts,
    )
