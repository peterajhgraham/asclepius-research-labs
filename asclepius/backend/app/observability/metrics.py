"""Prometheus metrics for query observability."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (  # type: ignore[import-untyped]
        Counter,
        Gauge,
        Histogram,
    )

    query_counter = Counter(
        "asclepius_queries_total",
        "Total number of queries processed",
        ["mode", "model"],
    )
    query_latency = Histogram(
        "asclepius_query_latency_seconds",
        "End-to-end query latency in seconds",
        ["mode"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    )
    retrieval_hits_histogram = Histogram(
        "asclepius_retrieval_hits",
        "Number of propositions retrieved per query",
        buckets=[0, 1, 3, 5, 8, 10, 15, 20],
    )
    daily_cost_gauge = Gauge(
        "asclepius_daily_cost_usd",
        "Current-day cumulative LLM spend in USD",
    )
    _ENABLED = True
    logger.info("Prometheus metrics enabled")
except ImportError:
    logger.info("prometheus_client not installed — metrics disabled")
    _ENABLED = False
    query_counter = None  # type: ignore[assignment]
    query_latency = None  # type: ignore[assignment]
    retrieval_hits_histogram = None  # type: ignore[assignment]
    daily_cost_gauge = None  # type: ignore[assignment]


def inc_query(mode: str = "standard", model: str = "unknown") -> None:
    if _ENABLED and query_counter is not None:
        query_counter.labels(mode=mode, model=model).inc()


def observe_latency(seconds: float, mode: str = "standard") -> None:
    if _ENABLED and query_latency is not None:
        query_latency.labels(mode=mode).observe(seconds)


def observe_hits(n: int) -> None:
    if _ENABLED and retrieval_hits_histogram is not None:
        retrieval_hits_histogram.observe(n)


def set_daily_cost(usd: float) -> None:
    if _ENABLED and daily_cost_gauge is not None:
        daily_cost_gauge.set(usd)
