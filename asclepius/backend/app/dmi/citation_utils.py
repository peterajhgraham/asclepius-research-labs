"""Citation utilities for DMI reports."""

from __future__ import annotations

import re


def deduplicate_pmids(pmids: list[str]) -> list[str]:
    """Return unique PMIDs preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for pmid in pmids:
        clean = pmid.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def extract_pmids_from_text(text: str) -> list[str]:
    """Extract PMID numbers from free text (e.g. 'PMID:12345')."""
    matches = re.findall(r"PMID[:\s]*(\d{1,9})", text, re.IGNORECASE)
    return deduplicate_pmids(matches)


def format_pmid_link(pmid: str) -> str:
    """Return a PubMed URL for a given PMID."""
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
