"""Single shared Anthropic client for the whole application."""
from __future__ import annotations
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

_client: Optional[Any] = None

def get_client() -> Optional[Any]:
    """Return the shared Anthropic client, initializing it on first call.

    Returns None if ANTHROPIC_API_KEY is not set.
    """
    global _client
    if _client is None:
        from app.core.config import settings
        if not settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set — LLM features unavailable")
            return None
        try:
            import anthropic
            _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            logger.info("Anthropic client initialized")
        except ImportError:
            logger.error("anthropic package not installed")
    return _client
