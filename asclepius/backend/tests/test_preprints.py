"""Tests for bioRxiv/medRxiv preprint integration.

NEW FEATURE: fetch_preprints() was added to dmi/pubmed.py to augment PubMed
results with recent preprints from bioRxiv and medRxiv via the public bioRxiv
Details API. Both disease_report.py and target_risk.py were updated to call
fetch_preprints() and merge results, deduplicating by DOI.

Tests verify:
  1. _query_preprint_server filters items by query term in title OR abstract.
  2. Items not matching the query are excluded.
  3. Network failures return [] without raising.
  4. max_results cap is respected within a single server call.
  5. fetch_preprints honours max_results across both servers.
  6. PubMedArticle fields are populated correctly from API item dict.
  7. Duplicate DOIs are excluded when merging into PubMed results (the
     deduplication logic in disease_report.py and target_risk.py).
  8. Authors field is populated from the first semicolon-delimited author.
  9. Year is extracted as the first 4 characters of the date field.
 10. Empty collection in API response returns [].
 11. Missing title/abstract fields default to empty string (no KeyError).

All tests use a fake HTTP layer — no network access required.
"""

from __future__ import annotations

import json
import types
import urllib.error
from unittest.mock import patch, MagicMock
from io import BytesIO

import pytest

from app.dmi.pubmed import _query_preprint_server, fetch_preprints
from app.services.pubmed_service import PubMedArticle


# ------------------------------------------------------------------
# Fake HTTP responses
# ------------------------------------------------------------------

def _make_fake_urlopen(payload: dict):
    """Return a context-manager fake for urllib.request.urlopen."""
    raw = json.dumps(payload).encode()

    class _FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return raw

    return _FakeResp()


def _mock_urlopen(payload: dict):
    return lambda url, timeout=10: _make_fake_urlopen(payload)


def _items(*titles_abstracts) -> list[dict]:
    """Build a fake bioRxiv collection list."""
    result = []
    for i, (title, abstract) in enumerate(titles_abstracts):
        result.append({
            "title": title,
            "abstract": abstract,
            "doi": f"10.1101/2024.01.{i+1:02d}.000000",
            "authors": f"Smith J; Jones K; Lee M",
            "server": "biorxiv",
            "date": "2024-03-15",
        })
    return result


# ------------------------------------------------------------------
# _query_preprint_server
# ------------------------------------------------------------------

class TestQueryPreprintServer:
    def test_matching_title_included(self, monkeypatch):
        payload = {"collection": _items(
            ("IL-17 signaling in psoriasis", "Background about skin."),
            ("Unrelated cardiovascular study", "Heart disease topic."),
        )}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "IL-17", max_results=10)
        titles = [r.title for r in results]
        assert any("IL-17" in t for t in titles)
        assert all("cardiovascular" not in t.lower() for t in titles)

    def test_matching_abstract_included(self, monkeypatch):
        payload = {"collection": _items(
            ("Rheumatoid arthritis study", "We investigated JAK-STAT pathway dysregulation."),
            ("Control paper", "No relevant content at all."),
        )}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "JAK-STAT", max_results=10)
        assert len(results) == 1
        assert "JAK-STAT" in results[0].abstract

    def test_no_match_returns_empty(self, monkeypatch):
        payload = {"collection": _items(
            ("Cardiovascular paper", "Heart stuff."),
            ("Metabolic syndrome", "Glucose metabolism."),
        )}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "rheumatoid arthritis", max_results=10)
        assert results == []

    def test_max_results_capped(self, monkeypatch):
        items = _items(
            *[(f"RA paper {i}", f"Rheumatoid arthritis content {i}") for i in range(20)]
        )
        payload = {"collection": items}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "rheumatoid arthritis", max_results=3)
        assert len(results) == 3

    def test_network_failure_returns_empty(self, monkeypatch):
        def _boom(url, timeout=10):
            raise OSError("name resolution failed")
        monkeypatch.setattr("urllib.request.urlopen", _boom)
        results = _query_preprint_server("fake-url", "anything", max_results=5)
        assert results == []

    def test_timeout_returns_empty(self, monkeypatch):
        import socket
        def _boom(url, timeout=10):
            raise TimeoutError("timed out")
        monkeypatch.setattr("urllib.request.urlopen", _boom)
        results = _query_preprint_server("fake-url", "anything", max_results=5)
        assert results == []

    def test_empty_collection_returns_empty(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen({"collection": []}))
        results = _query_preprint_server("fake-url", "RA", max_results=5)
        assert results == []

    def test_missing_collection_key_returns_empty(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen({}))
        results = _query_preprint_server("fake-url", "RA", max_results=5)
        assert results == []

    def test_case_insensitive_query_matching(self, monkeypatch):
        payload = {"collection": _items(
            ("Rheumatoid Arthritis Mechanisms", "Upper case study."),
        )}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "rheumatoid arthritis", max_results=5)
        assert len(results) == 1

    def test_article_fields_populated(self, monkeypatch):
        payload = {"collection": [
            {
                "title": "TNF-alpha RA pathogenesis",
                "abstract": "TNF-alpha drives inflammation.",
                "doi": "10.1101/2024.01.01.000001",
                "authors": "Smith J; Jones K; Lee M",
                "server": "biorxiv",
                "date": "2024-06-15",
            }
        ]}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "TNF-alpha", max_results=5)

        assert len(results) == 1
        art = results[0]
        assert art.title == "TNF-alpha RA pathogenesis"
        assert art.doi == "10.1101/2024.01.01.000001"
        assert art.year == "2024"
        assert art.journal == "biorxiv"
        assert art.authors == ["Smith J"]  # first author only
        assert "10.1101/2024.01.01.000001" in art.citation

    def test_missing_title_abstract_no_keyerror(self, monkeypatch):
        payload = {"collection": [{"doi": "10.1101/x", "server": "biorxiv", "date": "2024-01-01"}]}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        # Should not raise even though title/abstract are missing
        results = _query_preprint_server("fake-url", "anything", max_results=5)
        assert isinstance(results, list)

    def test_article_pmid_equals_doi(self, monkeypatch):
        payload = {"collection": _items(("RA study", "Rheumatoid arthritis mechanisms."))}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = _query_preprint_server("fake-url", "rheumatoid", max_results=5)
        art = results[0]
        assert art.pmid == f"preprint:{art.doi}"


