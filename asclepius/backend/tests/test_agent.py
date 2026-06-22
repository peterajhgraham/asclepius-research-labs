"""Tests for the tool-using research agent.

These focus on the loop's *control flow* — concurrent tool execution, the
cold-start warm-up gate, and graceful finalization — with the Anthropic client
and the underlying tool services faked, so they run without network access or an
API key.

Run with: pytest tests/test_agent.py -v
"""

from __future__ import annotations

import sys
import time
import types

import pytest

import app.services.agent_service as agent
from app.services.agent_service import (
    AgentEvent,
    _dedup_search_results,
    _fingerprint,
    _tool_search_pubmed,
    run_agent,
)


# ------------------------------------------------------------------
# Fakes for the Anthropic SDK
# ------------------------------------------------------------------

class _Block:
    """A stand-in for an Anthropic content block (text, tool_use)."""

    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _Usage:
    input_tokens = 10
    output_tokens = 20


class _Response:
    def __init__(self, content):
        self.content = content
        self.usage = _Usage()


class _FakeMessages:
    """Returns a scripted sequence of responses, one per create() call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self._script:
            return self._script.pop(0)
        # Default: a final_answer so any extra turn terminates cleanly.
        return _Response([
            _Block("tool_use", name="final_answer", id="fin", input={"answer": "done"})
        ])


class _FakeClient:
    def __init__(self, script):
        self.messages = _FakeMessages(script)


@pytest.fixture
def patched_agent(monkeypatch):
    """Wire up a fake anthropic module, budget checks, and a ready retriever.

    Yields a small controller object; set ``controller.script`` before calling
    run_agent to drive the planner's turns.
    """
    state = {"script": []}

    fake_anthropic = types.ModuleType("anthropic")

    def _Anthropic(**kwargs):
        return _FakeClient(state["script"])

    fake_anthropic.Anthropic = _Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

    monkeypatch.setattr(agent.settings, "anthropic_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        "app.routing.cost_tracker.check_budget", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "app.routing.cost_tracker.record_query", lambda *a, **k: 0.0
    )
    # Retriever is already warm — no cold-start delay.
    monkeypatch.setattr(agent, "_ensure_retriever_ready", lambda *a, **k: True)

    return types.SimpleNamespace(state=state)


def _collect(question, **kw):
    return list(run_agent(question, **kw))


def _final_answer(events):
    for e in events:
        if e.type == "final":
            return e.data.get("answer")
    return None


# ------------------------------------------------------------------
# Concurrent tool execution
# ------------------------------------------------------------------

def test_tool_calls_in_one_turn_run_concurrently(patched_agent, monkeypatch):
    """Three retrievals fanned out in a single turn should cost ~one tool
    latency, not the sum — that's the whole point of parallel dispatch."""
    delay = 0.3

    def slow_kb(query, top_k=6):
        time.sleep(delay)
        return {"results": [], "count": 0}

    monkeypatch.setitem(agent._TOOL_FNS, "search_knowledge_base", slow_kb)

    patched_agent.state["script"] = [
        _Response([
            _Block("tool_use", name="search_knowledge_base", id="a", input={"query": "x"}),
            _Block("tool_use", name="search_knowledge_base", id="b", input={"query": "y"}),
            _Block("tool_use", name="search_knowledge_base", id="c", input={"query": "z"}),
        ]),
        _Response([
            _Block("tool_use", name="final_answer", id="fin", input={"answer": "synthesis"}),
        ]),
    ]

    start = time.monotonic()
    events = _collect("compare three things")
    elapsed = time.monotonic() - start

    # Serial execution would take ~3*delay; parallel takes ~1*delay.
    assert elapsed < delay * 2, f"tools did not run concurrently (took {elapsed:.2f}s)"
    assert _final_answer(events) == "synthesis"
    # All three results were reported.
    results = [e for e in events if e.type == "tool_result"]
    assert len(results) == 3


