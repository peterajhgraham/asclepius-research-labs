"""Reciprocal Rank Fusion for combining multiple ranked retrieval lists."""

from __future__ import annotations


def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[int, float]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Fuse multiple ranked doc-id lists using RRF.

    Each element of ranked_lists is a list of (doc_index, score) pairs
    sorted by descending score.  Returns a merged list of (doc_index, rrf_score)
    sorted by descending rrf_score.

    Reference: Cormack et al. (2009). Reciprocal rank fusion outperforms
    condorcet and individual rank learning methods. SIGIR.
    """
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
