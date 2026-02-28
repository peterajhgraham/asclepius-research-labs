# scoring_utils.py
# Utility functions for scoring and ranking immune signaling nodes.

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np


def normalize_scores(
    scores: Dict[str, float],
    method: str = "minmax",
) -> Dict[str, float]:
    """Normalize a dictionary of raw scores.

    Parameters
    ----------
    scores:
        Mapping from node ID to raw score.
    method:
        Normalization method: ``"minmax"`` (default), ``"zscore"``, or
        ``"softmax"``.

    Returns
    -------
    dict
        Normalized scores in the same key order.

    Raises
    ------
    ValueError
        If *method* is not recognised.
    """
    if not scores:
        return {}

    keys = list(scores.keys())
    values = np.array([scores[k] for k in keys], dtype=float)

    if method == "minmax":
        v_min, v_max = values.min(), values.max()
        span = v_max - v_min
        normed = (values - v_min) / span if span > 0 else np.zeros_like(values)
    elif method == "zscore":
        std = values.std()
        normed = (values - values.mean()) / std if std > 0 else np.zeros_like(values)
    elif method == "softmax":
        shifted = values - values.max()
        exp_v = np.exp(shifted)
        normed = exp_v / exp_v.sum()
    else:
        raise ValueError(f"Unknown normalization method '{method}'. Use 'minmax', 'zscore', or 'softmax'.")

    return {k: float(v) for k, v in zip(keys, normed)}


def compute_influence_score(
    node_id: str,
    propagation_scores: Dict[str, float],
    out_degree: int,
    embedding_centrality: Optional[float] = None,
    alpha: float = 0.5,
    beta: float = 0.3,
    gamma: float = 0.2,
) -> float:
    """Compute a composite influence score for a candidate intervention node.

    The score combines three components:

    * **propagation**: how strongly the node's signal reaches the target
    * **structural**: how many outgoing edges the node has (out-degree)
    * **embedding**: optional embedding-based centrality estimate

    Parameters
    ----------
    node_id:
        Identifier of the node to score.
    propagation_scores:
        Output of :meth:`~causal.propagation.CausalPropagator.propagate`.
    out_degree:
        Out-degree of the node in the graph.
    embedding_centrality:
        Optional embedding-derived centrality (e.g. mean cosine similarity
        to all other nodes).  If *None*, the embedding term is dropped and
        *alpha* and *beta* are re-normalized.
    alpha:
        Weight for the propagation component.
    beta:
        Weight for the structural component.
    gamma:
        Weight for the embedding component (only used when
        *embedding_centrality* is provided).

    Returns
    -------
    float
        Composite influence score.
    """
    prop_val = abs(propagation_scores.get(node_id, 0.0))
    struct_val = math.log1p(out_degree)

    if embedding_centrality is None:
        total_w = alpha + beta
        return (alpha * prop_val + beta * struct_val) / total_w if total_w > 0 else 0.0

    total_w = alpha + beta + gamma
    return (
        alpha * prop_val
        + beta * struct_val
        + gamma * embedding_centrality
    ) / total_w


def compute_confidence_weighted_score(
    edge_list: List[Any],
    target_node: str,
) -> Dict[str, float]:
    """Aggregate confidence-weighted evidence for each node as it relates to *target_node*.

    Sums the ``confidence_score`` of all edges where the source or target
    is the given *target_node*, returning a score per connected node.

    Parameters
    ----------
    edge_list:
        Graph edges as ``(source, target, edge_type, metadata)`` tuples.
    target_node:
        The node to compute evidence scores relative to.

    Returns
    -------
    dict
        Mapping from neighbour node ID to aggregated confidence score.
    """
    scores: Dict[str, float] = {}
    for src, tgt, _, meta in edge_list:
        conf = float(meta.get("confidence_score", 0.5))
        if src == target_node:
            scores[tgt] = scores.get(tgt, 0.0) + conf
        elif tgt == target_node:
            scores[src] = scores.get(src, 0.0) + conf
    return scores


def entropy(probs: List[float]) -> float:
    """Compute Shannon entropy of a probability distribution.

    Parameters
    ----------
    probs:
        List of probability values (should sum to ~1).

    Returns
    -------
    float
        Entropy in nats.
    """
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log(p)
    return h
