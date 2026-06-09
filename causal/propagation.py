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
        # Build weighted adjacency dict (out-degree normalised, see below)
        adj = self._build_weighted_adj(edge_list, direction)

        # Bounded diffusion via the linear recurrence
        #
        #     x_{t+1}[n] = seed[n] + decay * Σ_{m→n} W[m→n] · x_t[m]
        #
        # i.e. the seed signal is *re-injected* every iteration and each hop
        # attenuates by ``decay``. Because the per-source weights are L1
        # normalised in ``_build_weighted_adj`` (Σ_m |W[m→n contributions]| ≤ 1
        # out of every node), the propagation operator is sub-stochastic and the
        # recurrence is a contraction with factor ``decay`` < 1. It therefore
        # converges to the bounded fixed point ``(I − decay·W)⁻¹ · seed``.
        #
        # The previous implementation instead *accumulated* contributions on top
        # of the carried-over scores without resetting or normalising, so in any
        # graph with cycles (which the immune signalling graph is full of) the
        # scores compounded every iteration and diverged to ~1e21 / inf — the
        # ``convergence_threshold`` never tripped because the deltas kept growing.
        scores: Dict[str, float] = {nid: float(val) for nid, val in seed_scores.items()}

        for _ in range(self.max_iterations):
            # Re-inject the seed each step; non-seed nodes start from zero and are
            # rebuilt purely from this iteration's propagated inflow.
            new_scores: Dict[str, float] = {nid: float(val) for nid, val in seed_scores.items()}

            for source, targets in adj.items():
                source_score = scores.get(source, 0.0)
                if source_score == 0.0:
                    continue
                contribution_base = self.decay * source_score
                for target, weight in targets:
                    new_scores[target] = new_scores.get(target, 0.0) + contribution_base * weight

            max_delta = 0.0
            for node in set(new_scores) | set(scores):
                max_delta = max(max_delta, abs(new_scores.get(node, 0.0) - scores.get(node, 0.0)))

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

        Outgoing weights are **L1 normalised per source** so the magnitudes
        leaving any node sum to at most 1. This keeps the propagation operator
        sub-stochastic, which is what guarantees the diffusion in
        :meth:`propagate` converges instead of compounding around cycles. The
        sign (activation vs. inhibition) is preserved; only the magnitude is
        scaled.

        Parameters
        ----------
        edge_list:
            Graph edges.
        direction:
            Propagation direction.

        Returns
        -------
        dict
            Mapping source → list of (target, normalised_signed_weight).
        """
        raw: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

        for src, tgt, etype, meta in edge_list:
            conf = float(meta.get("confidence_score", 0.5))
            sign = -1.0 if etype == "inhibits" else 1.0
            weight = sign * conf

            if direction in ("downstream", "both"):
                raw[src].append((tgt, weight))
            if direction in ("upstream", "both"):
                raw[tgt].append((src, weight))

        adj: Dict[str, List[Tuple[str, float]]] = {}
        for source, targets in raw.items():
            total = sum(abs(w) for _, w in targets)
            if total <= 0:
                adj[source] = targets
            else:
                adj[source] = [(tgt, w / total) for tgt, w in targets]

        return adj
