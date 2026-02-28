# intervention_ranker.py
# Rank graph nodes by their potential impact when perturbed.

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .propagation import CausalPropagator
from .scoring_utils import normalize_scores


class InterventionRanker:
    """Rank upstream intervention points for a target signal.

    Combines causal propagation scores with graph structural features
    (out-degree) to identify nodes whose perturbation is most likely to
    modulate the target.

    Parameters
    ----------
    propagator:
        A configured :class:`~causal.propagation.CausalPropagator` instance.
        If *None*, a default propagator is used.
    structural_weight:
        Weight applied to the structural (degree) component of the final
        score.  The propagation component receives weight
        ``1 - structural_weight``.
    """

    def __init__(
        self,
        propagator: Optional[CausalPropagator] = None,
        structural_weight: float = 0.3,
    ) -> None:
        self._propagator = propagator or CausalPropagator()
        self.structural_weight = structural_weight

    def rank_interventions(
        self,
        target_node: str,
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
        cell_type_context: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rank nodes by expected influence on *target_node*.

        Parameters
        ----------
        target_node:
            The node whose activation we wish to modulate (e.g. a
            pro-inflammatory cytokine such as ``"TNF"``).
        edge_list:
            Full graph edge list.
        cell_type_context:
            Optional cell-type filter.  Only edges with matching
            ``cell_type_context`` metadata (or no context set) are used.
        top_k:
            Return only the top *k* ranked nodes.  If *None*, all nodes
            are returned.

        Returns
        -------
        list of dict
            Sorted by ``"score"`` descending.  Each dict has keys:
            ``"node_id"``, ``"score"``, ``"propagation_score"``,
            ``"structural_score"``.
        """
        # Filter edges by cell-type context if requested
        filtered = _filter_by_context(edge_list, cell_type_context)

        # Step 1: upstream propagation from target
        seed = {target_node: 1.0}
        prop_scores = self._propagator.propagate(
            seed, filtered, direction="upstream"
        )
        prop_scores.pop(target_node, None)

        # Step 2: structural scores (out-degree normalised)
        out_degree = _compute_out_degree(filtered)
        max_degree = max(out_degree.values(), default=1)
        struct_scores = {
            nid: deg / max_degree for nid, deg in out_degree.items()
        }

        # Step 3: combine
        all_nodes = set(prop_scores) | set(struct_scores)
        combined: List[Dict[str, Any]] = []
        for nid in all_nodes:
            if nid == target_node:
                continue
            p_score = abs(prop_scores.get(nid, 0.0))
            s_score = struct_scores.get(nid, 0.0)
            final = (
                (1 - self.structural_weight) * p_score
                + self.structural_weight * s_score
            )
            combined.append(
                {
                    "node_id": nid,
                    "score": final,
                    "propagation_score": p_score,
                    "structural_score": s_score,
                }
            )

        combined.sort(key=lambda x: x["score"], reverse=True)

        if top_k is not None:
            combined = combined[:top_k]

        return combined


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_by_context(
    edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
    cell_type_context: Optional[str],
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Return edges matching the given cell-type context.

    Parameters
    ----------
    edge_list:
        All graph edges.
    cell_type_context:
        Cell type to filter by.  If *None*, the full edge list is returned.

    Returns
    -------
    Filtered edge list.
    """
    if cell_type_context is None:
        return edge_list
    return [
        e for e in edge_list
        if e[3].get("cell_type_context") in (None, cell_type_context)
    ]


def _compute_out_degree(
    edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
) -> Dict[str, int]:
    """Compute out-degree for all nodes.

    Parameters
    ----------
    edge_list:
        Graph edges.

    Returns
    -------
    dict
        Mapping node ID → out-degree.
    """
    degree: Dict[str, int] = {}
    for src, _, _, _ in edge_list:
        degree[src] = degree.get(src, 0) + 1
    return degree
