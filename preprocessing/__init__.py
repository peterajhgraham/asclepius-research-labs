"""
Preprocessing module for monogenic neurology variant → pathway analysis.

Submodules
----------
normalize_variants       : Canonical representation of genomic variants.
gene_to_pathway_mapping  : Map gene symbols to KEGG/Reactome pathway IDs.
ontology_normalization   : Normalize disease/phenotype ontology terms.
"""

from preprocessing.normalize_variants import (
    NormalizedVariant,
    normalize_variant,
    normalize_clinvar_records,
    normalize_gnomad_records,
    merge_variant_sources,
)
from preprocessing.gene_to_pathway_mapping import (
    GenePathwayMap,
    build_gene_pathway_map,
    lookup_pathways_for_gene,
    lookup_genes_for_pathway,
)
from preprocessing.ontology_normalization import (
    OntologyTerm,
    normalize_ontology_term,
    normalize_phenotype_ids,
    SUPPORTED_PREFIXES,
)

__all__ = [
    "NormalizedVariant",
    "normalize_variant",
    "normalize_clinvar_records",
    "normalize_gnomad_records",
    "merge_variant_sources",
    "GenePathwayMap",
    "build_gene_pathway_map",
    "lookup_pathways_for_gene",
    "lookup_genes_for_pathway",
    "OntologyTerm",
    "normalize_ontology_term",
    "normalize_phenotype_ids",
    "SUPPORTED_PREFIXES",
]
