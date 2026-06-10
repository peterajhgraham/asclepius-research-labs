"""Build and populate the immune signaling graph in Neo4j or an in-memory store.

Vendored into the backend (`app.kg`) so the deployable service is
self-contained. The backend always uses the in-memory backend, so the
optional ``neo4j`` driver is never imported in production.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .schema import EDGE_TYPES, NODE_TYPES


class ImmuneGraphBuilder:
    """Build and manage an immune signaling knowledge graph.

    Supports Neo4j as the primary backend and falls back to an in-memory
    adjacency structure when a Neo4j driver is not available (useful for
    testing and local development without a running database).

    Parameters
    ----------
    uri:
        Bolt URI for the Neo4j instance, e.g. ``"bolt://localhost:7687"``.
    user:
        Neo4j username.
    password:
        Neo4j password.
    use_memory_backend:
        When *True* the builder skips Neo4j entirely and stores the graph
        in plain Python dicts.  Defaults to *False*.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        use_memory_backend: bool = False,
    ) -> None:
        self._use_memory = use_memory_backend
        self._driver = None

        if not self._use_memory:
            try:
                from neo4j import GraphDatabase  # type: ignore

                self._driver = GraphDatabase.driver(uri, auth=(user, password))
            except ImportError:
                raise RuntimeError(
                    "neo4j Python driver is not installed. "
                    "Install it with `pip install neo4j` or set use_memory_backend=True."
                )

        # In-memory fallback storage
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the Neo4j driver connection if open."""
        if self._driver is not None:
            self._driver.close()

    def __enter__(self) -> "ImmuneGraphBuilder":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def create_node(self, node_id: str, node_type: str, **properties: Any) -> None:
        """Create or update a node in the graph.

        Parameters
        ----------
        node_id:
            Unique identifier for the node (e.g. HGNC gene symbol or UniProt
            accession).
        node_type:
            One of the node types defined in :data:`app.kg.schema.NODE_TYPES`.
        **properties:
            Arbitrary additional properties to store on the node (e.g.
            ``full_name``, ``hgnc_id``, ``uniprot_id``).

        Raises
        ------
        ValueError
            If *node_type* is not recognised.
        """
        if node_type not in NODE_TYPES:
            raise ValueError(
                f"Unknown node type '{node_type}'. Valid types: {NODE_TYPES}"
            )

        if self._use_memory:
            self._nodes[node_id] = {"id": node_id, "type": node_type, **properties}
        else:
            query = (
                f"MERGE (n:{node_type} {{id: $node_id}}) "
                "SET n += $properties"
            )
            with self._driver.session() as session:
                session.run(query, node_id=node_id, properties=properties)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a node by its ID (memory backend only).

        Parameters
        ----------
        node_id:
            The unique identifier of the node to retrieve.

        Returns
        -------
        dict or None
            Node property dictionary, or *None* if not found.
        """
        if self._use_memory:
            return self._nodes.get(node_id)
        raise NotImplementedError("get_node is only supported in memory backend mode.")

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        **properties: Any,
    ) -> None:
        """Create or update a directed edge between two nodes.

        Parameters
        ----------
        source_id:
            Identifier of the source node.
        target_id:
            Identifier of the target node.
        edge_type:
            One of the edge types defined in :data:`app.kg.schema.EDGE_TYPES`.
        **properties:
            Arbitrary edge metadata (e.g. ``confidence_score``,
            ``source_publication``, ``cell_type_context``).

        Raises
        ------
        ValueError
            If *edge_type* is not recognised.
        """
        if edge_type not in EDGE_TYPES:
            raise ValueError(
                f"Unknown edge type '{edge_type}'. Valid types: {EDGE_TYPES}"
            )

        if self._use_memory:
            self._edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                    **properties,
                }
            )
        else:
            query = (
                "MATCH (a {id: $source_id}), (b {id: $target_id}) "
                f"MERGE (a)-[r:{edge_type}]->(b) "
                "SET r += $properties"
            )
            with self._driver.session() as session:
                session.run(
                    query,
                    source_id=source_id,
                    target_id=target_id,
                    properties=properties,
                )

    # ------------------------------------------------------------------
    # Bulk loading helpers
    # ------------------------------------------------------------------

    def load_edge_list(
        self,
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
        node_type_map: Optional[Dict[str, str]] = None,
    ) -> None:
        """Bulk-load an edge list into the graph.

        Parameters
        ----------
        edge_list:
            Iterable of ``(source_id, target_id, edge_type, metadata)``
            tuples as produced by the data ingestion layer.
        node_type_map:
            Optional mapping from node ID to node type.  When provided,
            nodes are created/updated before their edges are inserted.
            Nodes not in the map default to type ``"Gene"``.
        """
        for source_id, target_id, edge_type, metadata in edge_list:
            if node_type_map is not None:
                for nid in (source_id, target_id):
                    ntype = node_type_map.get(nid, "Gene")
                    self.create_node(nid, ntype)
            self.create_edge(source_id, target_id, edge_type, **metadata)

    # ------------------------------------------------------------------
    # In-memory inspection helpers
    # ------------------------------------------------------------------

    def get_edge_list(self) -> List[Dict[str, Any]]:
        """Return all edges stored in the memory backend.

        Returns
        -------
        list of dict
            Each dict has keys ``source``, ``target``, ``type``, plus any
            additional metadata.

        Raises
        ------
        NotImplementedError
            When not using the memory backend.
        """
        if self._use_memory:
            return list(self._edges)
        raise NotImplementedError("get_edge_list is only supported in memory backend mode.")

    def get_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Return all nodes stored in the memory backend.

        Returns
        -------
        dict
            Mapping from node ID to node property dictionary.

        Raises
        ------
        NotImplementedError
            When not using the memory backend.
        """
        if self._use_memory:
            return dict(self._nodes)
        raise NotImplementedError("get_nodes is only supported in memory backend mode.")
