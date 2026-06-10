"""Knowledge graph service for the autoimmune intelligence pipeline.

Builds an in-memory immune signaling graph from the loaded datasets at
startup and provides query-time graph operations: subgraph extraction,
path finding, hub analysis, and integration with causal propagation.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

# Graph + causal reasoning live in `app.kg`, vendored *inside* the backend
# package. They used to be imported from the repo-root ``graph``/``causal``
# packages via a runtime ``sys.path`` insertion — but production deploys the
# backend with ``asclepius/backend`` as its root directory, where those
# sibling packages do not exist. The import therefore raised
# ``ModuleNotFoundError: No module named 'graph'`` and every graph-backed agent
# tool (``causal_propagate``, ``rank_interventions``) failed on every call.
# Importing from within the package makes the service self-contained and the
# import resolvable regardless of deployment topology.
from app.kg.graph_builder import ImmuneGraphBuilder
from app.kg.graph_queries import GraphQueryEngine
from app.kg.propagation import CausalPropagator
from app.kg.intervention_ranker import InterventionRanker

from app.data.ingestion import STORE

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Manages the in-memory knowledge graph and provides query operations."""

    def __init__(self) -> None:
        self._builder = ImmuneGraphBuilder(use_memory_backend=True)
        self._query_engine = GraphQueryEngine(self._builder)
        self._propagator = CausalPropagator(decay=0.85, max_iterations=50)
        self._ranker = InterventionRanker(propagator=self._propagator)
        self._edge_tuples: List[Tuple[str, str, str, Dict[str, Any]]] = []
        self._loaded = False
        # Lazily-built map: normalised name -> canonical node ID, for resolving
        # free-text seed names (e.g. "TNF-alpha") onto graph IDs (e.g. "TNF").
        self._node_alias_index: Optional[Dict[str, str]] = None
        self._out_degree: Dict[str, int] = {}

    def ensure_loaded(self) -> None:
        """Build the graph from loaded datasets (idempotent)."""
        if self._loaded:
            return
        self._build_from_datasets()
        self._loaded = True

    # ------------------------------------------------------------------
    # Graph query operations
    # ------------------------------------------------------------------

    def get_subgraph(
        self,
        seed_nodes: List[str],
        hops: int = 2,
        edge_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Extract a subgraph around seed nodes."""
        self.ensure_loaded()
        result = self._query_engine.get_subgraph(seed_nodes, hops=hops, edge_types=edge_types)

        # Enrich nodes with their type info
        all_nodes = self._builder.get_nodes()
        enriched_nodes = []
        for nid in result["nodes"]:
            node_data = all_nodes.get(nid, {"id": nid, "type": "Unknown"})
            enriched_nodes.append(node_data)

        return {
            "nodes": enriched_nodes,
            "edges": result["edges"],
            "node_count": len(enriched_nodes),
            "edge_count": len(result["edges"]),
        }

    def find_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
    ) -> List[List[str]]:
        """Find all simple paths between two nodes."""
        self.ensure_loaded()
        return self._query_engine.find_paths(source, target, max_depth=max_depth)

    def get_neighbours(
        self,
        node_id: str,
        direction: str = "both",
    ) -> List[str]:
        """Get direct neighbours of a node."""
        self.ensure_loaded()
        return self._query_engine.get_neighbours(node_id, direction=direction)

    def get_hubs(self, n: int = 15) -> List[Dict[str, Any]]:
        """Return the most highly connected nodes (hubs) in the graph."""
        self.ensure_loaded()
        hub_ids = self._query_engine.top_hubs(n=n)
        all_nodes = self._builder.get_nodes()
        degree = self._query_engine.compute_degree(direction="both")

        return [
            {
                "node_id": nid,
                "type": all_nodes.get(nid, {}).get("type", "Unknown"),
                "degree": degree.get(nid, 0),
            }
            for nid in hub_ids
        ]

    # ------------------------------------------------------------------
    # Causal reasoning
    # ------------------------------------------------------------------

    def propagate_signal(
        self,
        seed_scores: Dict[str, float],
        direction: str = "downstream",
    ) -> Dict[str, float]:
        """Run causal signal propagation from seed nodes."""
        self.ensure_loaded()
        return self._propagator.propagate(seed_scores, self._edge_tuples, direction)

    # ------------------------------------------------------------------
    # Node-name resolution
    # ------------------------------------------------------------------

    _GREEK_WORDS = {"ALPHA": "A", "BETA": "B", "GAMMA": "G", "DELTA": "D"}

    @staticmethod
    def _normalize_node_key(name: str) -> str:
        """Collapse a name to an alphanumeric, uppercase key for matching.

        ``"IL-17A"`` and ``"IL17A"`` both map to ``"IL17A"``; ``"TNF-alpha"``
        and ``"TNF alpha"`` both map to ``"TNFALPHA"``.
        """
        return re.sub(r"[^A-Z0-9]", "", (name or "").upper())

    @classmethod
    def _candidate_keys(cls, name: str) -> List[str]:
        """Generate the normalised keys a name might match in the graph.

        Greek subunit words are inconsistent across HGNC symbols — ``IFN-gamma``
        is ``IFNG`` (letter kept) but ``TNF-alpha`` is ``TNF`` (dropped) — so we
        emit *both* a letter-substituted and a stripped variant and let the
        caller pick whichever actually exists.
        """
        base = cls._normalize_node_key(name)
        keys = [base]
        for word, letter in cls._GREEK_WORDS.items():
            if base.endswith(word):
                stem = base[: -len(word)]
                keys.append(stem + letter)  # IFNGAMMA -> IFNG
                keys.append(stem)           # TNFALPHA -> TNF
        # de-dupe, preserve order, drop empties
        seen: set[str] = set()
        return [k for k in keys if k and not (k in seen or seen.add(k))]

    def _build_alias_index(self) -> Dict[str, str]:
        """Build a normalised-name -> canonical-node-ID lookup.

        The graph carries the same molecule under more than one label (e.g. the
        cytokine-edge ``"IL-17A"`` and the pathway gene symbol ``"IL17A"``). When
        two labels normalise to the same key we keep the one with the most
        outgoing edges, so seeds resolve to the node that can actually propagate
        a signal rather than a dead-end synonym.
        """
        self.ensure_loaded()
        self._out_degree = {}
        for src, _tgt, _etype, _meta in self._edge_tuples:
            self._out_degree[src] = self._out_degree.get(src, 0) + 1

        index: Dict[str, str] = {}
        for node_id in self._builder.get_nodes():
            key = self._normalize_node_key(node_id)
            if not key:
                continue
            incumbent = index.get(key)
            if incumbent is None or self._out_degree.get(node_id, 0) > self._out_degree.get(incumbent, 0):
                index[key] = node_id
        return index

    def resolve_node_id(self, name: str) -> Optional[str]:
        """Map a free-text node name onto a canonical graph node ID.

        Handles punctuation/case differences and greek-subunit aliases
        (``"TNF-alpha"`` -> ``"TNF"``, ``"IL-17A"`` -> ``"IL17A"``). When several
        labels match, returns the one with the most outgoing edges so propagation
        starts from a node that can actually carry a signal rather than a
        dead-end synonym. Returns ``None`` if nothing in the graph matches.
        """
        self.ensure_loaded()
        if self._node_alias_index is None:
            self._node_alias_index = self._build_alias_index()

        candidates: List[str] = []
        if name in self._builder.get_nodes():
            candidates.append(name)
        for key in self._candidate_keys(name):
            hit = self._node_alias_index.get(key)
            if hit is not None:
                candidates.append(hit)
        if not candidates:
            return None
        return max(candidates, key=lambda nid: self._out_degree.get(nid, 0))

    def rank_interventions(
        self,
        target_node: str,
        cell_type_context: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Rank upstream nodes by their potential to modulate a target."""
        self.ensure_loaded()
        return self._ranker.rank_interventions(
            target_node=target_node,
            edge_list=self._edge_tuples,
            cell_type_context=cell_type_context,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # Graph statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics about the loaded graph."""
        self.ensure_loaded()
        nodes = self._builder.get_nodes()
        edges = self._builder.get_edge_list()

        type_counts: Dict[str, int] = {}
        for node in nodes.values():
            ntype = node.get("type", "Unknown")
            type_counts[ntype] = type_counts.get(ntype, 0) + 1

        edge_type_counts: Dict[str, int] = {}
        for edge in edges:
            etype = edge.get("type", "unknown")
            edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": type_counts,
            "edge_types": edge_type_counts,
        }

    # ------------------------------------------------------------------
    # Graph building from datasets
    # ------------------------------------------------------------------

    def _build_from_datasets(self) -> None:
        """Populate the graph from the loaded STORE datasets."""
        logger.info("Building knowledge graph from datasets...")

        # 1. Cytokine network edges
        for edge in STORE.cytokine_edges:
            src_type = self._map_entity_type(edge.source_type)
            tgt_type = self._map_entity_type(edge.target_type)
            self._builder.create_node(edge.source, src_type)
            self._builder.create_node(edge.target, tgt_type)

            edge_type = edge.edge_type if edge.edge_type in (
                "activates", "inhibits", "binds",
            ) else "activates"
            meta = {
                "confidence_score": edge.confidence,
                "source_publication": edge.pmid,
            }
            self._builder.create_edge(edge.source, edge.target, edge_type, **meta)
            self._edge_tuples.append((edge.source, edge.target, edge_type, meta))

        # 2. Pathway nodes and edges
        for pw in STORE.pathways:
            self._builder.create_node(pw.pathway_name, "Pathway")
            for node in pw.key_nodes:
                gene = node.get("gene", "")
                if gene:
                    self._builder.create_node(gene, "Gene")
                    meta = {"confidence_score": 0.8}
                    self._builder.create_edge(gene, pw.pathway_name, "part_of_pathway", **meta)
                    self._edge_tuples.append((gene, pw.pathway_name, "part_of_pathway", meta))

            for pw_edge in pw.edges:
                src = pw_edge.get("source", "")
                tgt = pw_edge.get("target", "")
                etype = pw_edge.get("type", "activates")
                if src and tgt and etype in ("activates", "inhibits", "binds", "downstream_of"):
                    meta = {"confidence_score": 0.7}
                    self._builder.create_node(src, "Gene")
                    self._builder.create_node(tgt, "Gene")
                    self._builder.create_edge(src, tgt, etype, **meta)
                    self._edge_tuples.append((src, tgt, etype, meta))

        # 3. Disease-gene associations
        for dis in STORE.diseases:
            for gene_rec in dis.associated_genes:
                gene = gene_rec.get("gene", "")
                if gene:
                    self._builder.create_node(gene, "Gene")
            for cell in dis.key_cell_types:
                self._builder.create_node(cell, "CellType")

        # 4. Therapeutic targets
        for rx in STORE.therapeutics:
            target = rx.target
            if target:
                tgt_type = self._map_entity_type(rx.target_type)
                self._builder.create_node(target, tgt_type)

        logger.info(
            "Knowledge graph built: %d nodes, %d edges, %d causal edge tuples",
            len(self._builder.get_nodes()),
            len(self._builder.get_edge_list()),
            len(self._edge_tuples),
        )

    @staticmethod
    def _map_entity_type(raw_type: str) -> str:
        """Map dataset entity types to graph schema node types."""
        mapping = {
            "cytokine": "Cytokine",
            "receptor": "Receptor",
            "gene": "Gene",
            "protein": "Protein",
            "kinase": "Protein",
            "transcription factor": "TranscriptionFactor",
            "cell type": "CellType",
            "pathway": "Pathway",
            "enzyme": "Protein",
            "signaling molecule": "Protein",
        }
        return mapping.get(raw_type.lower(), "Gene")


# Singleton instance — graph is built lazily on first access
knowledge_graph = KnowledgeGraphService()
