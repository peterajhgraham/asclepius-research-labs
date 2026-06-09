"""Live PubMed search service using NCBI E-utilities.

Queries PubMed in real-time to supplement the curated knowledge base with
the latest literature.  Results are parsed, ranked, and returned as
structured citation objects for integration into the query pipeline.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

_NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Immune-relevant interaction verbs for relationship extraction
_INTERACTION_PATTERN = re.compile(
    r"(\b[A-Z][A-Za-z0-9\-]{1,20}\b)"
    r"\s+"
    r"(activates?|inhibits?|binds?|upregulates?|downregulates?|promotes?|suppresses?|phosphorylates?|modulates?|induces?|blocks?|attenuates?)"
    r"\s+"
    r"(\b[A-Z][A-Za-z0-9\-]{1,20}\b)",
    re.IGNORECASE,
)

_VERB_TO_EDGE = {
    "activates": "activates", "activate": "activates",
    "upregulates": "activates", "upregulate": "activates",
    "promotes": "activates", "promote": "activates",
    "induces": "activates", "induce": "activates",
    "phosphorylates": "activates", "phosphorylate": "activates",
    "inhibits": "inhibits", "inhibit": "inhibits",
    "downregulates": "inhibits", "downregulate": "inhibits",
    "suppresses": "inhibits", "suppress": "inhibits",
    "blocks": "inhibits", "block": "inhibits",
    "attenuates": "inhibits", "attenuate": "inhibits",
    "binds": "binds", "bind": "binds",
    "modulates": "activates", "modulate": "activates",
}


class PubMedArticle:
    """Parsed PubMed article with structured fields."""

    __slots__ = (
        "pmid", "title", "abstract", "authors", "journal",
        "year", "doi", "mesh_terms", "keywords",
    )

    def __init__(
        self,
        pmid: str,
        title: str = "",
        abstract: str = "",
        authors: Optional[List[str]] = None,
        journal: str = "",
        year: str = "",
        doi: str = "",
        mesh_terms: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
    ) -> None:
        self.pmid = pmid
        self.title = title
        self.abstract = abstract
        self.authors = authors or []
        self.journal = journal
        self.year = year
        self.doi = doi
        self.mesh_terms = mesh_terms or []
        self.keywords = keywords or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pmid": self.pmid,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "doi": self.doi,
            "mesh_terms": self.mesh_terms,
            "keywords": self.keywords,
        }

    @property
    def citation(self) -> str:
        """APA-style short citation."""
        first_author = self.authors[0] if self.authors else "Unknown"
        et_al = " et al." if len(self.authors) > 1 else ""
        return f"{first_author}{et_al} ({self.year}). {self.title}. {self.journal}. PMID:{self.pmid}"


class PubMedService:
    """Service for live PubMed queries and article parsing."""

    def __init__(
        self,
        email: str = "asclepius@research.dev",
        rate_limit_delay: float = 0.35,
        max_retries: int = 3,
    ) -> None:
        self.email = email
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        # Records the last transport/parse failure so callers can tell a genuine
        # "0 results" apart from "couldn't reach NCBI". Reset at the start of
        # every search(); None means the last search completed cleanly.
        self.last_error: Optional[str] = None
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "AsclepiusResearchLabs/1.0",
        })

    def search(
        self,
        query: str,
        max_results: int = 15,
        sort: str = "relevance",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> List[PubMedArticle]:
        """Search PubMed and return parsed article objects.

        Parameters
        ----------
        query : str
            PubMed search query (supports full PubMed syntax).
        max_results : int
            Maximum articles to retrieve.
        sort : str
            Sort order: "relevance" or "date".
        min_date / max_date : str, optional
            Date range filters (YYYY/MM/DD format).

        On a transport failure (NCBI unreachable, timeout, HTTP error) this
        returns ``[]`` *and* sets :attr:`last_error`; callers that need to
        distinguish an infrastructure failure from a genuinely empty result set
        should check ``last_error`` after calling.
        """
        self.last_error = None
        pmids = self._search_ids(query, max_results, sort, min_date, max_date)
        if not pmids:
            return []
        return self._fetch_articles(pmids)

    def search_autoimmune(
        self,
        topic: str,
        max_results: int = 10,
    ) -> List[PubMedArticle]:
        """Search with autoimmune-specific query enrichment.

        Automatically appends immune/autoimmune MeSH terms to improve
        relevance for our domain.
        """
        enriched = (
            f"({topic}) AND (autoimmune[MeSH] OR immune[MeSH] OR "
            f"immunology[MeSH] OR cytokine OR signaling pathway)"
        )
        return self.search(enriched, max_results=max_results)

    def extract_interactions(
        self,
        articles: List[PubMedArticle],
    ) -> List[Dict[str, Any]]:
        """Extract molecular interactions from article abstracts.

        Returns structured interaction records suitable for knowledge
        graph ingestion.
        """
        interactions: List[Dict[str, Any]] = []
        for article in articles:
            if not article.abstract:
                continue
            for match in _INTERACTION_PATTERN.finditer(article.abstract):
                source = match.group(1)
                verb = match.group(2).lower()
                target = match.group(3)
                edge_type = _VERB_TO_EDGE.get(verb, "activates")
                interactions.append({
                    "source": source,
                    "target": target,
                    "edge_type": edge_type,
                    "pmid": article.pmid,
                    "context": article.abstract[
                        max(0, match.start() - 80): match.end() + 80
                    ],
                    "confidence": 0.6,
                    "article_title": article.title,
                    "year": article.year,
                })
        return interactions

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _search_ids(
        self,
        query: str,
        max_results: int,
        sort: str,
        min_date: Optional[str],
        max_date: Optional[str],
    ) -> List[str]:
        """Call esearch to get a list of PMIDs."""
        params: Dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": sort,
            "email": self.email,
        }
        if min_date:
            params["mindate"] = min_date
            params["datetype"] = "pdat"
        if max_date:
            params["maxdate"] = max_date
            if "datetype" not in params:
                params["datetype"] = "pdat"

        try:
            resp = self._get(f"{_NCBI_BASE}/esearch.fcgi", params)
            data = resp.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except Exception as exc:
            logger.warning("PubMed search failed for query=%r", query, exc_info=True)
            self.last_error = f"PubMed request failed: {exc}"
            return []

    def _fetch_articles(self, pmids: List[str]) -> List[PubMedArticle]:
        """Fetch full article metadata via efetch (batch mode)."""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "email": self.email,
        }
        try:
            resp = self._get(f"{_NCBI_BASE}/efetch.fcgi", params)
            return self._parse_xml(resp.content)
        except Exception:
            logger.warning("PubMed fetch failed for %d PMIDs", len(pmids), exc_info=True)
            return []

    def _parse_xml(self, xml_content: bytes) -> List[PubMedArticle]:
        """Parse PubMed XML response into PubMedArticle objects."""
        articles: List[PubMedArticle] = []
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            logger.warning("Failed to parse PubMed XML response")
            return []

        for article_elem in root.findall(".//PubmedArticle"):
            try:
                articles.append(self._parse_article(article_elem))
            except Exception:
                logger.debug("Skipping malformed article element", exc_info=True)
        return articles

    @staticmethod
    def _parse_article(elem: ET.Element) -> PubMedArticle:
        """Parse a single PubmedArticle XML element."""
        # PMID
        pmid_elem = elem.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        # Title
        title_elem = elem.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else ""

        # Abstract - handle multiple AbstractText elements
        abstract_parts: List[str] = []
        for abs_elem in elem.findall(".//AbstractText"):
            label = abs_elem.get("Label", "")
            text = abs_elem.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts)

        # Authors
        authors: List[str] = []
        for author_elem in elem.findall(".//Author"):
            last = author_elem.findtext("LastName", "")
            initials = author_elem.findtext("Initials", "")
            if last:
                authors.append(f"{last} {initials}".strip())

        # Journal
        journal = elem.findtext(".//Journal/Title", "")

        # Year
        year = (
            elem.findtext(".//PubDate/Year", "")
            or elem.findtext(".//PubDate/MedlineDate", "")[:4]
            if elem.find(".//PubDate/MedlineDate") is not None
            else elem.findtext(".//PubDate/Year", "")
        )

        # DOI
        doi = ""
        for id_elem in elem.findall(".//ArticleId"):
            if id_elem.get("IdType") == "doi":
                doi = id_elem.text or ""
                break

        # MeSH terms
        mesh_terms = [
            desc.text
            for desc in elem.findall(".//MeshHeading/DescriptorName")
            if desc.text
        ]

        # Keywords
        keywords = [
            kw.text
            for kw in elem.findall(".//Keyword")
            if kw.text
        ]

        return PubMedArticle(
            pmid=pmid,
            title=title,
            abstract=abstract,
            authors=authors,
            journal=journal,
            year=year,
            doi=doi,
            mesh_terms=mesh_terms,
            keywords=keywords,
        )

    def _get(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """HTTP GET with retry and rate limiting."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.rate_limit_delay)
                resp = self._session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.debug("Retry %d/%d after %ds: %s", attempt + 1, self.max_retries, wait, exc)
                time.sleep(wait)
        raise requests.HTTPError(
            f"All {self.max_retries} attempts failed for {url}"
        ) from last_exc


# Singleton instance
pubmed = PubMedService()
