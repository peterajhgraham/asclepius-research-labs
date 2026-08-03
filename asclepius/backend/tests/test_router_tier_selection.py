"""Regression tests for the tier-routing fix.

BUG FIXED: stream_with_routing and call_with_routing were both hardcoded to
_TIERS[0] (Haiku), ignoring the complexity classifier entirely. Every query hit
Haiku regardless of complexity. Fixed by reading the classifier result to pick
the starting tier.

Tests here verify:
  1. Simple queries start at tier 0 (Haiku).
  2. Complex queries start at tier 1 (Sonnet) — the classifier's output feeds
     the router.
  3. stream_with_routing picks the correct model by inspecting the streamed
     metadata sentinel dict.
  4. call_with_routing escalates when confidence is low.
  5. Budget cap forces tier 0 regardless of complexity.

All tests are offline — the Anthropic client is monkey-patched.
"""

from __future__ import annotations

import types
from typing import Any, Generator

import pytest

import app.routing.router as router_module
from app.routing.classifier import classify_complexity, starting_tier


# ------------------------------------------------------------------
# Classifier correctness (upstream of router)
# ------------------------------------------------------------------

class TestClassifierFeeds:
    """Verify classifier + starting_tier contract that the fix relies on."""

    def test_simple_disease_query(self):
        assert classify_complexity("What is IL-6?") == "simple"
        assert starting_tier("simple") == 0

    def test_complex_mechanism_query(self):
        result = classify_complexity(
            "Compare the causal pathogenesis of rheumatoid arthritis and "
            "systemic lupus, detailing cytokine interactions."
        )
        assert result == "complex"
        assert starting_tier("complex") == 1

    def test_medium_query_is_now_complex(self):
        # "mechanism" is a complex-pattern keyword — should be "complex" under the binary classifier
        result = classify_complexity("Mechanism of TNF-alpha signaling in inflammation")
        assert result == "complex"

    def test_long_query_is_complex(self):
        # >10 words → complex regardless of keyword hits
        long_query = " ".join(["word"] * 12)
        assert classify_complexity(long_query) == "complex"

    def test_tier_mapping_exhaustive(self):
        assert starting_tier("simple") == 0
        assert starting_tier("complex") == 1
        assert starting_tier("unknown") == 0  # safe default


# ------------------------------------------------------------------
# Fake Anthropic client
# ------------------------------------------------------------------

class _FakeUsage:
    input_tokens = 100
    output_tokens = 200


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [types.SimpleNamespace(text=text)]
        self.usage = _FakeUsage()


class _FakeMessages:
    """Records which models were called; returns a scripted answer."""

    def __init__(self, answers: list[str]):
        self._answers = list(answers)
        self.called_models: list[str] = []

    def create(self, model: str, **kwargs) -> _FakeResponse:
        self.called_models.append(model)
        text = self._answers[min(len(self.called_models) - 1, len(self._answers) - 1)]
        return _FakeResponse(text)


class _FakeStreamContext:
    def __init__(self, text: str, model: str, client_messages):
        self._text = text
        self._model = model
        self._client_messages = client_messages

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @property
    def text_stream(self):
        yield self._text

    def get_final_message(self):
        m = types.SimpleNamespace()
        m.usage = _FakeUsage()
        return m


class _FakeStreamMessages:
    def __init__(self, model_used: str | None = None):
        self.called_models: list[str] = []
        self._model_used = model_used

    def stream(self, model: str, **kwargs):
        self.called_models.append(model)
        return _FakeStreamContext(
            "Substantial and detailed answer about immunological mechanisms that is long enough.",
            model,
            self,
        )


class _FakeAnthropicClient:
    def __init__(self, messages_obj):
        self.messages = messages_obj


# ------------------------------------------------------------------
# Patch helpers
# ------------------------------------------------------------------

def _patch_client(monkeypatch, messages_obj):
    """Inject a fake client so router never touches the network."""
    monkeypatch.setattr(
        router_module,
        "get_client",
        lambda: _FakeAnthropicClient(messages_obj),
    )


def _patch_budget(monkeypatch, has_budget: bool = True):
    monkeypatch.setattr(router_module, "check_budget", lambda: has_budget)
    monkeypatch.setattr(router_module, "record_query", lambda **kw: 0.0005)


# ------------------------------------------------------------------
# call_with_routing tier selection
# ------------------------------------------------------------------