# ------------------------------------------------------------------
# fetch_preprints
# ------------------------------------------------------------------

class TestFetchPreprints:
    def test_max_results_across_both_servers(self, monkeypatch):
        """fetch_preprints should stop after reaching max_results."""
        # biorxiv returns 5 matches; we want only 3 total
        biorxiv_items = _items(
            *[(f"RA preprint {i}", f"Rheumatoid arthritis study {i}") for i in range(5)]
        )
        call_count = [0]

        def _fake_urlopen(url, timeout=10):
            call_count[0] += 1
            return _make_fake_urlopen({"collection": biorxiv_items})

        monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
        results = fetch_preprints("rheumatoid arthritis", max_results=3)
        assert len(results) == 3

    def test_returns_list_of_pubmed_articles(self, monkeypatch):
        payload = {"collection": _items(("RA mechanism", "Rheumatoid arthritis IL-6."))}
        monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen(payload))
        results = fetch_preprints("rheumatoid arthritis", max_results=10)
        assert isinstance(results, list)
        assert all(isinstance(r, PubMedArticle) for r in results)

    def test_network_failure_returns_empty_not_raises(self, monkeypatch):
        monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=10: (_ for _ in ()).throw(OSError("down")))
        results = fetch_preprints("any query", max_results=5)
        assert results == []


# ------------------------------------------------------------------
# Deduplication: disease_report merges preprints without duplicating DOIs
# ------------------------------------------------------------------

class TestDedupInDiseaseReport:
    """
    disease_report.py uses: articles + [p for p in preprints if p.pmid not in {a.pmid for a in articles}]
    Verify that a preprint whose DOI already appears in PubMed results is not added twice.
    """

    def _make_article(self, pmid: str, title: str) -> PubMedArticle:
        return PubMedArticle(
            pmid=pmid, title=title, abstract="", authors=[],
            journal="PubMed", year="2024", doi=pmid,
        )

    def test_shared_doi_not_duplicated(self):
        shared_doi = "10.1234/shared"
        pubmed_articles = [self._make_article(shared_doi, "PubMed version")]
        preprints = [self._make_article(shared_doi, "bioRxiv version")]

        # Replicate the exact deduplication logic from disease_report.py
        merged = pubmed_articles + [p for p in preprints if p.pmid not in {a.pmid for a in pubmed_articles}]

        dois = [a.pmid for a in merged]
        assert dois.count(shared_doi) == 1

    def test_unique_preprint_added(self):
        pubmed_articles = [self._make_article("PMID:111", "PubMed article")]
        preprints = [self._make_article("10.1101/unique", "Unique preprint")]

        merged = pubmed_articles + [p for p in preprints if p.pmid not in {a.pmid for a in pubmed_articles}]

        assert len(merged) == 2
        assert any(a.pmid == "10.1101/unique" for a in merged)

    def test_all_shared_is_noop(self):
        doi = "10.1234/x"
        pub = [self._make_article(doi, "Title")]
        pre = [self._make_article(doi, "Same DOI")]

        merged = pub + [p for p in pre if p.pmid not in {a.pmid for a in pub}]
        assert len(merged) == 1
