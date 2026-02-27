"""
Data ingestion module for monogenic neurology variant analysis.

Loaders:
- load_clinvar    : ClinVar variant-disease associations
- load_gnomad     : gnomAD population variant frequencies
- load_pathways   : KEGG and Reactome biological pathways
"""

from data_ingestion.load_clinvar import ClinVarRecord, load_clinvar_tsv
from data_ingestion.load_gnomad import GnomadRecord, load_gnomad_tsv, fetch_gnomad_gene_variants
from data_ingestion.load_pathways import Pathway, load_kegg_pathways, load_reactome_pathways

__all__ = [
    "ClinVarRecord",
    "load_clinvar_tsv",
    "GnomadRecord",
    "load_gnomad_tsv",
    "fetch_gnomad_gene_variants",
    "Pathway",
    "load_kegg_pathways",
    "load_reactome_pathways",
]
