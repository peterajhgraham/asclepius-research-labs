"""Failure-mode regression tests: an outage must never look like an empty answer.

Bugs guarded:
  1. PubMed unreachable -> the Mechanism Report returned 200 "No literature
     found ... verify the disease name". Now it is a 503 with a clear message.
  2. Missing ANTHROPIC_API_KEY / failed LLM call -> the extractor returned an
     empty structure (flagged ``_fallback``) that nothing read, so the user got
     a blank report. Now it is a 503 saying the AI service is unavailable.
  3. A query blocked on the retrieval build lock for as long as the model
     download took. Now it waits a bounded time and answers without retrieval.

Run with: pytest tests/test_failure_modes.py -v
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from app.dmi import disease_report as dr
from app.dmi import pubmed as dmi_pubmed
from app.dmi import target_risk as tr
from app.dmi.errors import (
    ExtractionUnavailableError,
    LiteratureUnavailableError,
    ReportUnavailableError,
)
from app.services.pubmed_service import PubMedArticle, PubMedService


def _article(pmid: str = "111") -> PubMedArticle:
    return PubMedArticle(pmid=pmid, title="t", abstract="a")


class _BoomSession:
    headers: dict = {}

    def get(self, *a, **k):
        raise requests.ConnectionError("name resolution failed")


@pytest.fixture
def pubmed_down(monkeypatch):
    """A PubMed service whose every request fails at the transport layer."""
    svc = PubMedService(rate_limit_delay=0.0, max_retries=1)
    svc._session = _BoomSession()
    monkeypatch.setattr(dmi_pubmed, "_pubmed", svc)
    return svc


@pytest.fixture
def pubmed_empty(monkeypatch):
    """A PubMed service that is healthy but finds nothing."""

    class _Resp:
        status_code = 200
        content = b"<eFetchResult></eFetchResult>"

        def json(self):
            return {"esearchresult": {"idlist": []}}

        def raise_for_status(self):
            return None

    class _Session:
        headers: dict = {}

        def get(self, *a, **k):
            return _Resp()

    svc = PubMedService(rate_limit_delay=0.0, max_retries=1)
    svc._session = _Session()
    monkeypatch.setattr(dmi_pubmed, "_pubmed", svc)
    return svc


# ---------------------------------------------------------------------------
# PubMed: outage vs. genuinely empty
# ---------------------------------------------------------------------------

def test_disease_literature_raises_when_pubmed_is_down(pubmed_down):
    with pytest.raises(LiteratureUnavailableError):
        dmi_pubmed.fetch_disease_literature("rheumatoid arthritis")


def test_target_literature_raises_when_pubmed_is_down(pubmed_down):
    with pytest.raises(LiteratureUnavailableError):
        dmi_pubmed.fetch_target_literature("rheumatoid arthritis", "TNF")


def test_empty_result_is_not_an_error(pubmed_empty):
    assert dmi_pubmed.fetch_disease_literature("zzz not a disease") == []
    assert dmi_pubmed.fetch_target_literature("zzz", "qqq") == []


def test_efetch_failure_sets_last_error():
    """esearch succeeds but efetch fails: that is an outage too, not 'no articles'."""
    svc = PubMedService(rate_limit_delay=0.0, max_retries=1)

    def fake_get(url, params):
        if "esearch" in url:
            resp = MagicMock()
            resp.json.return_value = {"esearchresult": {"idlist": ["1", "2"]}}
            return resp
        raise requests.HTTPError("efetch 500")

    svc._get = fake_get
    assert svc.search("psoriasis") == []
    assert svc.last_error is not None


def test_unparseable_xml_sets_last_error():
    svc = PubMedService(rate_limit_delay=0.0, max_retries=1)
    assert svc._parse_xml(b"<not-xml") == []
    assert svc.last_error is not None


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def test_disease_report_503s_when_pubmed_and_preprints_are_empty(pubmed_down):
    with patch.object(dr, "fetch_preprints", return_value=[]):
        with pytest.raises(LiteratureUnavailableError):
            dr.generate_disease_report("rheumatoid arthritis", "immunology")


def test_disease_report_survives_pubmed_outage_if_preprints_exist(pubmed_down):
    extracted = {"disease_summary": "from preprints", "core_pathways": []}
    with patch.object(dr, "fetch_preprints", return_value=[_article("p1")]), patch.object(
        dr, "extract_disease_mechanisms", return_value=extracted
    ):
        report = dr.generate_disease_report("rheumatoid arthritis", "immunology")
    assert report.disease_summary == "from preprints"


def test_disease_report_genuinely_empty_still_says_no_literature(pubmed_empty):
    with patch.object(dr, "fetch_preprints", return_value=[]):
        report = dr.generate_disease_report("zzz not a disease", "immunology")
    assert "No literature found" in report.disease_summary


def test_disease_report_raises_when_extraction_fell_back():
    fallback = {"disease_summary": "", "_fallback": True, "_error": "AI not configured"}
    with patch.object(dr, "fetch_disease_literature", return_value=[_article()]), patch.object(
        dr, "fetch_preprints", return_value=[]
    ), patch.object(dr, "extract_disease_mechanisms", return_value=fallback):
        with pytest.raises(ExtractionUnavailableError, match="AI not configured"):
            dr.generate_disease_report("rheumatoid arthritis", "immunology")


def test_target_risk_503s_when_pubmed_and_preprints_are_empty(pubmed_down):
    with patch.object(tr, "fetch_preprints", return_value=[]):
        with pytest.raises(LiteratureUnavailableError):
            tr.generate_target_risk_report("rheumatoid arthritis", "TNF", "immunology")


def test_target_risk_raises_when_extraction_fell_back():
    fallback = {"_fallback": True, "_error": "AI request failed"}
    with patch.object(tr, "fetch_target_literature", return_value=[_article()]), patch.object(
        tr, "fetch_preprints", return_value=[]
    ), patch.object(tr, "extract_target_assessment", return_value=fallback):
        with pytest.raises(ExtractionUnavailableError, match="AI request failed"):
            tr.generate_target_risk_report("rheumatoid arthritis", "TNF", "immunology")


def test_extractor_fallback_carries_a_reason():
    """The extractor must say WHY it produced nothing, so the route can show it."""
    from app.dmi.extractor import extract_disease_mechanisms, extract_target_assessment

    with patch("app.dmi.extractor._get_anthropic_client", return_value=None):
        d = extract_disease_mechanisms("ra", "immunology", [_article()])
        t = extract_target_assessment("ra", "TNF", "immunology", [_article()])
    for out in (d, t):
        assert out["_fallback"] is True
        assert "ANTHROPIC_API_KEY" in out["_error"]

    boom = MagicMock()
    boom.messages.create.side_effect = RuntimeError("401 invalid x-api-key")
    with patch("app.dmi.extractor._get_anthropic_client", return_value=boom):
        d = extract_disease_mechanisms("ra", "immunology", [_article()])
    assert d["_fallback"] is True and d["_error"]
    assert "401" not in d["_error"]  # never leak upstream error text to the UI


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.mark.parametrize(
    "path,patch_target,body",
    [
        ("/dmi/disease-report", "app.dmi.routes.generate_disease_report", {"disease_name": "ra"}),
        (
            "/dmi/target-risk",
            "app.dmi.routes.generate_target_risk_report",
            {"disease_name": "ra", "target_name": "TNF"},
        ),
    ],
)
def test_routes_return_503_with_a_readable_message(path, patch_target, body):
    exc = ReportUnavailableError("PubMed could not be reached. Please try again in a moment.")
    with patch(patch_target, side_effect=exc):
        resp = _client().post(path, json=body)
    assert resp.status_code == 503
    assert "PubMed could not be reached" in resp.json()["detail"]


def test_routes_still_500_on_unexpected_errors():
    with patch("app.dmi.routes.generate_disease_report", side_effect=ValueError("bug")):
        resp = _client().post("/dmi/disease-report", json={"disease_name": "ra"})
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Retrieval: bounded wait instead of blocking on the build lock
# ---------------------------------------------------------------------------

def test_get_pipeline_wait_is_bounded_while_a_build_is_running(monkeypatch):
    from app.services import retrieval_service as rs

    monkeypatch.setattr(rs, "_pipeline", None)
    started = threading.Event()
    release = threading.Event()

    def hold_lock():
        with rs._build_lock:
            started.set()
            release.wait(10)

    t = threading.Thread(target=hold_lock, daemon=True)
    t.start()
    assert started.wait(5)
    try:
        t0 = time.monotonic()
        pipeline = rs.get_pipeline(wait=0.2)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, "get_pipeline(wait=...) blocked on the build lock"
        assert not pipeline.is_ready
    finally:
        release.set()
        t.join(5)


def test_retrieve_returns_no_hits_instead_of_hanging_during_build(monkeypatch):
    from app.core.config import settings
    from app.services import retrieval_service as rs

    monkeypatch.setattr(rs, "_pipeline", None)
    monkeypatch.setattr(settings, "retrieval_wait_seconds", 0.2)
    started = threading.Event()
    release = threading.Event()

    def hold_lock():
        with rs._build_lock:
            started.set()
            release.wait(10)

    t = threading.Thread(target=hold_lock, daemon=True)
    t.start()
    assert started.wait(5)
    try:
        t0 = time.monotonic()
        assert rs.retrieve("what drives synovial inflammation?") == []
        assert time.monotonic() - t0 < 2.0
    finally:
        release.set()
        t.join(5)


def test_get_pipeline_without_wait_still_builds_once(monkeypatch):
    """Default behaviour (warm-up thread, ingestion) is unchanged: wait for the build."""
    from app.services import retrieval_service as rs

    built = MagicMock()
    built.is_ready = True
    monkeypatch.setattr(rs, "_pipeline", None)
    monkeypatch.setattr(rs, "_build_started", False)
    with patch.object(rs, "_build_pipeline", return_value=built) as build:
        assert rs.get_pipeline() is built
        assert rs.get_pipeline() is built
    assert build.call_count == 1
