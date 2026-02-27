"""
Shared utility functions for the Asclepius neurology platform.

Functions
---------
to_snake_case          : Convert a string to snake_case.
normalise_gene_symbol  : Upper-case and strip a gene symbol.
build_variant_key      : Create a canonical chrom:pos:ref:alt key.
flatten_dict           : Flatten a nested dictionary with dot-separated keys.
chunked                : Yield successive n-sized chunks from an iterable.
"""

from __future__ import annotations

import re
from itertools import islice
from typing import Any, Dict, Generator, Iterable, Iterator, List, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# String normalisation
# ---------------------------------------------------------------------------

def to_snake_case(name: str) -> str:
    """Convert *name* to ``snake_case``.

    Handles CamelCase, PascalCase, spaces, and hyphens.

    Parameters
    ----------
    name : str
        Input string.

    Returns
    -------
    str
        Lower-case snake_case version of *name*.

    Examples
    --------
    >>> to_snake_case("GeneSymbol")
    'gene_symbol'
    >>> to_snake_case("ClinVar ID")
    'clin_var_id'
    """
    name = name.strip()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower()


def normalise_gene_symbol(symbol: str) -> str:
    """Return the canonical upper-case form of a HGNC gene symbol.

    Parameters
    ----------
    symbol : str
        Raw gene symbol (e.g. ``"  lrrk2 "`` or ``"LRRK2"``).

    Returns
    -------
    str
        Stripped, upper-cased symbol (e.g. ``"LRRK2"``).

    Examples
    --------
    >>> normalise_gene_symbol("  lrrk2 ")
    'LRRK2'
    """
    return symbol.strip().upper()


# ---------------------------------------------------------------------------
# Variant utilities
# ---------------------------------------------------------------------------

def build_variant_key(chrom: str, pos: int, ref: str, alt: str) -> str:
    """Build a canonical ``chrom:pos:ref:alt`` variant key.

    Parameters
    ----------
    chrom : str
        Chromosome name (leading ``"chr"`` prefix is stripped).
    pos : int
        1-based genomic position.
    ref : str
        Reference allele (upper-cased).
    alt : str
        Alternate allele (upper-cased).

    Returns
    -------
    str
        Canonical key, e.g. ``"12:40340400:G:A"``.

    Examples
    --------
    >>> build_variant_key("chr12", 40340400, "g", "a")
    '12:40340400:G:A'
    """
    chrom_lower = chrom.strip().lower()
    chrom_clean = chrom.strip()[3:] if chrom_lower.startswith("chr") else chrom.strip()
    return f"{chrom_clean}:{pos}:{ref.upper()}:{alt.upper()}"


# ---------------------------------------------------------------------------
# Dictionary utilities
# ---------------------------------------------------------------------------

def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> Dict[str, Any]:
    """Flatten a nested dictionary into a single-level dict.

    Parameters
    ----------
    d : dict
        Possibly nested dictionary to flatten.
    parent_key : str
        Key prefix for recursive calls.
    sep : str
        Separator between nested key levels (default ``"."``).

    Returns
    -------
    dict

    Examples
    --------
    >>> flatten_dict({"a": {"b": 1, "c": {"d": 2}}})
    {'a.b': 1, 'a.c.d': 2}
    """
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


# ---------------------------------------------------------------------------
# Iteration utilities
# ---------------------------------------------------------------------------

def chunked(iterable: Iterable[T], n: int) -> Generator[List[T], None, None]:
    """Yield successive *n*-sized chunks from *iterable*.

    Parameters
    ----------
    iterable : iterable
        Any iterable to split into chunks.
    n : int
        Maximum chunk size (last chunk may be smaller).

    Yields
    ------
    list
        A list of up to *n* items.

    Examples
    --------
    >>> list(chunked(range(7), 3))
    [[0, 1, 2], [3, 4, 5], [6]]
    """
    it: Iterator[T] = iter(iterable)
    while True:
        chunk = list(islice(it, n))
        if not chunk:
            break
        yield chunk
