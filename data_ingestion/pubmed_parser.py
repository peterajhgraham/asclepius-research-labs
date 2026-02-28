# pubmed_parser.py
# Extract immune gene/protein/cytokine/receptor interactions from PubMed abstracts.

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

_NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Common immune-relevant interaction verbs
_INTERACTION_PATTERN = re.compile(
    r"(\b[A-Z][A-Za-z0-9\-]+\b)"  # source entity (starts uppercase)
    r"\s+"
    r"(activates|inhibits|binds|upregulates|downregulates|promotes|suppresses)"
    r"\s+"
    r"(\b[A-Z][A-Za-z0-9\-]+\b)",  # target entity (starts uppercase)
    re.IGNORECASE,
)

# Map verbose verbs to canonical EDGE_TYPES
_VERB_TO_EDGE = {
    "activates": "activates",
    "upregulates": "activates",
    "promotes": "activates",
    "inhibits": "inhibits",
    "downregulates": "inhibits",
    "suppresses": "inhibits",
    "binds": "binds",
}


def search_pubmed(
    query: str,
    max_results: int = 100,
    email: Optional[str] = None,
    retries: int = 3,
    delay: float = 0.4,
) -> List[Dict[str, Any]]:
    """Search PubMed and return a list of abstract records.

    Uses the NCBI E-utilities API.  Rate-limited to ≤3 requests/second by
    default to comply with NCBI usage guidelines.

    Parameters
    ----------
    query:
        PubMed search string, e.g. ``"NF-kB signaling autoimmune"``.
    max_results:
        Maximum number of abstracts to retrieve.
    email:
        E-mail address to pass to NCBI (required for production use).
    retries:
        Number of times to retry a failed HTTP request.
    delay:
        Seconds to wait between successive fetch calls.

    Returns
    -------
    list of dict
        Each dict has keys ``"pmid"``, ``"title"``, and ``"abstract"``.
    """
    search_params: Dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }
    if email:
        search_params["email"] = email

    resp = _get_with_retry(f"{_NCBI_BASE}/esearch.fcgi", search_params, retries)
    ids: List[str] = resp.json()["esearchresult"]["idlist"]

    records: List[Dict[str, Any]] = []
    for pmid in ids:
        fetch_params: Dict[str, Any] = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
        }
        if email:
            fetch_params["email"] = email

        fetch_resp = _get_with_retry(f"{_NCBI_BASE}/efetch.fcgi", fetch_params, retries)
        soup = BeautifulSoup(fetch_resp.content, "xml")

        title_tag = soup.find("ArticleTitle")
        abstract_tag = soup.find("AbstractText")

        record: Dict[str, Any] = {
            "pmid": pmid,
            "title": title_tag.text if title_tag else "",
            "abstract": abstract_tag.text if abstract_tag else "",
        }
        records.append(record)
        time.sleep(delay)

    return records


def extract_interactions(
    abstracts: List[str],
    source_pmid: Optional[str] = None,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Extract pairwise interactions from a list of abstract texts.

    Uses a regex heuristic to identify ``(source, verb, target)`` triples.
    This can be replaced with a full NLP pipeline (e.g. spaCy + BioBERT).

    Parameters
    ----------
    abstracts:
        List of abstract text strings.
    source_pmid:
        Optional PubMed ID to attach as provenance metadata.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
        Compatible with :meth:`graph.graph_builder.ImmuneGraphBuilder.load_edge_list`.
    """
    interactions: List[Tuple[str, str, str, Dict[str, Any]]] = []

    for text in abstracts:
        for match in _INTERACTION_PATTERN.finditer(text):
            source, verb, target = match.group(1), match.group(2).lower(), match.group(3)
            edge_type = _VERB_TO_EDGE.get(verb, "activates")
            metadata: Dict[str, Any] = {"confidence_score": 0.5}
            if source_pmid:
                metadata["source_publication"] = source_pmid
            interactions.append((source, target, edge_type, metadata))

    return interactions


def parse_records_to_interactions(
    records: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Convenience wrapper: extract interactions from full PubMed record dicts.

    Parameters
    ----------
    records:
        Output from :func:`search_pubmed`.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
    """
    all_interactions: List[Tuple[str, str, str, Dict[str, Any]]] = []
    for record in records:
        pmid = record.get("pmid")
        abstract = record.get("abstract", "")
        if abstract:
            interactions = extract_interactions([abstract], source_pmid=pmid)
            all_interactions.extend(interactions)
    return all_interactions


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _get_with_retry(
    url: str,
    params: Dict[str, Any],
    retries: int,
) -> requests.Response:
    """HTTP GET with simple retry logic.

    Parameters
    ----------
    url:
        Target URL.
    params:
        Query parameters.
    retries:
        Number of attempts before raising.

    Returns
    -------
    requests.Response

    Raises
    ------
    requests.HTTPError
        If all retry attempts fail.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2 ** attempt)
    raise requests.HTTPError(f"All {retries} attempts failed for {url}") from last_exc
