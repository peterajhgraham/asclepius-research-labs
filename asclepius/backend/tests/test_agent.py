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
from app.services.agent_service import AgentEvent, run_agent


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
