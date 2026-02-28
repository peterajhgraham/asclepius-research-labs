# node2vec_baseline.py
# Node2Vec-style random walk baseline for node embeddings.

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class Node2VecBaseline:
    """Lightweight Node2Vec-style embedding baseline.

    Generates biased random walks on the graph and trains skip-gram style
    embeddings using negative sampling.  This is a self-contained
    implementation that avoids heavy ML framework dependencies.

    Parameters
    ----------
    embedding_dim:
        Dimensionality of learned embeddings.
    walk_length:
        Number of steps per random walk.
    num_walks:
        Number of walks starting from each node.
    window_size:
        Context window for skip-gram training.
    p:
        Return parameter (controls likelihood of revisiting previous node).
    q:
        In-out parameter (controls BFS vs DFS exploration).
    epochs:
        Number of passes through the generated walk corpus.
    learning_rate:
        SGD step size.
    negative_samples:
        Number of noise samples per positive pair.
    random_seed:
        Seed for reproducibility.
    """

    def __init__(
        self,
        embedding_dim: int = 64,
        walk_length: int = 30,
        num_walks: int = 10,
        window_size: int = 5,
        p: float = 1.0,
        q: float = 1.0,
        epochs: int = 5,
        learning_rate: float = 0.025,
        negative_samples: int = 5,
        random_seed: int = 42,
    ) -> None:
        self.embedding_dim = embedding_dim
        self.walk_length = walk_length
        self.num_walks = num_walks
        self.window_size = window_size
        self.p = p
        self.q = q
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.negative_samples = negative_samples
        self.random_seed = random_seed
        self._embeddings: Optional[Dict[str, np.ndarray]] = None

    def fit(
        self,
        node_ids: List[str],
        edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
    ) -> None:
        """Learn node embeddings via biased random walks + skip-gram.

        Parameters
        ----------
        node_ids:
            List of all node IDs in the graph.
        edge_list:
            Edge tuples ``(source, target, edge_type, metadata)``.
        """
        rng = random.Random(self.random_seed)
        np_rng = np.random.default_rng(self.random_seed)

        idx = {nid: i for i, nid in enumerate(node_ids)}
        n = len(node_ids)

        # Build adjacency list (undirected)
        adj: Dict[str, List[str]] = defaultdict(list)
        for src, tgt, _, _ in edge_list:
            if src in idx and tgt in idx:
                adj[src].append(tgt)
                adj[tgt].append(src)

        # Generate walks
        walks = self._generate_walks(node_ids, adj, rng)

        # Initialise embedding matrices
        W = np_rng.standard_normal((n, self.embedding_dim)).astype(np.float32) * 0.01
        C = np_rng.standard_normal((n, self.embedding_dim)).astype(np.float32) * 0.01

        lr = self.learning_rate

        for epoch in range(self.epochs):
            rng.shuffle(walks)
            for walk in walks:
                walk_idx = [idx[v] for v in walk]
                for pos, center in enumerate(walk_idx):
                    start = max(0, pos - self.window_size)
                    end = min(len(walk_idx), pos + self.window_size + 1)
                    for ctx_pos in range(start, end):
                        if ctx_pos == pos:
                            continue
                        ctx = walk_idx[ctx_pos]
                        # Positive sample
                        score = _sigmoid(W[center] @ C[ctx])
                        grad_c = lr * (1 - score) * W[center]
                        grad_w = lr * (1 - score) * C[ctx]
                        # Negative samples
                        negs = np_rng.integers(0, n, size=self.negative_samples)
                        for neg in negs:
                            neg_score = _sigmoid(W[center] @ C[neg])
                            grad_w -= lr * neg_score * C[neg]
                            C[neg] -= lr * neg_score * W[center]
                        W[center] += grad_w
                        C[ctx] += grad_c

            # Decay learning rate
            lr = max(0.0001, lr * 0.9)

        self._embeddings = {nid: W[idx[nid]] for nid in node_ids}

    def _generate_walks(
        self,
        node_ids: List[str],
        adj: Dict[str, List[str]],
        rng: random.Random,
    ) -> List[List[str]]:
        """Generate biased random walks.

        Parameters
        ----------
        node_ids:
            All nodes to start walks from.
        adj:
            Adjacency list.
        rng:
            Random number generator.

        Returns
        -------
        list of walks
        """
        walks: List[List[str]] = []
        for _ in range(self.num_walks):
            shuffled = list(node_ids)
            rng.shuffle(shuffled)
            for start in shuffled:
                walk = self._biased_walk(start, adj, rng)
                walks.append(walk)
        return walks

    def _biased_walk(
        self,
        start: str,
        adj: Dict[str, List[str]],
        rng: random.Random,
    ) -> List[str]:
        """Perform a single biased random walk.

        Parameters
        ----------
        start:
            Starting node.
        adj:
            Adjacency list.
        rng:
            Random number generator.

        Returns
        -------
        list of str
            Walk as a sequence of node IDs.
        """
        walk = [start]
        for step in range(self.walk_length - 1):
            cur = walk[-1]
            neighbors = adj.get(cur, [])
            if not neighbors:
                break
            if len(walk) == 1:
                walk.append(rng.choice(neighbors))
            else:
                prev = walk[-2]
                weights = []
                for nb in neighbors:
                    if nb == prev:
                        weights.append(1.0 / self.p)
                    elif nb in adj.get(prev, []):
                        weights.append(1.0)
                    else:
                        weights.append(1.0 / self.q)
                total = sum(weights)
                probs = [w / total for w in weights]
                walk.append(rng.choices(neighbors, weights=probs, k=1)[0])
        return walk

    def get_embeddings(self) -> Dict[str, np.ndarray]:
        """Return learned embeddings.

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
        """Save embeddings to a NumPy ``.npz`` file.

        Parameters
        ----------
        filepath:
            Destination path.
        """
        if self._embeddings is None:
            raise RuntimeError("Call fit() before save().")
        keys = list(self._embeddings.keys())
        vectors = np.stack([self._embeddings[k] for k in keys])
        np.savez(filepath, keys=keys, vectors=vectors)

    @classmethod
    def load(cls, filepath: str) -> "Node2VecBaseline":
        """Load embeddings from a ``.npz`` file.

        Parameters
        ----------
        filepath:
            Source path.

        Returns
        -------
        Node2VecBaseline
        """
        data = np.load(filepath, allow_pickle=True)
        instance = cls()
        instance._embeddings = {
            str(k): v for k, v in zip(data["keys"], data["vectors"])
        }
        return instance


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid function.

    Parameters
    ----------
    x:
        Input value.

    Returns
    -------
    float
    """
    if x >= 0:
        return 1.0 / (1.0 + np.exp(-x))
    exp_x = np.exp(x)
    return exp_x / (1.0 + exp_x)