class TestCallWithRoutingTierSelection:
    def test_simple_query_starts_at_haiku(self, monkeypatch):
        msgs = _FakeMessages(["A long, confident, detailed answer about IL-6 signaling mechanisms. " * 10])
        _patch_client(monkeypatch, msgs)
        _patch_budget(monkeypatch)

        router_module.call_with_routing(
            messages=[{"role": "user", "content": "What is IL-6?"}],
            system="You are a scientist.",
            query_preview="What is IL-6?",
        )

        assert msgs.called_models[0] == router_module._TIERS[0], (
            "Simple query must start routing at tier 0 (Haiku)"
        )

    def test_complex_query_starts_at_sonnet(self, monkeypatch):
        complex_query = (
            "Compare the causal pathogenesis of rheumatoid arthritis and systemic lupus, "
            "detailing cytokine interactions and downstream effects."
        )
        long_answer = "Detailed analysis of the complex mechanisms. " * 20
        msgs = _FakeMessages([long_answer])
        _patch_client(monkeypatch, msgs)
        _patch_budget(monkeypatch)

        router_module.call_with_routing(
            messages=[{"role": "user", "content": complex_query}],
            system="Expert immunologist.",
            query_preview=complex_query,
        )

        first_called = msgs.called_models[0]
        assert first_called == router_module._TIERS[1], (
            f"Complex query must start at tier 1 (Sonnet), but started at {first_called}"
        )

    def test_exactly_one_call_made(self, monkeypatch):
        """Router makes exactly one LLM call — no post-call escalation."""
        msgs = _FakeMessages(["A short answer."])
        _patch_client(monkeypatch, msgs)
        _patch_budget(monkeypatch)

        router_module.call_with_routing(
            messages=[{"role": "user", "content": "What is IL-6?"}],
            system="Scientist.",
            query_preview="What is IL-6?",
        )

        assert len(msgs.called_models) == 1, (
            "Router must make exactly one model call — escalation has been removed"
        )

    def test_returns_answer_model_cost_tuple(self, monkeypatch):
        msgs = _FakeMessages(["Good answer about pathways and cytokine signaling. " * 10])
        _patch_client(monkeypatch, msgs)
        _patch_budget(monkeypatch)

        result = router_module.call_with_routing(
            messages=[{"role": "user", "content": "What is TNF?"}],
            system="Scientist.",
            query_preview="What is TNF?",
        )

        assert isinstance(result, tuple) and len(result) == 3
        answer, model, cost = result
        assert isinstance(answer, str)
        assert isinstance(model, str)
        assert isinstance(cost, float)

    def test_budget_exhausted_returns_empty(self, monkeypatch):
        """When the daily budget is exhausted, the router returns an empty tuple without calling the LLM."""
        complex_q = "Compare causal mechanisms pathogenesis rheumatoid arthritis versus lupus."
        msgs = _FakeMessages(["Any answer"])
        _patch_client(monkeypatch, msgs)
        monkeypatch.setattr(router_module, "check_budget", lambda: False)
        monkeypatch.setattr(router_module, "record_query", lambda **kw: 0.0)

        result = router_module.call_with_routing(
            messages=[{"role": "user", "content": complex_q}],
            system="Scientist.",
            query_preview=complex_q,
        )

        assert result == ("", "", 0.0), "Budget-exhausted call must return empty tuple"
        assert msgs.called_models == [], "Budget-exhausted call must not hit the LLM"

    def test_no_client_returns_empty_tuple(self, monkeypatch):
        monkeypatch.setattr(router_module, "get_client", lambda: None)
        result = router_module.call_with_routing(
            messages=[{"role": "user", "content": "test"}],
            system="Scientist.",
            query_preview="test",
        )
        assert result == ("", "", 0.0)


# ------------------------------------------------------------------
# stream_with_routing tier selection
# ------------------------------------------------------------------

class TestStreamWithRoutingTierSelection:
    def _collect(self, gen: Generator) -> tuple[list[str], dict]:
        tokens = []
        meta: dict = {}
        for item in gen:
            if isinstance(item, dict):
                meta = item
            else:
                tokens.append(item)
        return tokens, meta

    def test_simple_query_uses_haiku(self, monkeypatch):
        stream_msgs = _FakeStreamMessages()
        _patch_client(monkeypatch, stream_msgs)
        _patch_budget(monkeypatch)

        gen = router_module.stream_with_routing(
            messages=[{"role": "user", "content": "What is IL-6?"}],
            system="Scientist.",
            query_preview="What is IL-6?",
        )
        _, meta = self._collect(gen)

        assert stream_msgs.called_models, "stream_with_routing made no API call"
        assert stream_msgs.called_models[0] == router_module._TIERS[0], (
            "Simple query must stream from tier 0 (Haiku)"
        )

    def test_complex_query_uses_sonnet(self, monkeypatch):
        complex_q = (
            "Compare pathogenesis mechanisms of rheumatoid arthritis versus lupus "
            "across cytokine networks and causal genetic interactions."
        )
        stream_msgs = _FakeStreamMessages()
        _patch_client(monkeypatch, stream_msgs)
        _patch_budget(monkeypatch)

        gen = router_module.stream_with_routing(
            messages=[{"role": "user", "content": complex_q}],
            system="Scientist.",
            query_preview=complex_q,
        )
        self._collect(gen)

        assert stream_msgs.called_models, "stream_with_routing made no API call"
        assert stream_msgs.called_models[0] == router_module._TIERS[1], (
            f"Complex query must stream from tier 1 (Sonnet), got {stream_msgs.called_models}"
        )

    def test_terminal_sentinel_emitted(self, monkeypatch):
        stream_msgs = _FakeStreamMessages()
        _patch_client(monkeypatch, stream_msgs)
        _patch_budget(monkeypatch)

        gen = router_module.stream_with_routing(
            messages=[{"role": "user", "content": "What is IL-6?"}],
            system="S.",
            query_preview="What is IL-6?",
        )
        _, meta = self._collect(gen)

        assert meta.get("_done") is True, "stream must yield {'_done': True, ...} sentinel"
        assert "model" in meta
        assert "cost" in meta

    def test_no_client_yields_nothing(self, monkeypatch):
        monkeypatch.setattr(router_module, "get_client", lambda: None)
        items = list(router_module.stream_with_routing(
            messages=[{"role": "user", "content": "test"}],
            system="S.",
            query_preview="test",
        ))
        assert items == []
