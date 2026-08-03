"""LLM router: pick one model based on query complexity and make a single call.

Tiers: Haiku (simple/medium queries) → Sonnet (complex queries).
"""

from __future__ import annotations

import logging
from typing import Any, Generator

from app.core.ai_client import get_client
from app.routing.classifier import classify_complexity, starting_tier
from app.routing.cost_tracker import check_budget, record_query

logger = logging.getLogger(__name__)

_TIERS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]


def call_with_routing(
    messages: list[dict[str, Any]],
    system: str,
    query_preview: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> tuple[str, str, float]:
    """Call the appropriate model based on query complexity.

    Returns (answer, model_used, cost_usd).
    """
    client = get_client()
    if client is None:
        return ("", "", 0.0)
    if not check_budget():
        logger.warning("Daily budget exceeded")
        return ("", "", 0.0)

    complexity = classify_complexity(query_preview) if query_preview else "simple"
    tier = starting_tier(complexity)
    model = _TIERS[min(tier, len(_TIERS) - 1)]

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )
        answer = response.content[0].text if response.content else ""
        cost = record_query(
            model=model,
            query=query_preview,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        logger.info("Router: model=%s len=%d cost=$%.5f", model, len(answer), cost)
        return (answer, model, cost)
    except Exception:
        logger.warning("Router call failed for model=%s", model, exc_info=True)
        return ("", model, 0.0)


def stream_with_routing(
    messages: list[dict[str, Any]],
    system: str,
    query_preview: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> Generator[str | dict[str, Any], None, None]:
    """Stream response tokens, then yield a terminal metadata dict.

    Yields:
        str: Response tokens as they arrive from the model.
        dict: ``{"_done": True, "model": model_id, "cost": cost_usd}`` as the
              final item. Callers must check ``isinstance(item, dict)`` to
              distinguish tokens from the completion sentinel.

    Model tier is selected by the complexity classifier.
    """
    client = get_client()
    if client is None:
        return

    if not check_budget():
        logger.warning("Daily budget exceeded; refusing stream request")
        yield {"_done": True, "model": "", "cost": 0.0}
        return

    complexity = classify_complexity(query_preview) if query_preview else "simple"
    tier = starting_tier(complexity)
    model = _TIERS[min(tier, len(_TIERS) - 1)]
    cost = 0.0
    try:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
            cost = record_query(
                model=model,
                query=query_preview,
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )
        yield {"_done": True, "model": model, "cost": cost}
    except Exception:
        logger.exception("stream_with_routing failed for model %s", model)
        yield {"_done": True, "model": model, "cost": cost}
        return
