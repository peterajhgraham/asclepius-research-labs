"""Tests for the knowledge-graph service's robustness fixes.

Two regressions are guarded here:

  1. The backend must be **self-contained**: its graph + causal logic must be
     imported from the vendored ``app.kg`` package, not the repo-root
     ``graph``/``causal`` packages. Production deploys ``asclepius/backend`` as
     the root directory, where those siblings don't exist — importing them there
     raised ``ModuleNotFoundError: No module named 'graph'`` and took down every
     graph-backed tool (most visibly ``causal_propagate``).
  2. ``resolve_node_id`` must map paper-style seed names ("TNF-alpha", "IL-17A")
     onto the canonical graph node that actually has outgoing edges ("TNF",
     "IL17A"), or propagation starts from a dead-end synonym and returns nothing
     but the seeds back.

Run with: pytest tests/test_graph_service.py -v
"""

from __future__ import annotations

import app.kg
from app.services import graph_service
from app.services.graph_service import knowledge_graph


def test_graph_service_uses_vendored_self_contained_package():
    # The service must bind to the vendored in-package implementations, never
    # the repo-root packages that are absent from the production image.
    assert graph_service.ImmuneGraphBuilder is app.kg.ImmuneGraphBuilder
    assert graph_service.CausalPropagator is app.kg.CausalPropagator
    assert graph_service.GraphQueryEngine is app.kg.GraphQueryEngine
    assert graph_service.InterventionRanker is app.kg.InterventionRanker


def test_graph_builds_a_non_trivial_graph():
    # The vendored package must actually build the immune graph from datasets.
    knowledge_graph.ensure_loaded()
    stats = knowledge_graph.get_stats()
    assert stats["total_nodes"] > 0
    assert stats["total_edges"] > 0


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
