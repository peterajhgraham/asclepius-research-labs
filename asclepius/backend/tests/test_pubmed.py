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
