# propagation.py
# Probabilistic causal signal propagation over the immune signaling graph.

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np


class CausalPropagator:
    """Propagate causal signals through the immune signaling graph.

    Implements a probabilistic belief propagation algorithm that diffuses
    activation or inhibition signals from a set of seed nodes through the
    graph, weighted by edge confidence scores.

    Parameters
    ----------
    decay:
        Signal decay factor applied at each hop (0 < decay ≤ 1).  Lower
        values confine the signal closer to the seed nodes.
    max_iterations:
        Maximum number of propagation steps.
    convergence_threshold:
        Absolute change in any node score below which propagation stops.
    """

    def __init__(
        self,
        decay: float = 0.85,
        max_iterations: int = 50,
        convergence_threshold: float = 1e-5,
    ) -> None:
        if not 0 < decay <= 1:
            raise ValueError("decay must be in (0, 1].")
        self.decay = decay
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold

    def propagate(
        self,
        seed_scores: Dict[str, float],
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
        direction: str = "downstream",
    ) -> Dict[str, float]:
        """Run signal propagation from seed nodes.

        Parameters
        ----------
        seed_scores:
            Initial signal values keyed by node ID.  Positive values
            represent activating signals; negative values represent
            inhibitory signals.
        edge_list:
            Graph edges as ``(source, target, edge_type, metadata)`` tuples.
        direction:
            ``"downstream"`` (signals flow source → target),
            ``"upstream"`` (signals flow target → source), or
            ``"both"``.

        Returns
        -------
        dict
            Mapping from node ID to propagated score.
        """
        # Build weighted adjacency dict
        adj = self._build_weighted_adj(edge_list, direction)

        # Initialise scores
        scores: Dict[str, float] = defaultdict(float)
        for nid, val in seed_scores.items():
            scores[nid] = val

        for iteration in range(self.max_iterations):
            new_scores: Dict[str, float] = dict(scores)
            max_delta = 0.0

            for source, targets in adj.items():
                source_score = scores.get(source, 0.0)
                if source_score == 0.0:
                    continue
                for target, weight in targets:
                    contribution = self.decay * source_score * weight
                    new_val = new_scores.get(target, 0.0) + contribution
                    delta = abs(new_val - new_scores.get(target, 0.0))
                    new_scores[target] = new_val
                    max_delta = max(max_delta, delta)

            scores = new_scores
            if max_delta < self.convergence_threshold:
                break

        return dict(scores)

    def _build_weighted_adj(
        self,
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
        direction: str,
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Build a weighted adjacency list respecting edge semantics.

        ``activates`` edges propagate the signal unmodified.
        ``inhibits`` edges propagate the negated signal.

        Parameters
        ----------
        edge_list:
            Graph edges.
        direction:
            Propagation direction.

        Returns
        -------
        dict
            Mapping source → list of (target, signed_weight).
        """
        adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

        for src, tgt, etype, meta in edge_list:
            conf = float(meta.get("confidence_score", 0.5))
            sign = -1.0 if etype == "inhibits" else 1.0
            weight = sign * conf

            if direction in ("downstream", "both"):
                adj[src].append((tgt, weight))
            if direction in ("upstream", "both"):
                adj[tgt].append((src, weight))

        return adj
