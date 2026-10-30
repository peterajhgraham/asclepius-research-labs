"""Guard against Anthropic SDK drift.

Regression guarded: ``requirements.txt`` does not pin ``anthropic``, so a redeploy
installed an SDK whose ``messages.create`` no longer accepts ``temperature``. Every
Mechanism Report and standard query then raised ``TypeError`` before making any
request, and the failure was swallowed into a blank report. The unit tests missed
it because they all used fake clients.

These tests use the REAL installed SDK:
  1. every literal keyword we pass to ``messages.create`` / ``messages.stream`` must
     be accepted by the installed SDK, or go through ``sdk_kwargs``;
  2. the extractor and router run end to end through the real SDK against a local
     stub of the Messages API (including streaming).

Run with: pytest tests/test_sdk_compat.py -v
"""

from __future__ import annotations

import ast
import inspect
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock

import anthropic
import pytest

from app.core.ai_client import sdk_kwargs
from app.dmi import extractor
from app.routing import cost_tracker, router
from app.services.pubmed_service import PubMedArticle

APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"

REPORT = {
    "disease_summary": "RA is a chronic synovitis.",
    "core_pathways": [],
    "causal_genes": ["PTPN22"],
    "key_cell_types": [],
    "validated_targets": [],
    "failed_targets": [],
    "mechanistic_contradictions": [],
    "biomarkers": [],
    "unresolved_questions": [],
}


# ---------------------------------------------------------------------------
# 1. Static check against the installed SDK's signatures
# ---------------------------------------------------------------------------

def _accepted_params() -> dict[str, set[str]]:
    client = anthropic.Anthropic(api_key="sk-test")
    return {
        "create": set(inspect.signature(client.messages.create).parameters),
        "stream": set(inspect.signature(client.messages.stream).parameters),
    }


def test_every_sdk_call_only_passes_keywords_the_installed_sdk_accepts():
    accepted = _accepted_params()
    problems: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            is_sdk_call = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("create", "stream")
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "messages"
            )
            if not is_sdk_call:
                continue
            unknown = {k.arg for k in node.keywords if k.arg} - accepted[node.func.attr]
            if unknown:
                problems.append(
                    f"{path.relative_to(APP_DIR.parent)}:{node.lineno} messages.{node.func.attr}() "
                    f"passes {sorted(unknown)}, which anthropic {anthropic.__version__} rejects; "
                    f"wrap the call's arguments in sdk_kwargs()"
                )
    assert not problems, "\n".join(problems)


# ---------------------------------------------------------------------------
# sdk_kwargs
# ---------------------------------------------------------------------------

def test_sdk_kwargs_drops_unsupported_and_keeps_supported():
    def method(model, max_tokens, system=None):  # no **kwargs
        ...

    out = sdk_kwargs(method, model="m", max_tokens=5, temperature=0.2, system="s")
    assert out == {"model": "m", "max_tokens": 5, "system": "s"}


def test_sdk_kwargs_passes_everything_through_when_the_method_takes_kwargs():
    def method(**kwargs):
        ...

    assert sdk_kwargs(method, temperature=0.2, model="m") == {"temperature": 0.2, "model": "m"}
    assert sdk_kwargs(MagicMock(), temperature=0.2) == {"temperature": 0.2}


def test_sdk_kwargs_warns_once_per_dropped_name(caplog):
    from app.core import ai_client

    ai_client._warned_unsupported.discard("zzz_unknown")

    def method(model):
        ...

    with caplog.at_level("WARNING", logger="app.core.ai_client"):
        sdk_kwargs(method, model="m", zzz_unknown=1)
        sdk_kwargs(method, model="m", zzz_unknown=1)
    assert sum("zzz_unknown" in r.message for r in caplog.records) == 1


# ---------------------------------------------------------------------------
# 2. Real SDK against a local stub of the Messages API
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


class _StubMessagesAPI(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def log_message(self, *args):  # keep test output quiet
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        type(self).seen.append({k: v for k, v in body.items() if k != "messages"})
        if body.get("stream"):
            self._stream()
        else:
            self._json(
                {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": body.get("model"),
                    "content": [{"type": "text", "text": json.dumps(REPORT)}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                }
            )

    def _json(self, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _stream(self):
        events = [
            ("message_start", {"type": "message_start", "message": {
                "id": "msg_1", "type": "message", "role": "assistant", "model": "stub", "content": [],
                "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 7, "output_tokens": 0}}}),
            ("content_block_start", {"type": "content_block_start", "index": 0,
                                     "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                     "delta": {"type": "text_delta", "text": "Hello"}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                     "delta": {"type": "text_delta", "text": " world"}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta",
                               "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                               "usage": {"output_tokens": 5}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        for name, payload in events:
            self.wfile.write(_sse(name, payload))
        self.wfile.flush()


@pytest.fixture
def real_client(monkeypatch, tmp_path):
    """A real anthropic client pointed at a local stub server."""
    _StubMessagesAPI.seen = []
    server = HTTPServer(("127.0.0.1", 0), _StubMessagesAPI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = anthropic.Anthropic(
        api_key="sk-test", base_url=f"http://127.0.0.1:{server.server_port}", max_retries=0
    )
    monkeypatch.setattr(cost_tracker, "_log_dir", lambda: tmp_path)
    monkeypatch.setattr(cost_tracker, "_daily_date", "")
    monkeypatch.setattr(cost_tracker, "_daily_total", 0.0)
    try:
        yield client
    finally:
        server.shutdown()
        server.server_close()


def test_extractor_works_end_to_end_through_the_real_sdk(real_client, monkeypatch):
    monkeypatch.setattr(extractor, "_get_anthropic_client", lambda: real_client)
    out = extractor.extract_disease_mechanisms(
        "rheumatoid arthritis", "immunology", [PubMedArticle(pmid="1", title="t", abstract="a")]
    )
    assert "_fallback" not in out, out.get("_error")
    assert out["causal_genes"] == ["PTPN22"]
    assert _StubMessagesAPI.seen, "the SDK never made a request"
    assert "temperature" not in _StubMessagesAPI.seen[0] or isinstance(
        _StubMessagesAPI.seen[0]["temperature"], (int, float)
    )


def test_router_call_works_end_to_end_through_the_real_sdk(real_client, monkeypatch):
    monkeypatch.setattr(router, "get_client", lambda: real_client)
    answer, model, cost = router.call_with_routing(
        messages=[{"role": "user", "content": "hi"}], system="s", query_preview="what is RA?"
    )
    assert answer and model, "router swallowed an SDK failure"
    assert json.loads(answer)["causal_genes"] == ["PTPN22"]
    assert cost > 0


def test_router_stream_works_end_to_end_through_the_real_sdk(real_client, monkeypatch):
    monkeypatch.setattr(router, "get_client", lambda: real_client)
    items = list(
        router.stream_with_routing(
            messages=[{"role": "user", "content": "hi"}], system="s", query_preview="what is RA?"
        )
    )
    tokens = [i for i in items if isinstance(i, str)]
    done = [i for i in items if isinstance(i, dict)]
    assert "".join(tokens) == "Hello world"
    assert done and done[-1]["model"] and done[-1]["cost"] > 0
