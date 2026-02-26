"""
Pathway impact scoring for variant → pathway inference.

Scoring strategy
----------------
Each variant linked to a pathway contributes a weight determined by its
clinical annotation:

===================  ======  =====================================
Variant class        Weight  Criteria
===================  ======  =====================================
High-confidence LoF  2.0     ``lof == "HC"``
Pathogenic           1.0     ``clinical_significance`` in pathogenic set
Likely pathogenic    1.0     ``clinical_significance`` in pathogenic set
VUS                  0.1     Variant of Uncertain Significance
Benign               0.0     Excluded from scoring
===================  ======  =====================================

The raw score is the sum of variant weights.  An optional
**burden-normalised** score divides by the log of the total gene count in
the pathway, reducing bias towards large pathways.

Typical usage
-------------
>>> from models.scoring import rank_pathways
>>> ranked = rank_pathways(graph)
>>> for ps in ranked[:5]:
...     print(ps.pathway_id, ps.score)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from models.variant_pathway_model import VariantPathwayGraph, VariantPathwayLink
from utils.config import Config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = Config()

_PATHOGENIC_SET: frozenset[str] = frozenset(
    s.lower() for s in _DEFAULT_CONFIG.PATHOGENIC_SIGNIFICANCES
)
_BENIGN_SET: frozenset[str] = frozenset({
    "benign",
    "likely benign",
    "benign/likely benign",
})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PathwayScore:
    """Aggregated impact score for a single pathway.

    Attributes
    ----------
    pathway_id : str
        Pathway identifier.
    pathway_name : str
        Human-readable pathway name.
    score : float
        Raw aggregated variant-weight score.
    normalised_score : float
        Score divided by ``log2(pathway_gene_count + 1)`` to reduce size bias.
    variant_count : int
        Number of unique variants contributing to this score.
    gene_count : int
        Number of unique genes with at least one contributing variant.
    pathway_gene_count : int
        Total genes annotated to this pathway in the reference gene set.
    """

    pathway_id: str
    pathway_name: str
    score: float
    normalised_score: float
    variant_count: int
    gene_count: int
    pathway_gene_count: int


# ---------------------------------------------------------------------------
# Per-variant weight
# ---------------------------------------------------------------------------

def _variant_weight(
    link: VariantPathwayLink,
    *,
    lof_weight: float = _DEFAULT_CONFIG.LOF_WEIGHT,
    pathogenic_weight: float = _DEFAULT_CONFIG.PATHOGENIC_WEIGHT,
    vus_weight: float = _DEFAULT_CONFIG.VUS_WEIGHT,
) -> float:
    """Return the scoring weight for a single variant link.

    Parameters
    ----------
    link : VariantPathwayLink
        A single variant–pathway edge.
    lof_weight : float
        Weight for high-confidence loss-of-function variants.
    pathogenic_weight : float
        Weight for pathogenic / likely pathogenic variants.
    vus_weight : float
        Weight for variants of uncertain significance.

    Returns
    -------
    float
        Non-negative weight.
    """
    # High-confidence LoF takes precedence
    if link.lof == "HC":
        return lof_weight

    sig_lower = link.clinical_significance.lower()

    # Benign variants contribute zero
    if sig_lower in _BENIGN_SET:
        return 0.0

    if sig_lower in _PATHOGENIC_SET:
        return pathogenic_weight

    # Default: treat as VUS
    return vus_weight


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_pathway(
    graph: VariantPathwayGraph,
    pathway_id: str,
    *,
    lof_weight: Optional[float] = None,
    pathogenic_weight: Optional[float] = None,
    vus_weight: Optional[float] = None,
) -> PathwayScore:
    """Compute the impact score for a single pathway.

    Parameters
    ----------
    graph : VariantPathwayGraph
        Variant–pathway graph from
        :func:`~models.variant_pathway_model.build_variant_pathway_graph`.
    pathway_id : str
        Pathway identifier to score.
    lof_weight : float, optional
        Override the default LoF weight.
    pathogenic_weight : float, optional
        Override the default pathogenic weight.
    vus_weight : float, optional
        Override the default VUS weight.

    Returns
    -------
    PathwayScore
    """
    kw: dict = {}
    if lof_weight is not None:
        kw["lof_weight"] = lof_weight
    if pathogenic_weight is not None:
        kw["pathogenic_weight"] = pathogenic_weight
    if vus_weight is not None:
        kw["vus_weight"] = vus_weight

    links = graph.links_for_pathway(pathway_id)
    if not links:
        return PathwayScore(
            pathway_id=pathway_id,
            pathway_name="",
            score=0.0,
            normalised_score=0.0,
            variant_count=0,
            gene_count=0,
            pathway_gene_count=graph.pathway_gene_counts.get(pathway_id, 0),
        )

    total_weight = sum(_variant_weight(link, **kw) for link in links)

    unique_variants = len({link.variant_key for link in links})
    unique_genes = len({link.gene_symbol for link in links})
    pathway_gene_count = graph.pathway_gene_counts.get(pathway_id, 1)
    pathway_name = links[0].pathway_name

    # Burden normalisation: divide by log2(pathway_size + 1)
    denom = math.log2(pathway_gene_count + 1)
    normalised = total_weight / denom if denom > 0 else 0.0

    return PathwayScore(
        pathway_id=pathway_id,
        pathway_name=pathway_name,
        score=total_weight,
        normalised_score=normalised,
        variant_count=unique_variants,
        gene_count=unique_genes,
        pathway_gene_count=pathway_gene_count,
    )


def rank_pathways(
    graph: VariantPathwayGraph,
    *,
    use_normalised: bool = True,
    min_score: float = 0.0,
    lof_weight: Optional[float] = None,
    pathogenic_weight: Optional[float] = None,
    vus_weight: Optional[float] = None,
) -> List[PathwayScore]:
    """Rank all pathways in *graph* by their variant impact score.

    Parameters
    ----------
    graph : VariantPathwayGraph
        Variant–pathway graph.
    use_normalised : bool
        If ``True`` (default), sort by ``normalised_score`` to reduce size
        bias.  If ``False``, sort by raw ``score``.
    min_score : float
        Exclude pathways whose score is at or below this threshold.
    lof_weight : float, optional
        Override LoF weight.
    pathogenic_weight : float, optional
        Override pathogenic weight.
    vus_weight : float, optional
        Override VUS weight.

    Returns
    -------
    list of PathwayScore
        Pathways sorted in descending order of score.
    """
    kw: dict = {}
    if lof_weight is not None:
        kw["lof_weight"] = lof_weight
    if pathogenic_weight is not None:
        kw["pathogenic_weight"] = pathogenic_weight
    if vus_weight is not None:
        kw["vus_weight"] = vus_weight

    unique_pathway_ids = {link.pathway_id for link in graph.links}
    scores: List[PathwayScore] = [
        score_pathway(graph, pid, **kw) for pid in unique_pathway_ids
    ]

    sort_key = "normalised_score" if use_normalised else "score"
    scores = [ps for ps in scores if getattr(ps, sort_key) > min_score]
    scores.sort(key=lambda ps: getattr(ps, sort_key), reverse=True)

    return scores
