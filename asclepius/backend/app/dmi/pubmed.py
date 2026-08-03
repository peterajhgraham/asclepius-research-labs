"""PubMed and preprint retrieval for DMI."""

from __future__ import annotations

import logging
import urllib.request
import json as _json

from app.services.pubmed_service import PubMedArticle, pubmed as _pubmed

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# bioRxiv / medRxiv preprint retrieval
# ---------------------------------------------------------------------------

_BIORXIV_BASE = "https://api.biorxiv.org/details/biorxiv/{interval}"
_MEDRXIV_BASE = "https://api.biorxiv.org/details/medrxiv/{interval}"
_PAGE_SIZE = 100


def _query_preprint_server(base_url: str, query: str, max_results: int) -> list[PubMedArticle]:
    """Return preprints matching *query* via title/abstract filter, with pagination."""
    results: list[PubMedArticle] = []
    q_lower = query.lower()
    words = q_lower.split()

    def _matches(text: str) -> bool:
        t = text.lower()
        return all(w in t for w in words)

    offset = 0
    max_pages = 50  # safety cap — bioRxiv has ~200k entries but we don't need to scan all
    pages_fetched = 0

    while len(results) < max_results:
        if pages_fetched >= max_pages:
            logger.warning("Hit page cap (%d) for preprint query %r — stopping", max_pages, query)
            break
        url = f"{base_url}/{offset}/json"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw = _json.loads(resp.read().decode())
        except Exception:
            break

        collection = raw.get("collection", [])
        if not collection:
            break

        for item in collection:
            try:
                title = str(item.get("title") or "")
                abstract = str(item.get("abstract") or "")
                if not _matches(title) and not _matches(abstract):
                    continue
                doi = str(item.get("doi") or "")
                raw_authors = str(item.get("authors") or "")
                authors = [raw_authors.split(";")[0].strip()] if raw_authors.strip() else []
                date_str = str(item.get("date") or "")
                year = date_str[:4] if len(date_str) >= 4 else ""
                # Use a clearly-prefixed identifier so callers can distinguish
                # preprint DOIs from numeric PubMed PMIDs (important for dedup
                # and for the frontend that builds PubMed URLs from pmid).
                results.append(
                    PubMedArticle(
                        pmid=f"preprint:{doi}" if doi else "",
                        title=title,
                        abstract=abstract,
                        authors=authors,
                        journal=str(item.get("server") or "preprint"),
                        year=year,
                        doi=doi,
                    )
                )
                if len(results) >= max_results:
                    return results
            except Exception:
                logger.debug("Skipping malformed preprint item", exc_info=True)
                continue

        if len(collection) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
        pages_fetched += 1

    return results


def fetch_all_literature(
    disease_name: str,
    max_results: int = 75,
) -> list[PubMedArticle]:
    """Fetch PubMed articles and preprints for a disease, merged and deduplicated.

    Calls :func:`fetch_disease_literature` for indexed PubMed articles and
    :func:`fetch_preprints` for bioRxiv/medRxiv, then merges the two lists,
    dropping duplicates by DOI.  The combined list is capped at *max_results*.
    """
    pubmed_articles = fetch_disease_literature(disease_name, max_results=max_results)
    preprints = fetch_preprints(disease_name, max_results=10)

    seen_dois: set[str] = {a.doi for a in pubmed_articles if a.doi}
    merged: list[PubMedArticle] = list(pubmed_articles)
    for p in preprints:
        doi_key = p.doi
        if doi_key and doi_key in seen_dois:
            continue
        if doi_key:
            seen_dois.add(doi_key)
        merged.append(p)

    logger.info(
        "fetch_all_literature: %d PubMed + %d preprints → %d merged for disease=%r",
        len(pubmed_articles),
        len(preprints),
        len(merged),
        disease_name,
    )
    return merged[:max_results]


def fetch_preprints(query: str, max_results: int = 10) -> list[PubMedArticle]:
    """Fetch recent preprints from bioRxiv and medRxiv matching *query*.

    Uses the public bioRxiv Details API with a wide date window, paginating
    through results in chunks of 100 until max_results is satisfied.
    Articles are tagged with source server in the ``journal`` field.
    """
    interval = "2024-01-01/2099-01-01"
    articles: list[PubMedArticle] = []
    # Deduplicate across servers by DOI so the same paper indexed on both
    # bioRxiv and medRxiv is only included once.
    seen_dois: set[str] = set()
    for base_template in (_BIORXIV_BASE, _MEDRXIV_BASE):
        base_url = base_template.format(interval=interval)
        for article in _query_preprint_server(base_url, query, max_results):
            doi_key = article.doi or article.pmid
            if doi_key and doi_key in seen_dois:
                continue
            if doi_key:
                seen_dois.add(doi_key)
            articles.append(article)
            if len(articles) >= max_results:
                break
        if len(articles) >= max_results:
            break
    logger.info("Preprints: fetched %d results for query=%r", len(articles), query)
    return articles[:max_results]
