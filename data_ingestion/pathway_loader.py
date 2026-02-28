# pathway_loader.py
# Load KEGG and Reactome immune pathway interaction data.

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

_KEGG_BASE = "https://rest.kegg.jp"
_REACTOME_BASE = "https://reactome.org/ContentService"


# ---------------------------------------------------------------------------
# KEGG helpers
# ---------------------------------------------------------------------------

def load_kegg_pathway(
    pathway_id: str,
    delay: float = 0.2,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Load gene–gene relationships from a KEGG pathway.

    Parameters
    ----------
    pathway_id:
        KEGG pathway identifier, e.g. ``"hsa04660"`` (T cell receptor
        signalling) or ``"hsa04630"`` (JAK-STAT).
    delay:
        Seconds to wait between KEGG API calls to stay within rate limits.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
        Ready for :meth:`graph.graph_builder.ImmuneGraphBuilder.load_edge_list`.
    """
    kgml_url = f"{_KEGG_BASE}/get/{pathway_id}/kgml"
    resp = requests.get(kgml_url, timeout=30)
    resp.raise_for_status()
    time.sleep(delay)

    return _parse_kgml(resp.text, pathway_id)


def _parse_kgml(kgml_text: str, pathway_id: str) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Parse KGML XML into edge tuples.

    Parameters
    ----------
    kgml_text:
        Raw KGML XML string.
    pathway_id:
        Pathway identifier used as provenance metadata.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("beautifulsoup4 is required for KGML parsing.")

    soup = BeautifulSoup(kgml_text, "xml")
    edges: List[Tuple[str, str, str, Dict[str, Any]]] = []

    # Build entry id → gene name map
    entry_map: Dict[str, str] = {}
    for entry in soup.find_all("entry"):
        entry_id = entry.get("id", "")
        entry_name = entry.get("name", "").replace("hsa:", "")
        entry_map[entry_id] = entry_name

    for relation in soup.find_all("relation"):
        entry1 = relation.get("entry1", "")
        entry2 = relation.get("entry2", "")
        rel_type = relation.get("type", "")

        source = entry_map.get(entry1, entry1)
        target = entry_map.get(entry2, entry2)

        subtypes = relation.find_all("subtype")
        subtype_names = [s.get("name", "") for s in subtypes]

        edge_type = _kegg_relation_to_edge(rel_type, subtype_names)
        metadata: Dict[str, Any] = {
            "source_publication": f"KEGG:{pathway_id}",
            "confidence_score": 0.8,
        }
        edges.append((source, target, edge_type, metadata))

    return edges


def _kegg_relation_to_edge(rel_type: str, subtypes: List[str]) -> str:
    """Map a KEGG relation type to a canonical edge type.

    Parameters
    ----------
    rel_type:
        KEGG relation ``type`` attribute (e.g. ``"PPrel"``).
    subtypes:
        List of subtype ``name`` attribute values from the relation element.

    Returns
    -------
    str
        Canonical edge type string.
    """
    for st in subtypes:
        if st in ("activation", "expression", "indirect effect"):
            return "activates"
        if st in ("inhibition", "repression"):
            return "inhibits"
        if st in ("binding/association",):
            return "binds"
    return "activates"


# ---------------------------------------------------------------------------
# Reactome helpers
# ---------------------------------------------------------------------------

def load_reactome_pathway(
    pathway_id: str,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Load interactions for a Reactome pathway.

    Parameters
    ----------
    pathway_id:
        Reactome stable identifier, e.g. ``"R-HSA-168256"``
        (immune system) or ``"R-HSA-9006934"`` (signaling by receptor
        tyrosine kinases).

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
    """
    url = f"{_REACTOME_BASE}/data/pathway/{pathway_id}/containedEvents"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    events = resp.json()
    edges: List[Tuple[str, str, str, Dict[str, Any]]] = []

    for event in events:
        inputs = event.get("input", [])
        outputs = event.get("output", [])
        event_st_id = event.get("stId", "")

        for inp in inputs:
            for out in outputs:
                src = inp.get("identifier") or inp.get("stId", "")
                tgt = out.get("identifier") or out.get("stId", "")
                if src and tgt:
                    metadata: Dict[str, Any] = {
                        "source_publication": f"Reactome:{event_st_id}",
                        "confidence_score": 0.85,
                    }
                    edges.append((src, tgt, "activates", metadata))

    return edges


def list_immune_kegg_pathways() -> Dict[str, str]:
    """Return a curated map of immune-relevant KEGG pathway IDs to descriptions.

    Returns
    -------
    dict
        Mapping from KEGG pathway ID to human-readable description.
    """
    return {
        "hsa04060": "Cytokine-cytokine receptor interaction",
        "hsa04064": "NF-kappa B signaling pathway",
        "hsa04620": "Toll-like receptor signaling pathway",
        "hsa04621": "NOD-like receptor signaling pathway",
        "hsa04630": "JAK-STAT signaling pathway",
        "hsa04660": "T cell receptor signaling pathway",
        "hsa04662": "B cell receptor signaling pathway",
        "hsa04664": "Fc epsilon RI signaling pathway",
        "hsa04940": "Type I diabetes mellitus",
        "hsa05322": "Systemic lupus erythematosus",
    }
