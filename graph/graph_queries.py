# graph_queries.py
# Query and explore the immune signaling knowledge graph.

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set

from .graph_builder import ImmuneGraphBuilder


class GraphQueryEngine:
    """High-level query interface over an :class:`ImmuneGraphBuilder` instance.

    All heavy queries are implemented for the in-memory backend and can be
    mapped to Cypher when a Neo4j backend is used.

    Parameters
    ----------
    builder:
        A populated :class:`ImmuneGraphBuilder` instance.
    """

    def __init__(self, builder: ImmuneGraphBuilder) -> None:
        self._builder = builder

    # ------------------------------------------------------------------
    # Neighbourhood queries
    # ------------------------------------------------------------------

    def get_neighbours(
        self,
        node_id: str,
        edge_types: Optional[List[str]] = None,
        direction: str = "outgoing",
    ) -> List[str]:
        """Return direct neighbours of *node_id*.

        Parameters
        ----------
        node_id:
            The node whose neighbours to retrieve.
        edge_types:
            Optional filter list of edge type strings.  If *None*, all
            edge types are considered.
        direction:
            ``"outgoing"`` (default) returns targets of edges *from* the
            node; ``"incoming"`` returns sources of edges *to* the node;
            ``"both"`` returns both.

        Returns
        -------
        list of str
            Neighbour node IDs (deduplicated, preserving insertion order).
        """
        edges = self._builder.get_edge_list()
        neighbours: List[str] = []
        seen: Set[str] = set()

        for edge in edges:
            keep_type = edge_types is None or edge["type"] in edge_types
            if not keep_type:
                continue

            candidate: Optional[str] = None
            if direction in ("outgoing", "both") and edge["source"] == node_id:
                candidate = edge["target"]
            elif direction in ("incoming", "both") and edge["target"] == node_id:
                candidate = edge["source"]

            if candidate is not None and candidate not in seen:
                neighbours.append(candidate)
                seen.add(candidate)

        return neighbours

    # ------------------------------------------------------------------
    # Path queries
    # ------------------------------------------------------------------

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
        edge_types: Optional[List[str]] = None,
    ) -> List[List[str]]:
        """Find all simple paths between *source_id* and *target_id*.

        Parameters
        ----------
        source_id:
            Starting node.
        target_id:
            Destination node.
        max_depth:
            Maximum number of hops to explore.
        edge_types:
            Optional edge-type filter.

        Returns
        -------
        list of list of str
            Each inner list is a sequence of node IDs representing one path.
        """
        paths: List[List[str]] = []
        # BFS with path tracking
        queue: deque = deque([(source_id, [source_id])])

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth + 1:
                continue
            for neighbour in self.get_neighbours(
                current, edge_types=edge_types, direction="outgoing"
            ):
                if neighbour == target_id:
                    paths.append(path + [neighbour])
                elif neighbour not in path:
                    queue.append((neighbour, path + [neighbour]))

        return paths

    # ------------------------------------------------------------------
    # Subgraph extraction
    # ------------------------------------------------------------------

    def get_subgraph(
        self,
        seed_nodes: List[str],
        hops: int = 1,
        edge_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Extract a subgraph around a set of seed nodes.

        Parameters
        ----------
        seed_nodes:
            Node IDs to centre the subgraph on.
        hops:
            Number of hops to expand outward from each seed.
        edge_types:
            Optional edge-type filter.

        Returns
        -------
        dict
            A dictionary with keys ``"nodes"`` (list of node IDs) and
            ``"edges"`` (list of edge dicts).
        """
        included: Set[str] = set(seed_nodes)
        frontier: Set[str] = set(seed_nodes)

        for _ in range(hops):
            next_frontier: Set[str] = set()
            for node in frontier:
                for nb in self.get_neighbours(
                    node, edge_types=edge_types, direction="both"
                ):
                    if nb not in included:
                        next_frontier.add(nb)
            included |= next_frontier
            frontier = next_frontier

        subgraph_edges = [
            e
            for e in self._builder.get_edge_list()
            if e["source"] in included and e["target"] in included
            and (edge_types is None or e["type"] in edge_types)
        ]

        return {"nodes": sorted(included), "edges": subgraph_edges}

    # ------------------------------------------------------------------
    # Degree / centrality helpers
    # ------------------------------------------------------------------

    def compute_degree(self, direction: str = "outgoing") -> Dict[str, int]:
        """Compute in-, out-, or total-degree for every node.

        Parameters
        ----------
        direction:
            ``"outgoing"`` for out-degree, ``"incoming"`` for in-degree,
            ``"both"`` for total degree.

        Returns
        -------
        dict
            Mapping from node ID to degree count.
        """
        degree: Dict[str, int] = defaultdict(int)

        for edge in self._builder.get_edge_list():
            if direction in ("outgoing", "both"):
                degree[edge["source"]] += 1
            if direction in ("incoming", "both"):
                degree[edge["target"]] += 1

        return dict(degree)

    def top_hubs(self, n: int = 10, direction: str = "both") -> List[str]:
        """Return the *n* most highly connected nodes.

        Parameters
        ----------
        n:
            Number of hub nodes to return.
        direction:
            Degree direction to rank by.

        Returns
        -------
        list of str
            Node IDs sorted by degree descending.
        """
        degree = self.compute_degree(direction=direction)
        return sorted(degree, key=lambda k: degree[k], reverse=True)[:n]
