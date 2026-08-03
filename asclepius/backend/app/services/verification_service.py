"""Figure-grounded answer verification.

After an answer has been generated against retrieved propositions, this
service does a second pass: it re-fetches every figure / table raster
cited in the retrieval results and asks Claude Sonnet vision whether
the actual image content supports each quantitative or factual claim
in the answer.

This is the highest-leverage trust pass for a scientific RAG tool — the
captioner can paraphrase a figure inaccurately, the LLM can confidently
fabricate a number that the figure does not actually show, and neither
text-only retrieval nor text-only generation can catch it. A second
look at the pixels does.

The pass is opt-in (`verify=True` on `/query` or the agent endpoint) so
the latency / cost only applies when the caller actually needs it.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_VERIFIER_MODEL = "claude-sonnet-4-6"
MAX_IMAGES_TO_VERIFY = 4


@dataclass
class VerificationResult:
    verdict: str           # supported | partially_supported | unsupported | no_images
    confidence: float      # 0..1
    notes: str
    revised_answer: str    # answer with unsupported claims marked
    images_inspected: int
    cost_usd: float = 0.0
    model_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "notes": self.notes,
            "revised_answer": self.revised_answer,
            "images_inspected": self.images_inspected,
            "cost_usd": self.cost_usd,
            "model_used": self.model_used,
        }


_VERIFIER_SYSTEM = (
    "You are a scientific fact-checker verifying claims in a generated answer against "
    "the actual figure and table images cited.\n\n"
    "Check each quantitative or factual claim against what the images actually show, "
    "then output a single JSON object with exactly these fields:\n"
    '{"verdict": "supported"|"partially_supported"|"unsupported", '
    '"confidence": <decimal number 0.0-1.0, not a text label>, '
    '"notes": "1-3 sentence summary", '
    '"revised_answer": "answer text with unsupported claims marked [unverified] '
    'and unclear claims marked [uncertain]"}\n\n'
    "Output only valid JSON. No commentary, no markdown fences."
)


def verify_against_figures(
    answer: str,
    image_hashes: list[str],
) -> VerificationResult:
    """Verify an answer against the figures it cites. Returns the original answer
    annotated with `[unverified]` / `[uncertain]` markers and a verdict."""

    if not image_hashes:
        return VerificationResult(
            verdict="no_images",
            confidence=0.0,
            notes="No figures or tables were cited in the retrieval results; "
                  "verification skipped.",
            revised_answer=answer,
            images_inspected=0,
        )

    if not settings.anthropic_api_key:
        return VerificationResult(
            verdict="skipped",
            confidence=0.0,
            notes="Verification requires ANTHROPIC_API_KEY; skipped.",
            revised_answer=answer,
            images_inspected=0,
        )

    from app.routing.cost_tracker import check_budget, record_query
    from app.storage.image_store import get_image_store

    if not check_budget():
        return VerificationResult(
            verdict="skipped",
            confidence=0.0,
            notes="Daily budget exhausted; verification skipped.",
            revised_answer=answer,
            images_inspected=0,
        )

    # Dedupe and cap
    unique_hashes: list[str] = []
    for h in image_hashes:
        if h and h not in unique_hashes:
            unique_hashes.append(h)
        if len(unique_hashes) >= MAX_IMAGES_TO_VERIFY:
            break

    store = get_image_store()
    vision_blocks: list[dict[str, Any]] = []
    for h in unique_hashes:
        loaded = store.read(h)
        if loaded is None:
            continue
        data, mt = loaded
        vision_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mt,
                "data": base64.b64encode(data).decode(),
            },
        })

    if not vision_blocks:
        return VerificationResult(
            verdict="skipped",
            confidence=0.0,
            notes="Cited figures could not be loaded from the image store.",
            revised_answer=answer,
            images_inspected=0,
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        content_blocks = [{"type": "text", "text": "Cited figures / tables:"}, *vision_blocks]
        content_blocks.append({
            "type": "text",
            "text": (
                f"Answer to verify:\n---\n{answer}\n---\n\n"
                "Return ONLY the JSON object as specified."
            ),
        })

        response = client.messages.create(
            model=_VERIFIER_MODEL,
            max_tokens=2048,
            system=_VERIFIER_SYSTEM,
            messages=[{"role": "user", "content": content_blocks}],
        )
        raw = response.content[0].text if response.content else "{}"
        cost = 0.0
        try:
            cost = record_query(
                model=_VERIFIER_MODEL,
                query=f"verify: {answer[:60]}",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning("Verification call failed", exc_info=True)
        return VerificationResult(
            verdict="skipped",
            confidence=0.0,
            notes=f"Verification call failed: {e}",
            revised_answer=answer,
            images_inspected=len(vision_blocks),
        )

    parsed = _parse_verifier_json(raw)
    return VerificationResult(
        verdict=parsed.get("verdict") or "partially_supported",
        confidence=_safe_confidence(parsed.get("confidence")),
        notes=str(parsed.get("notes") or "")[:1000],
        revised_answer=str(parsed.get("revised_answer") or answer),
        images_inspected=len(vision_blocks),
        cost_usd=round(cost, 6),
        model_used=_VERIFIER_MODEL,
    )


def _safe_confidence(val) -> float:
    if val is None:
        return 0.5
    try:
        return float(val)
    except (TypeError, ValueError):
        # Text labels → numeric
        mapping = {"high": 0.9, "medium": 0.6, "low": 0.3}
        return mapping.get(str(val).lower(), 0.5)


def _parse_verifier_json(raw: str) -> dict[str, Any]:
    """Forgiving JSON extraction — the verifier sometimes wraps its output in
    markdown fences or prefix text despite the explicit instruction."""
    import json
    import re

    s = (raw or "").strip()
    # Strip ```json ... ``` fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
    if fenced:
        s = fenced.group(1)
    # Otherwise grab the first {...} block
    if not s.startswith("{"):
        brace = re.search(r"\{.*\}", s, re.DOTALL)
        if brace:
            s = brace.group(0)
    try:
        return json.loads(s)
    except Exception:
        return {}
