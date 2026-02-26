"""
Normalize disease and phenotype ontology terms.

Supported ontologies
--------------------
- **HPO** (Human Phenotype Ontology) – ``HP:XXXXXXX``
- **OMIM** – ``OMIM:XXXXXX``
- **MONDO** (Monarch Disease Ontology) – ``MONDO:XXXXXXX``
- **MedGen** – ``MedGen:XXXXXXX``
- **Orphanet** – ``Orphanet:XXXXXX``

Each raw identifier is parsed into an :class:`OntologyTerm` with a canonical
``prefix:accession`` representation.

Typical usage
-------------
>>> from preprocessing.ontology_normalization import normalize_phenotype_ids
>>> terms = normalize_phenotype_ids(["HP:0002355", "OMIM:168600", "MedGen:C0270850"])
>>> for t in terms:
...     print(t.canonical_id, t.prefix)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Supported prefixes
# ---------------------------------------------------------------------------

#: Set of recognised ontology prefixes (upper-case for matching).
SUPPORTED_PREFIXES: frozenset[str] = frozenset({
    "HP",
    "OMIM",
    "MONDO",
    "MEDGEN",
    "ORPHANET",
    "ORPHA",
    "NCBITaxon",
    "EFO",
})

#: Canonical display prefix for aliases.
_PREFIX_ALIAS: dict[str, str] = {
    "ORPHA": "Orphanet",
    "ORPHANET": "Orphanet",
    "MEDGEN": "MedGen",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class OntologyTerm:
    """A normalised ontology term.

    Attributes
    ----------
    raw : str
        Original identifier string as provided.
    prefix : str
        Normalised ontology prefix (e.g. ``"HP"``, ``"OMIM"``).
    accession : str
        Numeric or alphanumeric accession part (e.g. ``"0002355"``).
    canonical_id : str
        ``prefix:accession`` in canonical form (e.g. ``"HP:0002355"``).
    is_supported : bool
        ``True`` if the prefix belongs to a supported ontology.
    """

    raw: str
    prefix: str
    accession: str
    canonical_id: str
    is_supported: bool


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_TERM_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)[:_]([A-Za-z0-9]+)$")


def normalize_ontology_term(raw: str) -> Optional[OntologyTerm]:
    """Parse and normalise a single ontology identifier string.

    Parameters
    ----------
    raw : str
        Raw identifier such as ``"HP:0002355"``, ``"OMIM:168600"``, or
        ``"MedGen:C0270850"``.

    Returns
    -------
    OntologyTerm or None
        ``None`` if the string cannot be parsed as a valid ontology term.

    Examples
    --------
    >>> t = normalize_ontology_term("HP:0002355")
    >>> t.prefix, t.accession, t.canonical_id
    ('HP', '0002355', 'HP:0002355')
    """
    stripped = raw.strip()
    match = _TERM_RE.match(stripped)
    if not match:
        return None

    raw_prefix, accession = match.group(1), match.group(2)
    upper_prefix = raw_prefix.upper()

    # Resolve aliases to canonical display form
    canonical_prefix = _PREFIX_ALIAS.get(upper_prefix, raw_prefix)

    canonical_id = f"{canonical_prefix}:{accession}"
    is_supported = upper_prefix in SUPPORTED_PREFIXES

    return OntologyTerm(
        raw=raw,
        prefix=canonical_prefix,
        accession=accession,
        canonical_id=canonical_id,
        is_supported=is_supported,
    )


def normalize_phenotype_ids(raw_ids: List[str]) -> List[OntologyTerm]:
    """Parse and normalise a list of raw phenotype/ontology identifiers.

    Unrecognised or malformed identifiers are silently skipped.

    Parameters
    ----------
    raw_ids : list of str
        Raw ontology IDs, e.g. from the ``PhenotypeIDS`` column of ClinVar.

    Returns
    -------
    list of OntologyTerm
        Successfully parsed terms only.

    Examples
    --------
    >>> terms = normalize_phenotype_ids(["HP:0002355", "bad-id", "OMIM:168600"])
    >>> [t.canonical_id for t in terms]
    ['HP:0002355', 'OMIM:168600']
    """
    terms: List[OntologyTerm] = []
    for raw in raw_ids:
        term = normalize_ontology_term(raw)
        if term is not None:
            terms.append(term)
    return terms
