# active_learning.py
# Select perturbation experiments to maximise information gain.

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from causal.scoring_utils import entropy


class ActiveLearner:
    """Bayesian active learning strategy for perturbation experiment selection.

    Maintains a belief distribution over intervention node efficacies and
    selects experiments that maximise expected information gain (EIG) under
    a Gaussian process–inspired uncertainty model.

    Parameters
    ----------
    exploration_weight:
        Trade-off between exploitation (high expected score) and exploration
        (high uncertainty).  Higher values favour exploration.
    random_seed:
        Seed for reproducibility.
    """

    def __init__(
        self,
        exploration_weight: float = 1.0,
        random_seed: int = 42,
    ) -> None:
        self.exploration_weight = exploration_weight
        self.random_seed = random_seed
        self._rng = np.random.default_rng(random_seed)

        # Belief state: mean and variance per candidate
        self._means: Dict[str, float] = {}
        self._variances: Dict[str, float] = {}
        self._observations: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialise_candidates(
        self,
        candidates: List[str],
        prior_scores: Optional[Dict[str, float]] = None,
    ) -> None:
        """Initialise the belief distribution over candidate nodes.

        Parameters
        ----------
        candidates:
            List of node IDs that can be perturbed.
        prior_scores:
            Optional prior expected efficacy per candidate (e.g. from
            causal propagation scores).  Defaults to zero mean for all.
        """
        for cand in candidates:
            self._means[cand] = float((prior_scores or {}).get(cand, 0.0))
            self._variances[cand] = 1.0  # start with high uncertainty
            self._observations[cand] = []

    # ------------------------------------------------------------------
    # Experiment selection
    # ------------------------------------------------------------------

    def select_experiments(
        self,
        budget: int,
        exclude: Optional[List[str]] = None,
    ) -> List[str]:
        """Select the next batch of experiments using upper-confidence bound.

        Parameters
        ----------
        budget:
            Number of experiments to select.
        exclude:
            Node IDs to exclude (already run or unavailable).

        Returns
        -------
        list of str
            Selected candidate IDs ordered by acquisition score.
        """
        exclude_set = set(exclude or [])
        available = [
            c for c in self._means if c not in exclude_set
        ]

        if not available:
            return []

        # Upper confidence bound: mean + w * std
        scores = {
            c: self._means[c] + self.exploration_weight * math.sqrt(self._variances[c])
            for c in available
        }
        sorted_cands = sorted(scores, key=lambda k: scores[k], reverse=True)
        return sorted_cands[:budget]

    # ------------------------------------------------------------------
    # Belief update
    # ------------------------------------------------------------------

    def update(self, node_id: str, observation: float) -> None:
        """Update the belief for a candidate after observing an experiment result.

        Uses Bayesian update rules for a Gaussian likelihood model.

        Parameters
        ----------
        node_id:
            The node that was perturbed.
        observation:
            Observed efficacy score (e.g. log-fold change in target).
        """
        if node_id not in self._means:
            raise KeyError(f"Node '{node_id}' not in candidate set.")

        self._observations[node_id].append(observation)
        n = len(self._observations[node_id])
        obs = self._observations[node_id]

        # Online update of mean and variance
        self._means[node_id] = sum(obs) / n
        if n > 1:
            self._variances[node_id] = max(
                0.01,
                sum((x - self._means[node_id]) ** 2 for x in obs) / n,
            )
        # Reduce variance as more observations come in
        self._variances[node_id] = max(0.01, self._variances[node_id] / (1 + n * 0.1))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def expected_information_gain(self, node_id: str) -> float:
        """Estimate EIG for perturbing *node_id* under the current belief.

        Parameters
        ----------
        node_id:
            Candidate node.

        Returns
        -------
        float
            Estimated information gain in nats.
        """
        if node_id not in self._variances:
            raise KeyError(f"Node '{node_id}' not in candidate set.")
        var = self._variances[node_id]
        # EIG for a Gaussian model: 0.5 * log(var_prior / var_posterior)
        # Here approximate with current variance (higher = more to learn)
        return 0.5 * math.log(1.0 + var)

    def get_belief_summary(self) -> List[Dict[str, Any]]:
        """Return a summary of the current belief state.

        Returns
        -------
        list of dict
            Sorted by mean score descending.  Each dict has keys
            ``"node_id"``, ``"mean"``, ``"variance"``, ``"n_observations"``.
        """
        summary = [
            {
                "node_id": c,
                "mean": self._means[c],
                "variance": self._variances[c],
                "n_observations": len(self._observations[c]),
            }
            for c in self._means
        ]
        summary.sort(key=lambda x: x["mean"], reverse=True)
        return summary
