# experiment_suggester.py
# Suggest perturbation experiments based on causal rankings and active learning.

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from causal.intervention_ranker import InterventionRanker
from optimizer.active_learning import ActiveLearner


class ExperimentSuggester:
    """End-to-end experiment suggestion engine.

    Combines causal intervention ranking with active learning to propose
    the most informative perturbation experiments given an objective and
    resource budget.

    Parameters
    ----------
    ranker:
        A configured :class:`~causal.intervention_ranker.InterventionRanker`.
        If *None*, a default ranker is used.
    learner:
        A configured :class:`~optimizer.active_learning.ActiveLearner`.
        If *None*, a default learner is used.
    """

    def __init__(
        self,
        ranker: Optional[InterventionRanker] = None,
        learner: Optional[ActiveLearner] = None,
    ) -> None:
        self._ranker = ranker or InterventionRanker()
        self._learner = learner or ActiveLearner()

    def suggest_experiments(
        self,
        objective: str,
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
        budget: int = 5,
        cell_type_context: Optional[str] = None,
        exclude: Optional[List[str]] = None,
        top_candidates: int = 50,
    ) -> List[Dict[str, Any]]:
        """Suggest perturbation experiments for a given objective.

        Workflow:

        1. Rank upstream intervention nodes using causal propagation.
        2. Initialise the active learner with causal scores as priors.
        3. Select *budget* experiments using upper-confidence bound.

        Parameters
        ----------
        objective:
            Target node to reduce/modulate (e.g. ``"TNF"``, ``"IL6"``).
        edge_list:
            Full immune graph edge list.
        budget:
            Maximum number of experiments to suggest.
        cell_type_context:
            Optional cell-type filter passed to the ranker.
        exclude:
            Node IDs already tested; excluded from suggestions.
        top_candidates:
            Number of top causal candidates to pass to the active learner.

        Returns
        -------
        list of dict
            Each dict has keys ``"rank"``, ``"node_id"``,
            ``"causal_score"``, ``"acquisition_score"``, and ``"rationale"``.
        """
        # Step 1: causal ranking
        ranked = self._ranker.rank_interventions(
            target_node=objective,
            edge_list=edge_list,
            cell_type_context=cell_type_context,
            top_k=top_candidates,
        )

        if not ranked:
            return []

        # Step 2: initialise learner with causal scores as priors
        candidates = [r["node_id"] for r in ranked]
        prior_scores = {r["node_id"]: r["score"] for r in ranked}
        self._learner.initialise_candidates(candidates, prior_scores=prior_scores)

        # Step 3: select experiments
        selected_ids = self._learner.select_experiments(
            budget=budget, exclude=exclude
        )

        # Step 4: build response
        causal_lookup = {r["node_id"]: r for r in ranked}
        belief = {b["node_id"]: b for b in self._learner.get_belief_summary()}

        suggestions = []
        for rank, nid in enumerate(selected_ids, start=1):
            causal_info = causal_lookup.get(nid, {})
            belief_info = belief.get(nid, {})
            suggestions.append(
                {
                    "rank": rank,
                    "node_id": nid,
                    "causal_score": causal_info.get("score", 0.0),
                    "acquisition_score": belief_info.get("mean", 0.0),
                    "rationale": _build_rationale(nid, causal_info, objective),
                }
            )

        return suggestions

    def record_result(self, node_id: str, observed_effect: float) -> None:
        """Record an experimental observation to update the active learner.

        Parameters
        ----------
        node_id:
            Perturbed node.
        observed_effect:
            Measured effect size (e.g. log-fold change in cytokine level).
        """
        self._learner.update(node_id, observed_effect)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_rationale(
    node_id: str,
    causal_info: Dict[str, Any],
    objective: str,
) -> str:
    """Construct a human-readable rationale string for a suggestion.

    Parameters
    ----------
    node_id:
        Suggested node.
    causal_info:
        Causal ranking info dict for the node.
    objective:
        Target objective node.

    Returns
    -------
    str
        Short rationale sentence.
    """
    prop_score = causal_info.get("propagation_score", 0.0)
    struct_score = causal_info.get("structural_score", 0.0)
    return (
        f"Perturbing '{node_id}' is predicted to modulate '{objective}' "
        f"(propagation={prop_score:.3f}, structural={struct_score:.3f})."
    )