def test_slow_tool_times_out_without_sinking_the_run(patched_agent, monkeypatch):
    """A single hung tool is abandoned at TOOL_TIMEOUT_S; the run still finishes."""
    monkeypatch.setattr(agent, "TOOL_TIMEOUT_S", 0.2)

    def hung_pubmed(query, max_results=5):
        time.sleep(5)
        return {"results": []}

    monkeypatch.setitem(agent._TOOL_FNS, "search_pubmed", hung_pubmed)

    patched_agent.state["script"] = [
        _Response([
            _Block("tool_use", name="search_pubmed", id="a", input={"query": "x"}),
        ]),
        _Response([
            _Block("tool_use", name="final_answer", id="fin", input={"answer": "ok"}),
        ]),
    ]

    start = time.monotonic()
    events = _collect("latest trials")
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, "hung tool was not abandoned promptly"
    results = [e for e in events if e.type == "tool_result"]
    assert any("timed out" in str(r.data.get("result_preview", "")) for r in results)
    assert _final_answer(events) == "ok"


# ------------------------------------------------------------------
# Warm-up gate
# ------------------------------------------------------------------

def test_warmup_is_invoked_before_loop(patched_agent, monkeypatch):
    calls = {"n": 0}

    def fake_warm(*a, **k):
        calls["n"] += 1
        return True

    monkeypatch.setattr(agent, "_ensure_retriever_ready", fake_warm)
    patched_agent.state["script"] = [
        _Response([_Block("tool_use", name="final_answer", id="f", input={"answer": "hi"})]),
    ]

    _collect("anything")
    assert calls["n"] == 1


# ------------------------------------------------------------------
# Graceful finalization
# ------------------------------------------------------------------

def test_final_answer_terminates_loop(patched_agent):
    patched_agent.state["script"] = [
        _Response([
            _Block("text", text="I have enough."),
            _Block("tool_use", name="final_answer", id="f", input={"answer": "the answer"}),
        ]),
    ]
    events = _collect("simple question")
    assert _final_answer(events) == "the answer"
    assert any(e.type == "done" for e in events)


def test_plain_text_with_no_tools_is_coerced_to_final(patched_agent):
    patched_agent.state["script"] = [
        _Response([_Block("text", text="just a direct answer")]),
    ]
    events = _collect("trivial")
    assert _final_answer(events) == "just a direct answer"


# ------------------------------------------------------------------
# Cross-call result deduplication
# ------------------------------------------------------------------

def test_fingerprint_ignores_case_and_whitespace():
    assert _fingerprint("TNF  blocks\nIL-17") == _fingerprint("tnf blocks il-17")
    assert _fingerprint("a") != _fingerprint("b")


def test_dedup_strips_repeats_and_notes_them():
    seen: set[str] = set()
    first = _dedup_search_results(
        {"results": [{"text": "Infliximab targets TNF"}], "count": 1}, seen
    )
    assert first["count"] == 1
    assert "note" not in first

    second = _dedup_search_results(
        {
            "results": [
                {"text": "Infliximab targets TNF"},  # duplicate
                {"text": "Secukinumab targets IL-17A"},  # new
            ],
            "count": 2,
        },
        seen,
    )
    assert second["count"] == 1
    assert second["results"][0]["text"] == "Secukinumab targets IL-17A"
    assert "omitted" in second["note"]


# ------------------------------------------------------------------
# PubMed failure is surfaced, not masked as an empty result
# ------------------------------------------------------------------

def test_pubmed_transport_failure_is_reported_as_error(monkeypatch):
    """When NCBI is unreachable the tool must return an error + note, not a
    silent empty success the planner would read as 'no literature exists'."""
    import app.services.pubmed_service as pubmed_module

    class _DownService:
        last_error = "PubMed request failed: name resolution failed"

        def search(self, query, max_results=5):
            return []

    monkeypatch.setattr(pubmed_module, "pubmed", _DownService())

    out = _tool_search_pubmed("psoriatic arthritis biomarkers")
    assert out["count"] == 0
    assert "error" in out
    assert "unreachable" in out["note"].lower()


