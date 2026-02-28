# train_gnn.py
# Train a graph neural network over the immune signaling graph.

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class GNNTrainer:
    """Lightweight GNN trainer for node embedding learning.

    This implementation provides a message-passing framework using pure NumPy
    so that it runs without a GPU or deep-learning framework.  For production
    use, replace the forward pass with a PyTorch Geometric or DGL model.

    Parameters
    ----------
    embedding_dim:
        Dimensionality of learned node embeddings.
    num_layers:
        Number of message-passing layers.
    learning_rate:
        Gradient descent step size.
    epochs:
        Training iterations.
    random_seed:
        Seed for reproducibility.
    """

    def __init__(
        self,
        embedding_dim: int = 64,
        num_layers: int = 2,
        learning_rate: float = 0.01,
        epochs: int = 100,
        random_seed: int = 42,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.random_seed = random_seed
        self._embeddings: Optional[Dict[str, np.ndarray]] = None

    def fit(
        self,
        node_ids: List[str],
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
    ) -> None:
        """Train node embeddings using simplified message passing.

        Parameters
        ----------
        node_ids:
            Ordered list of unique node identifiers.
        edge_list:
            Edge tuples ``(source, target, edge_type, metadata)``.
        """
        rng = np.random.default_rng(self.random_seed)
        n = len(node_ids)
        idx = {nid: i for i, nid in enumerate(node_ids)}

        # Initialise random embeddings
        H = rng.standard_normal((n, self.embedding_dim)).astype(np.float32)

        # Build normalised adjacency matrix (symmetric)
        A = np.zeros((n, n), dtype=np.float32)
        for src, tgt, _, _ in edge_list:
            i, j = idx.get(src), idx.get(tgt)
            if i is not None and j is not None:
                A[i, j] = 1.0
                A[j, i] = 1.0  # treat as undirected for aggregation

        # Degree normalisation: D^{-1/2} A D^{-1/2}
        degree = A.sum(axis=1) + 1e-6  # avoid division by zero
        D_inv_sqrt = np.diag(1.0 / np.sqrt(degree))
        A_norm = D_inv_sqrt @ A @ D_inv_sqrt

        # Simple supervised objective: minimise reconstruction of adjacency
        for _ in range(self.epochs):
            for _ in range(self.num_layers):
                H = np.tanh(A_norm @ H)

            # Gradient w.r.t. link reconstruction (simplified)
            pred = H @ H.T
            loss_grad = 2.0 * (pred - A) / (n * n)
            H -= self.learning_rate * loss_grad @ H

        self._embeddings = {nid: H[idx[nid]] for nid in node_ids}

    def get_embeddings(self) -> Dict[str, np.ndarray]:
        """Return trained node embeddings.

        Returns
        -------
        dict
            Mapping from node ID to embedding vector.

        Raises
        ------
        RuntimeError
            If :meth:`fit` has not been called.
        """
        if self._embeddings is None:
            raise RuntimeError("Call fit() before get_embeddings().")
        return dict(self._embeddings)

    def save(self, filepath: str) -> None:
        """Persist embeddings to a NumPy ``.npz`` file.

        Parameters
        ----------
        filepath:
            Destination file path (should end with ``.npz``).
        """
        if self._embeddings is None:
            raise RuntimeError("Call fit() before save().")
        keys = list(self._embeddings.keys())
        vectors = np.stack([self._embeddings[k] for k in keys])
        np.savez(filepath, keys=keys, vectors=vectors)

    @classmethod
    def load(cls, filepath: str) -> "GNNTrainer":
        """Load embeddings previously saved with :meth:`save`.

        Parameters
        ----------
        filepath:
            Path to ``.npz`` file.

        Returns
        -------
        GNNTrainer
            Instance with ``_embeddings`` populated.
        """
        data = np.load(filepath, allow_pickle=True)
        trainer = cls()
        trainer._embeddings = {
            str(k): v for k, v in zip(data["keys"], data["vectors"])
        }
        return trainer
