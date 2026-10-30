"""Single shared Anthropic client for the whole application."""
from __future__ import annotations
import inspect
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


_warned_unsupported: set[str] = set()


def sdk_kwargs(method: Any, **kwargs: Any) -> dict[str, Any]:
    """Keep only the keyword arguments the installed Anthropic SDK accepts.

    SDK releases add and remove request parameters (``temperature`` is no longer
    accepted by ``messages.create``), and passing an unknown one raises
    ``TypeError`` before any request is made. Because ``requirements.txt`` does
    not pin the SDK, a redeploy can pick up such a release, so unsupported
    arguments are dropped (with a one-time warning) instead of failing every call.
    """
    try:
        params = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    kept = {k: v for k, v in kwargs.items() if k in params}
    for name in kwargs.keys() - kept.keys():
        if name not in _warned_unsupported:
            _warned_unsupported.add(name)
            logger.warning("Installed Anthropic SDK does not accept %r; omitting it from requests", name)
    return kept
