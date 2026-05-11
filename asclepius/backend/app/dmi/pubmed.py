"""PubMed retrieval for DMI using NCBI E-utilities API."""

from __future__ import annotations

import logging
from typing import Optional

from app.services.pubmed_service import PubMedArticle, PubMedService

logger = logging.getLogger(__name__)

_pubmed = PubMedService()


def fetch_disease_literature(
    disease_name: str,
    max_results: int = 75,
) -> list[PubMedArticle]:
    """Fetch mechanism/pathway/target/trial literature for a disease.

    First tries a specific mechanistic query; falls back to a broad search
    on the disease name alone if no results are returned.
    """
    specific_query = (
        f'("{disease_name}") AND '
        f"(mechanism OR pathway OR target OR therapy OR treatment)"
    )
    articles = _pubmed.search(specific_query, max_results=max_results, sort="relevance")
    logger.info(
        "PubMed: fetched %d articles (specific query) for disease=%r",
        len(articles),
        disease_name,
    )

    if not articles:
        broad_query = f'"{disease_name}"'
        articles = _pubmed.search(broad_query, max_results=max_results, sort="relevance")
        logger.info(
            "PubMed: fetched %d articles (broad fallback) for disease=%r",
            len(articles),
            disease_name,
        )

    return articles


def fetch_target_literature(
    disease_name: str,
    target_name: str,
    max_results: int = 50,
) -> list[PubMedArticle]:
    """Fetch literature specifically about a target in the context of a disease.

    Falls back to a broader query when the specific one returns no results.
    """
    specific_query = (
        f'("{disease_name}") AND ("{target_name}") AND '
        f"(mechanism OR pathway OR therapy OR trial OR failure)"
    )
    articles = _pubmed.search(specific_query, max_results=max_results, sort="relevance")
    logger.info(
        "PubMed: fetched %d articles (specific) for disease=%r target=%r",
        len(articles),
        disease_name,
        target_name,
    )

    if not articles:
        broad_query = f'"{disease_name}" AND "{target_name}"'
        articles = _pubmed.search(broad_query, max_results=max_results, sort="relevance")
        logger.info(
            "PubMed: fetched %d articles (broad fallback) for disease=%r target=%r",
            len(articles),
            disease_name,
            target_name,
        )

    return articles
