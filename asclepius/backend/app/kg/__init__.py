"""Self-contained knowledge-graph + causal-reasoning package for the backend.

This is vendored from the repo-root ``graph`` and ``causal`` packages so the
deployable FastAPI service has no dependency on code outside its own package
tree. The production backend is deployed with ``asclepius/backend`` as its
root directory, where the repo-root packages are not present — importing them
there raised ``ModuleNotFoundError: No module named 'graph'`` and took down
every graph-backed agent tool (most visibly ``causal_propagate``).
"""

from .schema import EDGE_METADATA_FIELDS, EDGE_TYPES, NODE_TYPES
from .graph_builder import ImmuneGraphBuilder
from .graph_queries import GraphQueryEngine
from .propagation import CausalPropagator
from .intervention_ranker import InterventionRanker
from .scoring_utils import compute_influence_score, normalize_scores

__all__ = [
    "NODE_TYPES",
    "EDGE_TYPES",
    "EDGE_METADATA_FIELDS",
    "ImmuneGraphBuilder",
    "GraphQueryEngine",
    "CausalPropagator",
    "InterventionRanker",
    "compute_influence_score",
    "normalize_scores",
]
