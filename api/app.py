# app.py
# Optional REST API wrapper for the immunograph reasoning engine.

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from flask import Flask, jsonify, request
except ImportError:
    raise ImportError(
        "Flask is required for the API server. Install with `pip install flask`."
    )

from causal.intervention_ranker import InterventionRanker
from causal.propagation import CausalPropagator
from causal.scoring_utils import normalize_scores
from data_ingestion.entity_normalizer import normalize_entity
from graph.graph_builder import ImmuneGraphBuilder
from graph.graph_queries import GraphQueryEngine
from optimizer.experiment_suggester import ExperimentSuggester

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared state (in-memory for demo purposes)
# ---------------------------------------------------------------------------

_builder = ImmuneGraphBuilder(use_memory_backend=True)
_query_engine = GraphQueryEngine(_builder)
_propagator = CausalPropagator()
_ranker = InterventionRanker(propagator=_propagator)
_suggester = ExperimentSuggester(ranker=_ranker)


# ---------------------------------------------------------------------------
# Graph endpoints
# ---------------------------------------------------------------------------

@app.route("/graph/nodes", methods=["GET"])
def list_nodes():
    """Return all nodes in the in-memory graph.

    Returns
    -------
    JSON array of node objects.
    """
    nodes = list(_builder.get_nodes().values())
    return jsonify(nodes)


@app.route("/graph/edges", methods=["GET"])
def list_edges():
    """Return all edges in the in-memory graph.

    Returns
    -------
    JSON array of edge objects.
    """
    edges = _builder.get_edge_list()
    return jsonify(edges)


@app.route("/graph/node", methods=["POST"])
def create_node():
    """Create or update a graph node.

    Request body (JSON):
        - ``node_id`` (str): unique identifier
        - ``node_type`` (str): must be a valid NODE_TYPE
        - additional properties are stored as metadata

    Returns
    -------
    JSON confirmation message.
    """
    data: Dict[str, Any] = request.get_json(force=True)
    node_id = data.pop("node_id", None)
    node_type = data.pop("node_type", None)
    if not node_id or not node_type:
        return jsonify({"error": "node_id and node_type are required"}), 400
    try:
        _builder.create_node(node_id, node_type, **data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok", "node_id": node_id})


@app.route("/graph/edge", methods=["POST"])
def create_edge():
    """Create or update a graph edge.

    Request body (JSON):
        - ``source_id`` (str)
        - ``target_id`` (str)
        - ``edge_type`` (str)
        - additional properties are stored as edge metadata

    Returns
    -------
    JSON confirmation message.
    """
    data: Dict[str, Any] = request.get_json(force=True)
    source_id = data.pop("source_id", None)
    target_id = data.pop("target_id", None)
    edge_type = data.pop("edge_type", None)
    if not source_id or not target_id or not edge_type:
        return jsonify({"error": "source_id, target_id, and edge_type are required"}), 400
    try:
        _builder.create_edge(source_id, target_id, edge_type, **data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "ok"})


@app.route("/graph/neighbours/<node_id>", methods=["GET"])
def get_neighbours(node_id: str):
    """Return direct neighbours of a node.

    Query parameters:
        - ``direction``: ``outgoing`` (default), ``incoming``, or ``both``
        - ``edge_types``: comma-separated edge type filter

    Returns
    -------
    JSON array of neighbour node IDs.
    """
    direction = request.args.get("direction", "outgoing")
    edge_types_raw = request.args.get("edge_types")
    edge_types = edge_types_raw.split(",") if edge_types_raw else None
    neighbours = _query_engine.get_neighbours(
        node_id, edge_types=edge_types, direction=direction
    )
    return jsonify(neighbours)


# ---------------------------------------------------------------------------
# Causal reasoning endpoints
# ---------------------------------------------------------------------------

