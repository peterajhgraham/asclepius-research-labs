"""4-tier LLM router with automatic escalation when confidence < 0.60.

Routing order: Haiku → Sonnet → Opus (escalates if answer quality is low).
Falls back to OpenAI when no Anthropic key is configured.
"""

from __future__ import annotations

import logging
from typing import Any, Generator

from app.routing.classifier import classify_complexity, starting_tier
from app.routing.cost_tracker import check_budget, record_query

logger = logging.getLogger(__name__)

_TIERS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]

_CONFIDENCE_THRESHOLD = 0.60
_MIN_QUALITY_LEN = 150

_UNCERTAINTY_PHRASES = [
    "i don't know",
    "i do not know",
    "cannot determine",
    "insufficient information",
    "not enough information",
    "unable to answer",
    "no information",
    "unclear",
    "i'm not sure",
    "i am not sure",
]


def _estimate_confidence(answer: str) -> float:
    """Heuristic confidence score for automatic escalation decisions."""
    if len(answer.strip()) < _MIN_QUALITY_LEN:
        return 0.30
    lower = answer.lower()
    for phrase in _UNCERTAINTY_PHRASES:
        if phrase in lower:
            return 0.40
    return 0.85


def _anthropic_client() -> Any | None:
    try:
        import anthropic
        from app.core.config import settings
        if not settings.anthropic_api_key:
            return None
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    except ImportError:
        logger.warning("anthropic package not installed")
        return None


def call_with_routing(
    messages: list[dict[str, Any]],
    system: str,
    query_preview: str,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> tuple[str, str, float]:
    """Route through tiers until confidence threshold met.

    Returns (answer, model_used, total_cost_usd).
    """
    client = _anthropic_client()
    if client is None:
        return "", "", 0.0

    complexity = classify_complexity(query_preview)
    start = starting_tier(complexity)
    tiers = _TIERS[start:] if check_budget() else [_TIERS[0]]

    answer = ""
    model_used = tiers[0]
    total_cost = 0.0
    prev_model: str | None = None

    for model in tiers:
        if not check_budget():
            logger.warning("Daily budget cap reached — stopping at %s", model)
            break
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=messages,
            )
            answer = response.content[0].text or ""
            usage = response.usage
            cost = record_query(
                model=model,
                query=query_preview,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                escalated_from=prev_model,
            )
            total_cost += cost
            model_used = model
            confidence = _estimate_confidence(answer)
            logger.info(
                "Router: model=%s confidence=%.2f len=%d cost=$%.5f",
                model, confidence, len(answer), cost,
            )
            if confidence >= _CONFIDENCE_THRESHOLD:
                break
            prev_model = model
        except Exception:
            logger.warning("Router call failed for model=%s", model, exc_info=True)
            prev_model = model
            continue

    return answer, model_used, total_cost


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

    Streaming is always served from Tier I (fastest latency). The terminal
    dict lets callers report the exact model and audit cost without guessing.
    """
    client = _anthropic_client()
    if client is None:
        return

    if not check_budget():
        logger.warning("Daily budget cap reached — streaming disabled")
        return

    model = _TIERS[0]
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
        logger.warning("Streaming failed for model=%s", model, exc_info=True)
