# entity_normalizer.py
# Normalize gene, protein, cytokine, and receptor identifiers to HGNC/UniProt.

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

_MYGENE_BASE = "https://mygene.info/v3"
_UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"

# Simple alias table for common immune entities (supplement API lookups)
_ALIAS_TABLE: Dict[str, str] = {
    "TNF-alpha": "TNF",
    "TNFa": "TNF",
    "IFN-gamma": "IFNG",
    "IFNg": "IFNG",
    "IL-6": "IL6",
    "IL6R": "IL6R",
    "IL-2": "IL2",
    "TGF-beta": "TGFB1",
    "TGFb": "TGFB1",
    "NF-kB": "NFKB1",
    "NFkB": "NFKB1",
    "JAK1": "JAK1",
    "JAK2": "JAK2",
    "STAT3": "STAT3",
    "STAT1": "STAT1",
    "PD-1": "PDCD1",
    "PD-L1": "CD274",
    "CTLA-4": "CTLA4",
    "CD28": "CD28",
    "TCR": "TRA",
    "BCR": "IGHM",
}


def normalize_entity(
    entity_name: str,
    species: str = "human",
    use_api: bool = False,
    delay: float = 0.1,
) -> Dict[str, Any]:
    """Normalize an entity name to a standard identifier.

    First checks a local alias table, then optionally queries the MyGene.info
    API for HGNC symbol and Entrez ID resolution.

    Parameters
    ----------
    entity_name:
        Raw entity name to normalize (e.g. ``"TNF-alpha"``).
    species:
        Species scope for API queries (default ``"human"``).
    use_api:
        Whether to query the MyGene.info REST API as a fallback.
    delay:
        Seconds to wait after an API call.

    Returns
    -------
    dict
        Keys: ``"raw"``, ``"symbol"``, ``"hgnc_id"`` (if available),
        ``"entrez_id"`` (if available), ``"uniprot_id"`` (if available).
    """
    # Step 1: check local alias table
    canonical = _ALIAS_TABLE.get(entity_name, entity_name)
    result: Dict[str, Any] = {"raw": entity_name, "symbol": canonical}

    if not use_api:
        return result

    # Step 2: query MyGene.info
    try:
        resp = requests.get(
            f"{_MYGENE_BASE}/query",
            params={
                "q": canonical,
                "species": species,
                "fields": "symbol,entrezgene,HGNC,uniprot",
                "size": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        time.sleep(delay)
        hits = resp.json().get("hits", [])
        if hits:
            hit = hits[0]
            result["symbol"] = hit.get("symbol", canonical)
            if "entrezgene" in hit:
                result["entrez_id"] = str(hit["entrezgene"])
            if "HGNC" in hit:
                result["hgnc_id"] = hit["HGNC"]
            uniprot = hit.get("uniprot", {})
            sp = uniprot.get("Swiss-Prot")
            if sp:
                result["uniprot_id"] = sp if isinstance(sp, str) else sp[0]
    except requests.RequestException:
        pass  # Return best-effort result from alias table

    return result


def normalize_edge_list(
    edge_list: List[Tuple[str, str, str, Dict[str, Any]]],
    use_api: bool = False,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Normalize all entity IDs in an edge list.

    Parameters
    ----------
    edge_list:
        Iterable of ``(source_id, target_id, edge_type, metadata)`` tuples.
    use_api:
        Whether to use the MyGene.info API for lookups.

    Returns
    -------
    list of (source_id, target_id, edge_type, metadata) tuples
        With entity names replaced by their canonical HGNC symbols.
    """
    cache: Dict[str, str] = {}

    def _norm(name: str) -> str:
        if name not in cache:
            result = normalize_entity(name, use_api=use_api)
            cache[name] = result["symbol"]
        return cache[name]

    return [
        (_norm(src), _norm(tgt), etype, meta)
        for src, tgt, etype, meta in edge_list
    ]


def build_alias_table(
    extra_aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Return the current alias table, optionally extended with extra aliases.

    Parameters
    ----------
    extra_aliases:
        Additional ``{alias: canonical}`` mappings to merge in.

    Returns
    -------
    dict
        Combined alias table.
    """
    table = dict(_ALIAS_TABLE)
    if extra_aliases:
        table.update(extra_aliases)
    return table