@app.route("/causal/propagate", methods=["POST"])
def propagate():
    """Run causal signal propagation from seed nodes.

    Request body (JSON):
        - ``seeds``: dict mapping node_id → initial_score
        - ``direction``: ``"downstream"`` (default), ``"upstream"``, or ``"both"``

    Returns
    -------
    JSON dict mapping node_id → propagated score.
    """
    data: Dict[str, Any] = request.get_json(force=True)
    seeds: Dict[str, float] = data.get("seeds", {})
    direction: str = data.get("direction", "downstream")
    if not seeds:
        return jsonify({"error": "seeds dict is required"}), 400
    edge_list = [
        (e["source"], e["target"], e["type"],
         {k: v for k, v in e.items() if k not in ("source", "target", "type")})
        for e in _builder.get_edge_list()
    ]
    scores = _propagator.propagate(seeds, edge_list, direction=direction)
    return jsonify(normalize_scores(scores))


@app.route("/causal/rank_interventions", methods=["POST"])
def rank_interventions():
    """Rank upstream intervention nodes for a target.

    Request body (JSON):
        - ``target_node`` (str): target node ID
        - ``top_k`` (int, optional): number of results
        - ``cell_type_context`` (str, optional): filter context

    Returns
    -------
    JSON array of ranked intervention dicts.
    """
    data: Dict[str, Any] = request.get_json(force=True)
    target_node: str = data.get("target_node", "")
    top_k: Optional[int] = data.get("top_k")
    cell_type_context: Optional[str] = data.get("cell_type_context")
    if not target_node:
        return jsonify({"error": "target_node is required"}), 400
    edge_list = [
        (e["source"], e["target"], e["type"],
         {k: v for k, v in e.items() if k not in ("source", "target", "type")})
        for e in _builder.get_edge_list()
    ]
    ranked = _ranker.rank_interventions(
        target_node=target_node,
        edge_list=edge_list,
        cell_type_context=cell_type_context,
        top_k=top_k,
    )
    return jsonify(ranked)


# ---------------------------------------------------------------------------
# Experiment suggestion endpoints
# ---------------------------------------------------------------------------

@app.route("/optimizer/suggest", methods=["POST"])
def suggest_experiments():
    """Suggest perturbation experiments for an objective.

    Request body (JSON):
        - ``objective`` (str): target node to modulate
        - ``budget`` (int, optional): number of experiments (default 5)
        - ``cell_type_context`` (str, optional)
        - ``exclude`` (list of str, optional)

    Returns
    -------
    JSON array of experiment suggestion dicts.
    """
    data: Dict[str, Any] = request.get_json(force=True)
    objective: str = data.get("objective", "")
    budget: int = int(data.get("budget", 5))
    cell_type_context: Optional[str] = data.get("cell_type_context")
    exclude: Optional[List[str]] = data.get("exclude")
    if not objective:
        return jsonify({"error": "objective is required"}), 400
    edge_list = [
        (e["source"], e["target"], e["type"],
         {k: v for k, v in e.items() if k not in ("source", "target", "type")})
        for e in _builder.get_edge_list()
    ]
    suggestions = _suggester.suggest_experiments(
        objective=objective,
        edge_list=edge_list,
        budget=budget,
        cell_type_context=cell_type_context,
        exclude=exclude,
    )
    return jsonify(suggestions)


# ---------------------------------------------------------------------------
# Entity normalisation endpoint
# ---------------------------------------------------------------------------

@app.route("/normalize", methods=["POST"])
def normalize_entity_endpoint():
    """Normalise an entity name to a standard identifier.

    Request body (JSON):
        - ``entity`` (str): raw entity name
        - ``use_api`` (bool, optional): whether to query MyGene.info

    Returns
    -------
    JSON dict with normalised identifier fields.
    """
    data: Dict[str, Any] = request.get_json(force=True)
    entity: str = data.get("entity", "")
    use_api: bool = bool(data.get("use_api", False))
    if not entity:
        return jsonify({"error": "entity is required"}), 400
    result = normalize_entity(entity, use_api=use_api)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    """Return a simple health-check response.

    Returns
    -------
    JSON status message.
    """
    return jsonify({"status": "healthy", "service": "immunograph"})


if __name__ == "__main__":
    import os

    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
