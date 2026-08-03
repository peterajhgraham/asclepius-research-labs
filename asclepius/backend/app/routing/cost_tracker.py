"""Per-query cost tracking with JSONL audit logs and daily budget enforcement."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

# Anthropic pricing per million tokens (May 2026)
_PRICE_PER_M: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.80,   "output": 4.00},
    "claude-haiku-4-5":          {"input": 0.80,   "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00,   "output": 15.00},
    "claude-opus-4-7":           {"input": 15.00,  "output": 75.00},
    # OpenAI fallback models
    "gpt-4o":                    {"input": 5.00,   "output": 15.00},
    "gpt-4o-mini":               {"input": 0.15,   "output": 0.60},
}

_lock = Lock()
_daily_total: float = 0.0
_daily_date: str = ""


def _log_dir() -> Path:
    p = Path(__file__).parents[2] / "data" / "routing_logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a given model and token counts."""
    prices = _PRICE_PER_M.get(model, {"input": 5.0, "output": 15.0})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


def record_query(
    model: str,
    query: str,
    input_tokens: int,
    output_tokens: int,
    escalated_from: str | None = None,
    extra: dict[str, Any] | None = None,
) -> float:
    """Append a JSONL cost record and return the query cost in USD."""
    global _daily_total, _daily_date

    cost = compute_cost(model, input_tokens, output_tokens)

    with _lock:
        today = date.today().isoformat()
        if _daily_date != today:
            _daily_date = today
            _daily_total = _load_daily_total(today)
        _daily_total += cost
        captured_total = _daily_total

        record: dict[str, Any] = {
            "date": today,
            "model": model,
            "query_preview": query[:100],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "daily_total_usd": round(captured_total, 6),
        }
        if escalated_from:
            record["escalated_from"] = escalated_from
        if extra:
            record.update(extra)

        try:
            log_file = _log_dir() / f"{today}.jsonl"
            with log_file.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            logger.warning("Failed to write cost log", exc_info=True)

    logger.debug(
        "Query cost $%.6f | daily total $%.4f | model=%s",
        cost, _daily_total, model,
    )
    return cost


def get_daily_total() -> float:
    """Return today's cumulative LLM spend in USD."""
    with _lock:
        return _daily_total


def check_budget(budget_override: float | None = None) -> bool:
    """Return True if spend is under the daily budget cap."""
    global _daily_total, _daily_date
    today = date.today().isoformat()
    with _lock:
        if _daily_date != today:
            _daily_date = today
            _daily_total = _load_daily_total(today)
        if budget_override is not None:
            return _daily_total < budget_override
        from app.core.config import settings
        return _daily_total < settings.daily_budget_usd


def _load_daily_total(day: str) -> float:
    log_file = _log_dir() / f"{day}.jsonl"
    if not log_file.exists():
        return 0.0
    total = 0.0
    try:
        for line in log_file.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                total += record.get("cost_usd", 0.0)
    except Exception:
        logger.warning("Failed to load daily cost total from %s", log_file)
    return total
