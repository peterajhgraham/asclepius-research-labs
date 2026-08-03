"""Regression tests: OpenAI fallback fully removed from llm_service.py.

BUG FIXED: llm_service.py initialised an OpenAI client and branched to
_openai_answer() when ANTHROPIC_API_KEY was absent but OPENAI_API_KEY was
present. This created a hard dependency on the openai package even though
Asclepius Research Labs only uses Anthropic models.

Fixed by:
  - Removing the OpenAI client init block entirely.
  - Removing the elif _openai_client branch from query().
  - Removing the _openai_answer() static method.
  - Removing openai>=1.30.0 from requirements.txt.
  - The error message in extractor.py now references ANTHROPIC_API_KEY.

Tests verify:
  1. 'openai' is never imported by llm_service (import-level regression).
  2. LLMService has no _openai_answer method.
  3. LLMService has no _openai_client attribute after construction.
  4. query() returns a local fallback result when no Anthropic key present
     (not an OpenAI result and not a crash).
  5. The only LLM provider branch is Anthropic.
  6. The error message in extractor.py references ANTHROPIC_API_KEY, not
     OpenAI.
"""

from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import patch

import pytest

import app.services.llm_service as llm_module
from app.services.llm_service import LLMService


# ------------------------------------------------------------------
# 1. openai never imported at module level
# ------------------------------------------------------------------

class TestNoOpenAIImport:
    def test_openai_not_in_llm_service_module_dict(self):
        """The module itself must not hold a reference to openai."""
        module_dict = vars(llm_module)
        assert "openai" not in module_dict, (
            "llm_service.py must not import 'openai' — it was removed as a dependency"
        )

    def test_openai_not_in_sys_modules_after_import(self):
        """Importing llm_service must not pull openai into sys.modules."""
        # Remove openai if it somehow snuck in before this test
        openai_was_present = "openai" in sys.modules
        # Re-import to trigger module-level code
        importlib.reload(llm_module)
        # If openai was not installed to begin with, it should still not be here
        if not openai_was_present:
            assert "openai" not in sys.modules, (
                "Importing llm_service pulled 'openai' into sys.modules"
            )


# ------------------------------------------------------------------
# 2. No _openai_answer method or _openai_client attribute
# ------------------------------------------------------------------

class TestNoOpenAIAttributes:
    def test_no_openai_answer_method(self):
        assert not hasattr(LLMService, "_openai_answer"), (
            "LLMService._openai_answer was removed — this method must not exist"
        )

    def test_no_openai_client_attribute(self):
        svc = LLMService()
        assert not hasattr(svc, "_openai_client"), (
            "LLMService._openai_client was removed — this attribute must not exist"
        )

    def test_no_openai_reference_in_query_method_source(self):
        import inspect
        source = inspect.getsource(LLMService.query)
        assert "openai" not in source.lower(), (
            "LLMService.query() must not reference OpenAI"
        )


# ------------------------------------------------------------------
# 3. query() behaviour without Anthropic key
# ------------------------------------------------------------------

class TestQueryWithoutAnthropicKey:
    def test_returns_result_when_no_key(self):
        """Without an API key, query() must return a result (local fallback), not raise."""
        with patch("app.services.llm_service.settings") as m:
            m.anthropic_api_key = None
            svc = LLMService()
            result = svc.query("What is IL-6?")
        assert result is not None, (
            "query() must return a result even when no API key is configured"
        )

    def test_does_not_call_openai_when_anthropic_key_missing(self):
        """When Anthropic key is missing, the code must not attempt an OpenAI call."""
        openai_called = []

        # If OpenAI is somehow in scope, patch it to detect any calls
        if "openai" in sys.modules:
            original = sys.modules["openai"]
            spy = types.ModuleType("openai")
            class _SpyClient:
                def __init__(self, *a, **kw):
                    openai_called.append(True)
            spy.OpenAI = _SpyClient
            sys.modules["openai"] = spy

        try:
            with patch("app.services.llm_service.settings") as m:
                m.anthropic_api_key = None
                svc = LLMService()
                svc.query("test")
        finally:
            if "openai" in sys.modules and openai_called:
                sys.modules["openai"] = original  # type: ignore[possibly-undefined]

        assert not openai_called, "query() must not invoke OpenAI"


# ------------------------------------------------------------------
# 4. Only two branches: Anthropic or local
# ------------------------------------------------------------------

class TestOnlyAnthropicOrLocal:
    def test_query_method_has_anthropic_branch(self):
        import inspect
        source = inspect.getsource(LLMService.query)
        assert "anthropic_api_key" in source or "anthropic" in source.lower(), (
            "query() must have an Anthropic branch"
        )

    def test_query_method_source_has_no_elif_openai(self):
        import inspect
        source = inspect.getsource(LLMService.query)
        lines = source.lower().splitlines()
        for line in lines:
            assert "elif" not in line or "openai" not in line, (
                f"Found 'elif ... openai ...' line in query() — must be removed:\n{line}"
            )


# ------------------------------------------------------------------
# 5. extractor.py error message references Anthropic
# ------------------------------------------------------------------

class TestExtractorErrorMessage:
    def test_no_openai_mention_in_extractor(self):
        import app.dmi.extractor as extractor_module
        import inspect
        source = inspect.getsource(extractor_module)
        # The old message said "an OpenAI API key" — must now say ANTHROPIC_API_KEY
        assert "openai api key" not in source.lower(), (
            "extractor.py still mentions 'OpenAI API key' — should reference ANTHROPIC_API_KEY"
        )

    def test_anthropic_key_referenced_in_extractor_error(self):
        import app.dmi.extractor as extractor_module
        import inspect
        source = inspect.getsource(extractor_module)
        assert "ANTHROPIC_API_KEY" in source, (
            "extractor.py error message should reference ANTHROPIC_API_KEY"
        )
