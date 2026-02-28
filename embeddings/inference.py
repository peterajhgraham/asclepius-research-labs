# inference.py
# Generate node and subgraph embeddings from a trained model.

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import numpy as np


class EmbeddingInference:
    """Embedding inference engine supporting multiple trained models.

    Wraps either a :class:`~embeddings.train_gnn.GNNTrainer` or a
    :class:`~embeddings.node2vec_baseline.Node2VecBaseline` (or any object
    with a ``get_embeddings()`` method) to provide a unified inference API.

    Parameters
    ----------
    model:
        Trained embedding model exposing ``get_embeddings() -> dict``.
    """

    def __init__(self, model: Any) -> None:
        if not hasattr(model, "get_embeddings"):
            raise TypeError("model must have a get_embeddings() method.")
        self._model = model
        self._embeddings: Dict[str, np.ndarray] = model.get_embeddings()

    def get_node_embedding(self, node_id: str) -> np.ndarray:
        """Return the embedding vector for a single node.

        Parameters
        ----------
        node_id:
            Target node identifier.

        Returns
        -------
        numpy.ndarray
            1-D embedding vector.

        Raises
        ------
        KeyError
            If *node_id* is not in the embedding vocabulary.
        """
        if node_id not in self._embeddings:
            raise KeyError(f"Node '{node_id}' not found in embeddings.")
        return self._embeddings[node_id]

    def get_subgraph_embedding(
        self,
        node_ids: List[str],
        aggregation: str = "mean",
    ) -> np.ndarray:
        """Compute an aggregate embedding for a subgraph or pathway module.

        Parameters
        ----------
        node_ids:
            List of node IDs belonging to the subgraph.
        aggregation:
            Aggregation strategy: ``"mean"`` (default), ``"sum"``, or
            ``"max"``.

        Returns
        -------
        numpy.ndarray
            Aggregated embedding vector.

        Raises
        ------
        ValueError
            If *aggregation* is not recognised or no valid node IDs are given.
        """
        valid_ids = [nid for nid in node_ids if nid in self._embeddings]
        if not valid_ids:
            raise ValueError("None of the provided node_ids have embeddings.")

        stack = np.stack([self._embeddings[nid] for nid in valid_ids])

        if aggregation == "mean":
            return stack.mean(axis=0)
        if aggregation == "sum":
            return stack.sum(axis=0)
        if aggregation == "max":
            return stack.max(axis=0)
        raise ValueError(f"Unknown aggregation '{aggregation}'. Use 'mean', 'sum', or 'max'.")

    def cosine_similarity(self, node_a: str, node_b: str) -> float:
        """Compute cosine similarity between two node embeddings.

        Parameters
        ----------
        node_a:
            First node ID.
        node_b:
            Second node ID.

        Returns
        -------
        float
            Cosine similarity in [-1, 1].
        """
        v_a = self.get_node_embedding(node_a)
        v_b = self.get_node_embedding(node_b)
        denom = (np.linalg.norm(v_a) * np.linalg.norm(v_b)) + 1e-10
        return float(np.dot(v_a, v_b) / denom)

    def most_similar(
        self,
        node_id: str,
        top_k: int = 10,
        exclude: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Find the *top_k* most similar nodes by cosine similarity.

        Parameters
        ----------
        node_id:
            Query node.
        top_k:
            Number of results to return.
        exclude:
            Optional list of node IDs to exclude from results.

        Returns
        -------
        list of dict
            Each dict has keys ``"node_id"`` and ``"similarity"``, sorted
            by descending similarity.
        """
        query_vec = self.get_node_embedding(node_id)
        exclude_set = set(exclude or []) | {node_id}

        scores = []
        for nid, vec in self._embeddings.items():
            if nid in exclude_set:
                continue
            denom = (np.linalg.norm(query_vec) * np.linalg.norm(vec)) + 1e-10
            sim = float(np.dot(query_vec, vec) / denom)
            scores.append({"node_id": nid, "similarity": sim})

        scores.sort(key=lambda x: x["similarity"], reverse=True)
        return scores[:top_k]

    @property
    def vocabulary(self) -> List[str]:
        """Return all node IDs in the embedding vocabulary.

        Returns
        -------
        list of str
        """
        return list(self._embeddings.keys())
