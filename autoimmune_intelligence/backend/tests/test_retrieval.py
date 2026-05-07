"""Tests for the hybrid retrieval pipeline.

Run with: pytest tests/test_retrieval.py -v
"""

from __future__ import annotations

import pytest
from app.retrieval.bm25_index import BM25Index, tokenize
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.pipeline import RetrievalPipeline, RetrievedProposition
from app.chunking.sliding_window import chunk_text
from app.routing.classifier import classify_complexity, starting_tier
from app.routing.cost_tracker import compute_cost


# ------------------------------------------------------------------
# Tokenizer
# ------------------------------------------------------------------

class TestTokenize:
    def test_lowercase(self):
        assert "TNF" not in tokenize("TNF-alpha signaling")
        assert "tnf" in tokenize("TNF-alpha signaling") or "tnf-alpha" in tokenize("TNF-alpha signaling")

    def test_strips_punctuation(self):
        tokens = tokenize("IL-6, IL-17, and TNF-α.")
        assert "il-6" in tokens or "il" in tokens

    def test_filters_short_tokens(self):
        tokens = tokenize("a T B cell IL-6")
        assert "a" not in tokens
        assert "b" not in tokens

    def test_returns_list(self):
        result = tokenize("rheumatoid arthritis JAK-STAT pathway")
        assert isinstance(result, list)
        assert len(result) > 0


# ------------------------------------------------------------------
# BM25 Index
# ------------------------------------------------------------------

