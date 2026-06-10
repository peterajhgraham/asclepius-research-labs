"""Tests for causal signal propagation.

The regression these guard against: on a graph with cycles (which the immune
signalling graph always is), the propagation used to accumulate contributions
every iteration without bounding them, so scores diverged to ~1e21 / inf and the
``causal_propagate`` agent tool returned garbage (or an error) instead of a
ranked downstream impact list.

Run with: pytest tests/test_propagation.py -v
"""

from __future__ import annotations

import math

from app.kg.propagation import CausalPropagator


def _meta(conf: float = 0.8) -> dict:
    return {"confidence_score": conf}


def _cyclic_graph() -> list[tuple[str, str, str, dict]]:
    """A small graph with a feedback loop A→B→C→A plus a branch."""
    return [
        ("A", "B", "activates", _meta()),
        ("B", "C", "activates", _meta()),
        ("C", "A", "activates", _meta()),  # cycle back to the seed
        ("B", "D", "activates", _meta()),
        ("C", "E", "inhibits", _meta()),
    ]


def test_propagation_converges_on_cyclic_graph():
    """Scores must stay finite and bounded even with feedback loops."""
    prop = CausalPropagator(decay=0.85, max_iterations=50)
    scores = prop.propagate({"A": 1.0}, _cyclic_graph(), direction="downstream")

    assert scores, "propagation returned no scores"
    assert all(math.isfinite(v) for v in scores.values()), "scores diverged to inf/nan"
    # With L1-normalised weights and decay<1 the fixed point is bounded by
    # ||seed|| / (1 - decay); nothing should explode into the thousands.
    assert max(abs(v) for v in scores.values()) < 100.0


def test_seed_signal_dominates_and_decays_with_distance():
    """The seed keeps the strongest signal; downstream nodes attenuate."""
    prop = CausalPropagator(decay=0.85, max_iterations=100)
    scores = prop.propagate({"A": 1.0}, _cyclic_graph(), direction="downstream")

    assert scores["A"] >= scores["B"] > 0
    # B is one hop from the seed, C is two — the nearer node carries more signal.
    assert abs(scores["B"]) > abs(scores["C"])


def test_inhibitory_edges_flip_sign():
    """An ``inhibits`` edge propagates a negated signal to its target."""
    prop = CausalPropagator(decay=0.85, max_iterations=100)
    edges = [("A", "B", "inhibits", _meta())]
    scores = prop.propagate({"A": 1.0}, edges, direction="downstream")
    assert scores["B"] < 0


def test_empty_graph_returns_seed_only():
    prop = CausalPropagator()
    scores = prop.propagate({"A": 1.0}, [], direction="downstream")
    assert scores == {"A": 1.0}


def test_high_confidence_dense_graph_stays_bounded():
    """Many high-confidence edges in a tight cycle must not blow up — this is the
    exact shape that produced the ~1e21 scores before the fix."""
    prop = CausalPropagator(decay=0.95, max_iterations=50)
    nodes = [f"N{i}" for i in range(10)]
    edges = []
    for i, src in enumerate(nodes):
        for tgt in nodes:  # fully connected, including self-feedback paths
            if src != tgt:
                edges.append((src, tgt, "activates", _meta(0.99)))
    scores = prop.propagate({"N0": 1.0}, edges, direction="both")
    assert all(math.isfinite(v) for v in scores.values())
    assert max(abs(v) for v in scores.values()) < 100.0
