"""Extraction tests: the success path, and the ways a good answer used to be thrown away.

Guarded:
  - A working LLM produces a full Mechanism Report (the golden path).
  - Cost tracking failing never discards the model's answer.
  - An answer cut off at the token limit is retried once with a bigger budget.
  - Failures name the real cause (bad key, no credits, wrong model, rate limit,
    overload) in words that are safe to show, never upstream error text.

Run with: pytest tests/test_extraction.py -v
"""

from __future__ import annotations

import json
import types
from unittest.mock import patch

import anthropic
import pytest

from app.dmi import disease_report as dr
from app.dmi import extractor
from app.dmi import target_risk as tr
from app.dmi.errors import ExtractionUnavailableError
from app.services.pubmed_service import PubMedArticle

DISEASE_JSON = {
    "disease_summary": "RA is a chronic autoimmune synovitis driven by TNF and IL-6.",
    "core_pathways": [
        {"name": "TNF signalling", "description": "Drives synovial inflammation.", "evidence_pmids": ["111"]}
    ],
    "causal_genes": ["PTPN22", "HLA-DRB1"],
    "key_cell_types": ["synovial fibroblast"],
    "validated_targets": [{"target": "TNF", "mechanism": "Neutralisation", "evidence_pmids": ["111"]}],
    "failed_targets": [],
    "mechanistic_contradictions": [],
    "biomarkers": ["RF", "anti-CCP"],
    "unresolved_questions": ["Why do some patients not respond to TNF blockade?"],
}


class _Resp:
    def __init__(self, text: str, stop: str = "end_turn"):
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.stop_reason = stop
        self.usage = types.SimpleNamespace(input_tokens=10, output_tokens=20)


class _Client:
    """A stand-in Anthropic client that plays back canned responses (or raises them)."""

    def __init__(self, *outcomes):
        self.messages = self
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _article(pmid: str = "111") -> PubMedArticle:
    return PubMedArticle(pmid=pmid, title="TNF in RA", abstract="TNF drives synovitis.")


def _use(client):
    return patch("app.dmi.extractor._get_anthropic_client", return_value=client)


def _status_error(cls, status: int, message: str = "upstream says nope"):
    # Stand-ins for the SDK's HTTP objects keep these tests independent of which
    # HTTP library the installed SDK version happens to use.
    response = types.SimpleNamespace(status_code=status, headers={}, request=object())
    return cls(message, response=response, body=None)


# ---------------------------------------------------------------------------
# Golden path
# ---------------------------------------------------------------------------

def test_golden_path_full_report():
    client = _Client(_Resp(json.dumps(DISEASE_JSON)))
    with _use(client), patch.object(dr, "fetch_disease_literature", return_value=[_article()]), patch.object(
        dr, "fetch_preprints", return_value=[]
    ):
        report = dr.generate_disease_report("rheumatoid arthritis", "immunology")
    assert report.disease_summary.startswith("RA is a chronic")
    assert [p.name for p in report.core_pathways] == ["TNF signalling"]
    assert report.causal_genes == ["PTPN22", "HLA-DRB1"]
    assert [t.target for t in report.validated_targets] == ["TNF"]
    assert "111" in report.all_citations


def test_golden_path_target_risk():
    target_json = {
        "pathway_position": "upstream",
        "redundancy_level": "low",
        "historical_failures": [],
        "biomarker_alignment": "strong",
        "contradictory_evidence": False,
        "phase2_failures": 0,
        "risk_explanation": "Well validated.",
    }
    client = _Client(_Resp(json.dumps(target_json)))
    with _use(client), patch.object(tr, "fetch_target_literature", return_value=[_article()]), patch.object(
        tr, "fetch_preprints", return_value=[]
    ):
        report = tr.generate_target_risk_report("rheumatoid arthritis", "TNF", "immunology")
    assert report.target == "TNF"
    assert report.risk_explanation == "Well validated."


def test_markdown_fenced_json_is_accepted():
    client = _Client(_Resp("```json\n" + json.dumps(DISEASE_JSON) + "\n```"))
    with _use(client):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert "_fallback" not in out
    assert out["causal_genes"] == ["PTPN22", "HLA-DRB1"]