class TestBM25Index:
    def _make_index(self) -> BM25Index:
        idx = BM25Index()
        docs = [
            ("Rheumatoid arthritis involves TNF-alpha and IL-6 signaling.", {"type": "disease"}),
            ("JAK-STAT pathway dysregulation drives autoimmune inflammation.", {"type": "pathway"}),
            ("Adalimumab targets TNF-alpha in rheumatoid arthritis.", {"type": "therapeutic"}),
            ("Multiple sclerosis involves demyelination and T cell infiltration.", {"type": "disease"}),
        ]
        for text, meta in docs:
            idx.add(text, meta)
        idx.build()
        return idx

    def test_query_returns_results(self):
        idx = self._make_index()
        hits = idx.query("TNF-alpha rheumatoid arthritis")
        # If rank_bm25 is not installed, hits will be empty (graceful fallback)
        try:
            import rank_bm25  # noqa: F401
            assert len(hits) > 0
        except ImportError:
            pytest.skip("rank_bm25 not installed in this environment")
        assert all(isinstance(h, tuple) and len(h) == 2 for h in hits)

    def test_query_ranked_by_score(self):
        idx = self._make_index()
        hits = idx.query("TNF-alpha")
        scores = [h[1] for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_query_no_match_returns_empty_or_zero(self):
        idx = self._make_index()
        hits = idx.query("xyzzy frobnicator")
        # Either empty or all zero scores
        assert all(sc == 0 for _, sc in hits) or len(hits) == 0

    def test_size(self):
        idx = self._make_index()
        assert idx.size == 4

    def test_get_doc(self):
        idx = self._make_index()
        doc = idx.get_doc(0)
        assert "text" in doc
        assert "metadata" in doc

    def test_empty_index(self):
        idx = BM25Index()
        idx.build()
        assert idx.query("anything") == []


# ------------------------------------------------------------------
# Reciprocal Rank Fusion
# ------------------------------------------------------------------

class TestRRF:
    def test_single_list_preserves_order(self):
        ranked = [(0, 1.0), (1, 0.8), (2, 0.5)]
        fused = reciprocal_rank_fusion(ranked)
        assert fused[0][0] == 0  # top doc stays first

    def test_fusion_boosts_shared_docs(self):
        list_a = [(0, 1.0), (1, 0.8), (2, 0.5)]
        list_b = [(0, 0.9), (2, 0.7), (3, 0.3)]
        fused = reciprocal_rank_fusion(list_a, list_b)
        # Doc 0 appears first in both lists — should be first after fusion
        top_ids = [doc_id for doc_id, _ in fused[:2]]
        assert 0 in top_ids

    def test_k_parameter(self):
        ranked = [(0, 1.0), (1, 0.5)]
        fused_k60 = reciprocal_rank_fusion(ranked, k=60)
        fused_k1 = reciprocal_rank_fusion(ranked, k=1)
        # With smaller k, rank differences are larger
        assert fused_k1[0][1] > fused_k60[0][1]

    def test_empty_lists(self):
        fused = reciprocal_rank_fusion([], [])
        assert fused == []

    def test_returns_all_unique_docs(self):
        list_a = [(0, 1.0), (1, 0.5)]
        list_b = [(2, 0.9), (3, 0.4)]
        fused = reciprocal_rank_fusion(list_a, list_b)
        doc_ids = [d for d, _ in fused]
        assert set(doc_ids) == {0, 1, 2, 3}


# ------------------------------------------------------------------
# Retrieval Pipeline (no ML models — BM25 only path)
# ------------------------------------------------------------------

class TestRetrievalPipeline:
    def _make_pipeline(self) -> RetrievalPipeline:
        pipeline = RetrievalPipeline()
        docs = [
            ("TNF-alpha activates NF-kB signaling in macrophages.", {"type": "cytokine_edge", "source": "TNF-alpha"}),
            ("JAK-STAT pathway drives T helper cell differentiation.", {"type": "pathway", "pathway_name": "JAK-STAT"}),
            ("Adalimumab blocks TNF-alpha in rheumatoid arthritis.", {"type": "therapeutic", "drug_name": "Adalimumab"}),
            ("Lupus erythematosus involves B cell hyperactivation.", {"type": "disease", "disease_name": "SLE"}),
            ("Tofacitinib is a JAK inhibitor approved for rheumatoid arthritis.", {"type": "therapeutic"}),
        ]
        for text, meta in docs:
            pipeline.add_document(text, meta)
        pipeline.build()
        return pipeline

    def test_is_ready_after_build(self):
        pipeline = self._make_pipeline()
        assert pipeline.is_ready

    def test_retrieve_returns_propositions(self):
        pipeline = self._make_pipeline()
        results = pipeline.retrieve("TNF-alpha rheumatoid arthritis")
        assert isinstance(results, list)
        assert all(isinstance(r, RetrievedProposition) for r in results)

    def test_retrieve_returns_top_k(self):
        pipeline = self._make_pipeline()
        results = pipeline.retrieve("arthritis", top_k=2)
        assert len(results) <= 2

    def test_retrieve_scores_are_positive(self):
        pipeline = self._make_pipeline()
        results = pipeline.retrieve("TNF-alpha")
        assert all(r.score >= 0 for r in results)

    def test_empty_pipeline_not_ready(self):
        pipeline = RetrievalPipeline()
        assert not pipeline.is_ready

    def test_empty_pipeline_returns_empty(self):
        pipeline = RetrievalPipeline()
        pipeline.build()
        assert pipeline.retrieve("anything") == []


# ------------------------------------------------------------------
# Sliding Window Chunker
# ------------------------------------------------------------------

class TestSlidingWindow:
    def test_short_text_not_chunked(self):
        text = "Short text about IL-6."
        chunks = chunk_text(text, chunk_size=200)
        assert chunks == [text]

    def test_long_text_is_chunked(self):
        words = ["word"] * 300
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1

    def test_overlap_creates_shared_content(self):
        words = [f"w{i}" for i in range(120)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=60, overlap=10)
        assert len(chunks) >= 2
        # The last word of chunk 0 should appear in chunk 1 (overlap)
        chunk0_words = set(chunks[0].split())
        chunk1_words = set(chunks[1].split())
        assert len(chunk0_words & chunk1_words) >= 1

    def test_chunk_word_count(self):
        words = [f"w{i}" for i in range(200)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=50, overlap=0)
        for chunk in chunks[:-1]:  # last chunk may be smaller
            assert len(chunk.split()) == 50


# ------------------------------------------------------------------
# Query Complexity Classifier
# ------------------------------------------------------------------

class TestClassifier:
    def test_simple_query(self):
        assert classify_complexity("What is IL-6?") == "simple"

    def test_medium_query(self):
        result = classify_complexity("What is the mechanism of TNF-alpha signaling?")
        assert result in ("medium", "complex")

    def test_complex_query(self):
        result = classify_complexity(
            "Compare the pathogenesis of rheumatoid arthritis and lupus, "
            "including cytokine interactions and causal mechanisms."
        )
        assert result == "complex"

    def test_starting_tier_simple(self):
        assert starting_tier("simple") == 0

    def test_starting_tier_complex(self):
        assert starting_tier("complex") == 1


# ------------------------------------------------------------------
# Cost Tracker
# ------------------------------------------------------------------

class TestCostTracker:
    def test_haiku_cost_lower_than_sonnet(self):
        haiku_cost = compute_cost("claude-haiku-4-5-20251001", 1000, 500)
        sonnet_cost = compute_cost("claude-sonnet-4-6", 1000, 500)
        assert haiku_cost < sonnet_cost

    def test_zero_tokens_is_zero_cost(self):
        assert compute_cost("claude-haiku-4-5-20251001", 0, 0) == 0.0

    def test_unknown_model_uses_default_pricing(self):
        cost = compute_cost("unknown-model-xyz", 1000, 1000)
        assert cost > 0

    def test_cost_scales_with_tokens(self):
        cost_1k = compute_cost("claude-sonnet-4-6", 1000, 0)
        cost_2k = compute_cost("claude-sonnet-4-6", 2000, 0)
        assert abs(cost_2k - 2 * cost_1k) < 1e-10
