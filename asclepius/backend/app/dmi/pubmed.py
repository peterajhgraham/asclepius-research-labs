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

    Query: "{disease_name} AND (mechanism OR pathway OR target OR trial)"
    """
    query = (
        f'("{disease_name}") AND '
        f"(mechanism OR pathway OR target OR clinical trial)"
    )
    articles = _pubmed.search(query, max_results=max_results, sort="relevance")
    logger.info(
        "PubMed: fetched %d articles for disease=%r", len(articles), disease_name
    )
    return articles


def fetch_target_literature(
    disease_name: str,
    target_name: str,
    max_results: int = 50,
) -> list[PubMedArticle]:
    """Fetch literature specifically about a target in the context of a disease."""
    query = (
        f'("{disease_name}") AND ("{target_name}") AND '
        f"(mechanism OR pathway OR target OR trial OR failure)"
    )
    articles = _pubmed.search(query, max_results=max_results, sort="relevance")
    logger.info(
        "PubMed: fetched %d articles for disease=%r target=%r",
        len(articles),
        disease_name,
        target_name,
    )
    return articles