# ---------------------------------------------------------------------------
# A good answer must survive unrelated failures
# ---------------------------------------------------------------------------

def test_cost_tracking_failure_does_not_discard_the_answer():
    client = _Client(_Resp(json.dumps(DISEASE_JSON)))
    with _use(client), patch("app.dmi.extractor.record_query", side_effect=PermissionError("read-only fs")):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert "_fallback" not in out
    assert out["disease_summary"].startswith("RA is")


def test_unwritable_cost_log_dir_does_not_break_cost_tracking(monkeypatch):
    from app.routing import cost_tracker

    monkeypatch.setattr(cost_tracker, "_log_dir", lambda: (_ for _ in ()).throw(PermissionError("ro")))
    assert cost_tracker._load_daily_total("2099-01-01") == 0.0
    # and recording a query still returns a cost instead of raising
    monkeypatch.setattr(cost_tracker, "_daily_date", "")
    assert cost_tracker.record_query("claude-haiku-4-5", "q", 100, 100) > 0


# ---------------------------------------------------------------------------
# Truncated answers
# ---------------------------------------------------------------------------

def test_truncated_answer_is_retried_with_a_bigger_budget():
    cut_off = _Resp('{"disease_summary": "RA is a chronic', stop="max_tokens")
    client = _Client(cut_off, _Resp(json.dumps(DISEASE_JSON)))
    with _use(client):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert "_fallback" not in out
    assert len(client.calls) == 2
    assert client.calls[1]["max_tokens"] == 2 * client.calls[0]["max_tokens"]


def test_truncated_twice_reports_an_incomplete_answer():
    cut = lambda: _Resp('{"disease_summary": "RA', stop="max_tokens")  # noqa: E731
    client = _Client(cut(), cut())
    with _use(client):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert out["_fallback"] is True
    assert "incomplete" in out["_error"].lower()
    assert len(client.calls) == 2  # exactly one retry, never a loop


def test_invalid_json_without_truncation_is_not_retried():
    client = _Client(_Resp("Sorry, I cannot help with that."))
    with _use(client):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert out["_fallback"] is True
    assert len(client.calls) == 1


def test_json_that_is_not_an_object_is_rejected():
    client = _Client(_Resp("[1, 2, 3]"))
    with _use(client):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert out["_fallback"] is True


# ---------------------------------------------------------------------------
# Failures name their cause, safely
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exc,expected",
    [
        (_status_error(anthropic.AuthenticationError, 401), "API key"),
        (_status_error(anthropic.PermissionDeniedError, 403), "permission"),
        (_status_error(anthropic.NotFoundError, 404), "model"),
        (_status_error(anthropic.RateLimitError, 429), "rate limited"),
        (_status_error(anthropic.InternalServerError, 529), "overloaded"),
        (
            _status_error(anthropic.BadRequestError, 400, "Your credit balance is too low to access the API"),
            "credits",
        ),
        (_status_error(anthropic.BadRequestError, 400, "something else"), "rejected the request"),
        (
            anthropic.APIConnectionError(request=object()),
            "could not be reached",
        ),
        (RuntimeError("boom"), "request failed"),
    ],
)
def test_llm_failures_name_their_cause(exc, expected):
    client = _Client(exc)
    with _use(client):
        out = extractor.extract_disease_mechanisms("ra", "immunology", [_article()])
    assert out["_fallback"] is True
    assert expected.lower() in out["_error"].lower()
    assert "upstream says nope" not in out["_error"]
    assert "credit balance is too low" not in out["_error"]  # paraphrased, never echoed


def test_report_surfaces_the_real_cause_as_unavailable():
    client = _Client(_status_error(anthropic.AuthenticationError, 401))
    with _use(client), patch.object(dr, "fetch_disease_literature", return_value=[_article()]), patch.object(
        dr, "fetch_preprints", return_value=[]
    ):
        with pytest.raises(ExtractionUnavailableError, match="API key"):
            dr.generate_disease_report("rheumatoid arthritis", "immunology")