def test_pubmed_genuine_empty_is_not_an_error(monkeypatch):
    """A real empty result (NCBI reachable, no hits) stays a clean empty list."""
    import app.services.pubmed_service as pubmed_module

    class _EmptyService:
        last_error = None

        def search(self, query, max_results=5):
            return []

    monkeypatch.setattr(pubmed_module, "pubmed", _EmptyService())

    out = _tool_search_pubmed("a query with no hits")
    assert out["count"] == 0
    assert "error" not in out


def test_dedup_leaves_non_search_payloads_untouched():
    seen: set[str] = set()
    payload = {"ranked": [{"node": "TNF", "score": 1.0}]}
    assert _dedup_search_results(payload, seen) == payload


def test_repeated_queries_are_flagged_but_not_blinded(patched_agent, monkeypatch):
    """The same dominant doc surfacing for two queries should reach the planner
    cleanly the first time and be flagged as overlapping the second — but never
    suppressed to an empty turn, which would starve the closing synthesis."""
    def kb(query, top_k=6):
        return {"results": [{"text": "Infliximab targets TNF-alpha"}], "count": 1}

    monkeypatch.setitem(agent._TOOL_FNS, "search_knowledge_base", kb)

    patched_agent.state["script"] = [
        _Response([
            _Block("tool_use", name="search_knowledge_base", id="a", input={"query": "tnf"}),
            _Block("tool_use", name="search_knowledge_base", id="b", input={"query": "il17"}),
        ]),
        _Response([
            _Block("tool_use", name="final_answer", id="fin", input={"answer": "done"}),
        ]),
    ]

    events = _collect("compare")
    previews = [e.data.get("result_preview", "") for e in events if e.type == "tool_result"]
    # First query returns the doc cleanly (no overlap note).
    assert any("Infliximab" in p and "overlap" not in p for p in previews)
    # Second query still surfaces the doc (not blinded) but flags the overlap.
    assert any("Infliximab" in p and "overlap" in p for p in previews)


def test_dedup_keeps_evidence_when_every_hit_is_a_repeat():
    """A turn whose hits are all repeats must still return them (capped), so the
    planner and the closing synthesis are never left with an empty transcript."""
    seen: set[str] = set()
    payload = {"results": [{"text": "Infliximab targets TNF"}], "count": 1}
    _dedup_search_results(payload, seen)  # first sighting populates `seen`

    again = _dedup_search_results(
        {"results": [{"text": "Infliximab targets TNF"}], "count": 1}, seen
    )
    assert again["count"] == 1
    assert again["results"][0]["text"] == "Infliximab targets TNF"
    assert "overlap" in again["note"]


# ------------------------------------------------------------------
# PubMed over-long queries are simplified, not silently empty
# ------------------------------------------------------------------

def test_simplify_pubmed_query_drops_years_and_filler():
    out = agent._simplify_pubmed_query(
        "TNF inhibitor vs IL-17 inhibitor psoriatic arthritis head-to-head "
        "efficacy safety comparison 2022 2023 2024"
    )
    terms = out.split()
    assert "2024" not in terms and "vs" not in terms and "comparison" not in terms
    assert "TNF" in terms and "IL-17" in terms and "psoriatic" in terms
    assert len(terms) <= 6  # capped so PubMed's AND has a chance of hitting


def test_pubmed_retries_simplified_query_when_verbatim_is_empty(monkeypatch):
    """A long verbatim query that returns nothing should trigger one retry with a
    simplified keyword query; if that hits, those results are returned with a note."""
    import app.services.pubmed_service as pubmed_module

    class _Article:
        pmid, title, abstract, journal, year = "123", "T", "A", "J", "2024"

    class _PickyService:
        last_error = None

        def __init__(self):
            self.calls: list[str] = []

        def search(self, query, max_results=5):
            self.calls.append(query)
            # Only the short (simplified) query returns hits.
            return [_Article()] if len(query.split()) <= 6 else []

    svc = _PickyService()
    monkeypatch.setattr(pubmed_module, "pubmed", svc)

    out = _tool_search_pubmed(
        "TNF inhibitor vs IL-17 inhibitor psoriatic arthritis head-to-head "
        "efficacy safety comparison 2022 2023 2024"
    )
    assert out["count"] == 1
    assert "simplified" in out.get("note", "").lower()
    assert len(svc.calls) == 2  # verbatim attempt, then simplified retry


