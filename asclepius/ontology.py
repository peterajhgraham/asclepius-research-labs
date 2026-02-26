"""
Ontology normalisation layer.

v0: simple lookup-table backed by the ``ontology_terms`` database table.

Future work:
  - Integrate Cell Ontology / OBO Foundry term sets
  - Fuzzy string matching
  - Embedding-based similarity search
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from asclepius.db_models import OntologyTerm


def normalize_term(
    session: Session,
    raw_term: str,
    namespace: Optional[str] = None,
) -> str:
    """
    Return the canonical ontology term for *raw_term*.

    Performs a case-insensitive lookup against the ``ontology_terms`` table.
    If no match is found the raw term is returned unchanged (pass-through).

    Parameters
    ----------
    session : sqlalchemy.orm.Session
    raw_term : str
        The term as it appears in raw metadata (e.g. ``"T cell"``).
    namespace : str, optional
        Restrict the lookup to a specific namespace (e.g. ``"cell_type"``).

    Returns
    -------
    str
        Canonical term (e.g. ``"CL:0000084"``) or *raw_term* if not found.
    """
    q = session.query(OntologyTerm).filter(
        OntologyTerm.raw_term.ilike(raw_term)
    )
    if namespace is not None:
        q = q.filter(OntologyTerm.namespace == namespace)
    term = q.first()
    return term.normalized_term if term else raw_term


def add_term(
    session: Session,
    raw_term: str,
    normalized_term: str,
    namespace: Optional[str] = None,
    commit: bool = True,
) -> OntologyTerm:
    """
    Insert or update an ontology mapping.

    Parameters
    ----------
    session : Session
    raw_term : str
    normalized_term : str
    namespace : str, optional
    commit : bool
        If ``True`` (default) the session is committed immediately.

    Returns
    -------
    OntologyTerm
    """
    existing = (
        session.query(OntologyTerm)
        .filter(OntologyTerm.raw_term == raw_term)
        .filter(OntologyTerm.namespace == namespace)
        .first()
    )
    if existing:
        existing.normalized_term = normalized_term
        entry = existing
    else:
        entry = OntologyTerm(
            raw_term=raw_term,
            normalized_term=normalized_term,
            namespace=namespace,
        )
        session.add(entry)
    if commit:
        session.commit()
    return entry
