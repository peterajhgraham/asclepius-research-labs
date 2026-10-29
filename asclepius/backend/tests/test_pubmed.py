"""Tests for the PubMed service's failure signalling.

Regression guarded: when NCBI is unreachable, ``search`` used to swallow the
transport error and return ``[]`` — indistinguishable from a genuinely empty
result set. The research agent then read that as "the literature has nothing"
and finalised on thin evidence. ``last_error`` now records the failure.

Run with: pytest tests/test_pubmed.py -v
"""

from __future__ import annotations

import requests

from app.services.pubmed_service import PubMedService


class _BoomSession:
    """A requests-like session whose GET always fails at the transport layer."""

    headers: dict = {}

    def get(self, *a, **k):
        raise requests.ConnectionError("name resolution failed")


def _make_service() -> PubMedService:
    svc = PubMedService(rate_limit_delay=0.0, max_retries=1)
    svc._session = _BoomSession()
    return svc


def test_transport_failure_sets_last_error():
    svc = _make_service()
    results = svc.search("psoriatic arthritis", max_results=5)
    assert results == []
    assert svc.last_error is not None
    assert "failed" in svc.last_error.lower()


def test_clean_run_clears_last_error():
    """A subsequent successful (empty) search must clear a stale error."""
    svc = _make_service()
    svc.search("anything")  # fails -> sets last_error
    assert svc.last_error is not None

    # Swap in a session that returns a valid, empty esearch payload.
    class _EmptySession:
        headers: dict = {}

        def get(self, *a, **k):
            class _Resp:
                status_code = 200
                content = b"<eFetchResult></eFetchResult>"

                def json(self):
                    return {"esearchresult": {"idlist": []}}

                def raise_for_status(self):
                    return None

            return _Resp()

    svc._session = _EmptySession()
    results = svc.search("genuinely empty query")
    assert results == []
    assert svc.last_error is None  # cleared: this is a real empty result, not a failure


# ---------------------------------------------------------------------------
# NCBI rate limiting and API key
# ---------------------------------------------------------------------------

import threading as _threading
import time as _time


class _OkResp:
    status_code = 200
    headers: dict = {}
    content = b""

    def raise_for_status(self):
        return None

    def json(self):
        return {"esearchresult": {"idlist": []}}


def test_api_key_is_sent_when_configured():
    seen = {}

    class _Session:
        headers: dict = {}

        def get(self, url, params=None, timeout=None):
            seen.update(params)
            return _OkResp()

    svc = PubMedService(rate_limit_delay=0.0, max_retries=1, api_key="abc123")
    svc._session = _Session()
    svc._get("https://example.test", {"db": "pubmed"})
    assert seen["api_key"] == "abc123"


def test_no_api_key_param_when_unset():
    seen = {}

    class _Session:
        headers: dict = {}

        def get(self, url, params=None, timeout=None):
            seen.update(params)
            return _OkResp()

    svc = PubMedService(rate_limit_delay=0.0, max_retries=1, api_key="")
    svc._session = _Session()
    svc._get("https://example.test", {"db": "pubmed"})
    assert "api_key" not in seen


def test_requests_are_spaced_across_threads():
    """Concurrent callers must not burst past NCBI's per-IP limit."""
    stamps: list[float] = []

    class _Session:
        headers: dict = {}

        def get(self, url, params=None, timeout=None):
            stamps.append(_time.monotonic())
            return _OkResp()

    svc = PubMedService(rate_limit_delay=0.05, max_retries=1, api_key="")
    svc._session = _Session()
    threads = [_threading.Thread(target=svc._get, args=("https://x.test", {})) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    stamps.sort()
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert len(stamps) == 6
    assert min(gaps) >= 0.04, f"requests bunched up: {gaps}"


def test_429_honours_retry_after_then_succeeds(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.pubmed_service.time.sleep", lambda s: sleeps.append(s))

    class _Limited:
        status_code = 429
        headers = {"Retry-After": "3"}

        def raise_for_status(self):
            raise requests.HTTPError("429")

    responses = [_Limited(), _OkResp()]

    class _Session:
        headers: dict = {}

        def get(self, url, params=None, timeout=None):
            return responses.pop(0)

    svc = PubMedService(rate_limit_delay=0.0, max_retries=3, api_key="")
    svc._session = _Session()
    assert svc._get("https://x.test", {}).status_code == 200
    assert 3.0 in sleeps


def test_429_on_last_attempt_still_fails_loudly(monkeypatch):
    monkeypatch.setattr("app.services.pubmed_service.time.sleep", lambda s: None)

    class _Limited:
        status_code = 429
        headers: dict = {}

        def raise_for_status(self):
            raise requests.HTTPError("429")

    class _Session:
        headers: dict = {}

        def get(self, url, params=None, timeout=None):
            return _Limited()

    svc = PubMedService(rate_limit_delay=0.0, max_retries=2, api_key="")
    svc._session = _Session()
    assert svc.search("anything") == []
    assert svc.last_error is not None