# ------------------------------------------------------------------
# compare_topics must reject a disease-vs-itself comparison
# ------------------------------------------------------------------

def test_compare_topics_rejects_same_disease_self_comparison(monkeypatch):
    """Two phrases that fuzzy-match the same disease (e.g. two drug classes 'in
    psoriatic arthritis') must not yield a degenerate disease-vs-itself result —
    the tool should steer the planner to search_knowledge_base instead."""
    import app.services.comparative_service as comp

    def fake_compare(a, b):
        return {
            "disease_a": {"disease_name": "Psoriatic arthritis"},
            "disease_b": {"disease_name": "Psoriatic arthritis"},
            "similarity_score": 1.0,
            "summary": "x",
            "overlaps": {},
        }

    monkeypatch.setattr(comp, "compare_diseases", fake_compare)

    out = agent._tool_compare_topics(
        "TNF blockade in psoriatic arthritis", "IL-17 blockade in psoriatic arthritis"
    )
    assert "error" in out and "same disease" in out["error"].lower()
    assert "search_knowledge_base" in out["hint"]


# ------------------------------------------------------------------
# Forced finalization never dead-ends on an empty coerced tool call
# ------------------------------------------------------------------

def test_forced_finalization_falls_back_to_freeform_when_tool_empty(patched_agent, monkeypatch):
    """When the budget is exhausted and the coerced final_answer comes back empty,
    the agent must fall back to a free-form synthesis rather than the canned
    'ran out of time' message."""
    monkeypatch.setitem(
        agent._TOOL_FNS,
        "search_knowledge_base",
        lambda query, top_k=6: {"results": [{"text": "TNF and IL-17 evidence"}], "count": 1},
    )

    patched_agent.state["script"] = [
        # iter 1: planner calls a tool but never final_answer → exhausts max_iters
        _Response([_Block("tool_use", name="search_knowledge_base", id="a", input={"query": "x"})]),
        # forced finalization attempt 1 (tool_choice): empty answer
        _Response([_Block("tool_use", name="final_answer", id="f", input={"answer": "   "})]),
        # forced finalization attempt 2 (free-form): real prose
        _Response([_Block("text", text="Synthesized despite the budget.")]),
    ]

    events = _collect("complex multi-part question", max_iters=1)
    assert _final_answer(events) == "Synthesized despite the budget."


def test_empty_final_answer_triggers_synthesis_not_placeholder(patched_agent, monkeypatch):
    """If the planner terminates the loop with an empty `answer`, the agent must
    NOT emit the '(empty answer)' placeholder — it should recompose from the
    transcript via the forced-synthesis path."""
    monkeypatch.setitem(
        agent._TOOL_FNS,
        "search_knowledge_base",
        lambda query, top_k=6: {"results": [{"text": "amyloid clearance evidence"}], "count": 1},
    )

    patched_agent.state["script"] = [
        # iter 1: gather some evidence
        _Response([_Block("tool_use", name="search_knowledge_base", id="a", input={"query": "x"})]),
        # iter 2: planner calls final_answer but leaves the answer blank
        _Response([_Block("tool_use", name="final_answer", id="f", input={"answer": ""})]),
        # forced finalization (tool_choice) produces the real answer
        _Response([_Block("tool_use", name="final_answer", id="g", input={"answer": "recomposed answer"})]),
    ]

    events = _collect("multi-part question")
    answer = _final_answer(events)
    assert answer == "recomposed answer"
    assert answer != "(empty answer)"
