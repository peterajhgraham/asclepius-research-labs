import logging

logger = logging.getLogger("queries")


def log_query(question: str) -> None:
    """Log each user query for analytics and auditing."""
    logger.info("User Query: %s", question)
