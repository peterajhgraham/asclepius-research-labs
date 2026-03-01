"""LLM service that answers autoimmune-disease questions.

Uses the local knowledge base for retrieval.  When an OpenAI API key is
configured, the matched KB context is sent to the LLM for a synthesised
answer.  Without an API key the service falls back to returning the
best-matching KB entry directly — no external dependency required.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.models.schema import QueryResponse
from app.services.query_engine import search

logger = logging.getLogger(__name__)

# Optional OpenAI integration — only imported when an API key is present.
_openai_client: Optional[object] = None

if settings.openai_api_key:
    try:
        from openai import OpenAI  # type: ignore[import-untyped]

        _openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialised (model=%s)", settings.llm_model)
    except ImportError:
        logger.warning("openai package not installed — falling back to knowledge-base mode")
    except Exception:
        logger.warning("Failed to initialise OpenAI client — falling back to knowledge-base mode", exc_info=True)


class LLMService:
    """Handles queries for the Autoimmune Intelligence API."""

    def query(self, question: str) -> QueryResponse:
        logger.info("LLMService.query called with question=%r", question)

        # 1. Retrieve relevant KB entries
        results = search(question, top_k=3)

        if not results:
            return QueryResponse(
                answer=(
                    "I could not find a strong match for your query in the "
                    "current knowledge base. Try rephrasing your question or "
                    "asking about a specific autoimmune disease, cytokine "
                    "pathway, or therapeutic target."
                ),
                sources=[],
            )

        # 2. If OpenAI is available, synthesise an answer using KB context
        if _openai_client is not None:
            return self._llm_answer(question, results)

        # 3. Fallback: return the best KB match directly
        return self._kb_answer(question, results)

    # ------------------------------------------------------------------
    # Knowledge-base-only answer (no external API needed)
    # ------------------------------------------------------------------
    @staticmethod
    def _kb_answer(question: str, results: list) -> QueryResponse:
        """Compose an answer from the top KB hits."""
        primary = results[0].entry

        parts = [primary.answer]

        # Append supplementary context from lower-ranked hits
        for r in results[1:]:
            if r.score > 0.1:
                parts.append(
                    f"\n\nRelated — {r.entry.topic}:\n{r.entry.answer}"
                )

        all_sources: list[str] = []
        for r in results:
            all_sources.extend(r.entry.sources)

        return QueryResponse(answer="\n".join(parts), sources=all_sources)

    # ------------------------------------------------------------------
    # LLM-augmented answer (OpenAI)
    # ------------------------------------------------------------------
    @staticmethod
    def _llm_answer(question: str, results: list) -> QueryResponse:
        """Send KB context + question to OpenAI for a synthesised answer."""
        context_blocks = []
        all_sources: list[str] = []
        for r in results:
            context_blocks.append(
                f"### {r.entry.topic}\n{r.entry.answer}\n"
                f"Sources: {'; '.join(r.entry.sources)}"
            )
            all_sources.extend(r.entry.sources)

        context = "\n\n".join(context_blocks)

        try:
            response = _openai_client.chat.completions.create(  # type: ignore[union-attr]
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Autoimmune Intelligence, a research assistant "
                            "that synthesises immunological evidence. Answer the "
                            "user's question using ONLY the provided context. "
                            "Cite sources by author and journal. Be precise and "
                            "evidence-based. If the context is insufficient, say so."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Context:\n{context}\n\n"
                            f"Question: {question}\n\n"
                            "Provide a detailed, structured answer."
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            answer = response.choices[0].message.content or results[0].entry.answer
        except Exception:
            logger.warning("OpenAI call failed — falling back to KB", exc_info=True)
            return LLMService._kb_answer(question, results)

        return QueryResponse(answer=answer, sources=all_sources)
