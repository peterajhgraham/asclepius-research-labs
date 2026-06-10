"""Tests for the knowledge-graph service's robustness fixes.

Two regressions are guarded here:

  1. ``_find_project_root`` must not assume a fixed directory depth. The old
     ``Path(__file__).parents[4]`` raised ``IndexError: 4`` on the deployed
     (shallower) layout, which took down every graph-backed tool — most visibly
     ``causal_propagate``.
  2. ``resolve_node_id`` must map paper-style seed names ("TNF-alpha", "IL-17A")
     onto the canonical graph node that actually has outgoing edges ("TNF",
     "IL17A"), or propagation starts from a dead-end synonym and returns nothing
     but the seeds back.

Run with: pytest tests/test_graph_service.py -v
"""

from __future__ import annotations

from app.services.graph_service import _find_project_root, knowledge_graph


def test_project_root_contains_graph_and_causal_packages():
    root = _find_project_root()
    assert (root / "graph").is_dir()
    assert (root / "causal").is_dir()


def test_resolve_maps_greek_aliases_to_canonical_symbols():
    # TNF-alpha and IL-17A exist in the graph as dead-end synonym nodes; the
    # resolver must prefer the edge-bearing canonical symbols.
    assert knowledge_graph.resolve_node_id("TNF-alpha") == "TNF"
    assert knowledge_graph.resolve_node_id("IL-17A") == "IL17A"
    assert knowledge_graph.resolve_node_id("IFN-gamma") == "IFNG"


def test_resolve_is_punctuation_and_case_insensitive():
    assert knowledge_graph.resolve_node_id("tnf") == "TNF"
    assert knowledge_graph.resolve_node_id("il17a") == "IL17A"


def test_resolve_returns_none_for_unknown_node():
    assert knowledge_graph.resolve_node_id("definitely-not-a-real-gene-xyz") is None


def test_resolved_seed_actually_propagates_downstream():
    """The whole point: a resolved seed must reach real downstream nodes, not
    just echo the seed back."""
    scores = knowledge_graph.propagate_signal(
        {knowledge_graph.resolve_node_id("TNF-alpha"): 1.0}, direction="downstream"
    )
    downstream = {k for k, v in scores.items() if k != "TNF" and abs(v) > 0}
    assert downstream, "resolved TNF seed propagated to nothing downstream"
