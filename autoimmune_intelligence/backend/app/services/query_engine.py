"""Unified retrieval engine for the autoimmune knowledge base + datasets.

Searches across:
1. Curated KB entries (knowledge_base.py)
2. Cytokine signaling network
3. Immune signaling pathways
4. Disease-gene associations
5. Therapeutics / clinical evidence

Returns a single ``SearchResult`` that aggregates relevant hits from every
data source so the LLM service can compose a rich answer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.data.knowledge_base import ENTRIES, KBEntry
from app.data.ingestion import STORE

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into unique tokens (len > 1)."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    return {t for t in text.split() if len(t) > 1}


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class ScoredEntry:
    entry: KBEntry
    score: float


@dataclass
class SearchResult:
    """Aggregated search results from all data sources."""

    kb_hits: list[ScoredEntry] = field(default_factory=list)
    cytokine_hits: list[dict[str, Any]] = field(default_factory=list)
    pathway_hits: list[dict[str, Any]] = field(default_factory=list)
    disease_hits: list[dict[str, Any]] = field(default_factory=list)
    therapeutic_hits: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return bool(
            self.kb_hits
            or self.cytokine_hits
            or self.pathway_hits
            or self.disease_hits
            or self.therapeutic_hits
        )


# ---------------------------------------------------------------------------
# KB search (original)
# ---------------------------------------------------------------------------

def _search_kb(query_tokens: set[str], top_k: int = 3, threshold: float = 0.05) -> list[ScoredEntry]:
    scored: list[ScoredEntry] = []
    for entry in ENTRIES:
        kw_tokens = {k.lower() for k in entry.keywords}
        topic_tokens = _tokenize(entry.topic)
        kw_hits = query_tokens & kw_tokens
        kw_score = len(kw_hits) / len(kw_tokens) if kw_tokens else 0.0
        topic_hits = query_tokens & topic_tokens
        topic_score = len(topic_hits) / len(topic_tokens) if topic_tokens else 0.0
        score = 0.6 * kw_score + 0.4 * topic_score
        if score >= threshold:
            scored.append(ScoredEntry(entry=entry, score=score))
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Cytokine network search
# ---------------------------------------------------------------------------

def _search_cytokines(query_tokens: set[str], top_k: int = 10) -> list[dict[str, Any]]:
    hits: list[tuple[float, dict]] = []
    for edge in STORE.cytokine_edges:
        searchable = {
            edge.source.lower(), edge.target.lower(),
            edge.pathway.lower(), edge.edge_type.lower(),
            edge.source_type.lower(), edge.target_type.lower(),
        }
        searchable |= {d.lower() for d in edge.diseases}
        searchable |= _tokenize(edge.description)
        overlap = query_tokens & searchable
        if overlap:
            score = len(overlap) / max(len(query_tokens), 1)
            hits.append((score, {
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "pathway": edge.pathway,
                "diseases": edge.diseases,
                "confidence": edge.confidence,
                "description": edge.description,
                "pmid": edge.pmid,
            }))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [h[1] for h in hits[:top_k]]


# ---------------------------------------------------------------------------
# Pathway search
# ---------------------------------------------------------------------------

def _search_pathways(query_tokens: set[str], top_k: int = 5) -> list[dict[str, Any]]:
    hits: list[tuple[float, dict]] = []
    for pw in STORE.pathways:
        searchable = _tokenize(pw.pathway_name) | _tokenize(pw.description)
        searchable |= {d.lower() for d in pw.disease_relevance}
        for node in pw.key_nodes:
            searchable.add(node.get("gene", "").lower())
            searchable |= _tokenize(node.get("role", ""))
        for tgt in pw.therapeutic_targets:
            searchable.add(tgt.get("target", "").lower())
            searchable.add(tgt.get("drug", "").lower())
        overlap = query_tokens & searchable
        if overlap:
            score = len(overlap) / max(len(query_tokens), 1)
            hits.append((score, {
                "pathway_id": pw.pathway_id,
                "pathway_name": pw.pathway_name,
                "description": pw.description,
                "disease_relevance": pw.disease_relevance,
                "key_nodes": pw.key_nodes[:8],
                "therapeutic_targets": pw.therapeutic_targets,
                "edges_count": len(pw.edges),
                "references": pw.key_references,
            }))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [h[1] for h in hits[:top_k]]


# ---------------------------------------------------------------------------
# Disease-gene association search
# ---------------------------------------------------------------------------

def _search_diseases(query_tokens: set[str], top_k: int = 5) -> list[dict[str, Any]]:
    hits: list[tuple[float, dict]] = []
    for dis in STORE.diseases:
        searchable = _tokenize(dis.disease_name) | _tokenize(dis.description)
        searchable |= {m.lower() for m in dis.pathogenic_mechanisms}
        searchable |= {c.lower() for c in dis.key_cell_types}
        for g in dis.associated_genes:
            searchable.add(g.get("gene", "").lower())
        for ab in dis.autoantibodies:
            searchable |= _tokenize(ab)
        for hla in dis.hla_associations:
            searchable.add(hla.lower().replace("*", ""))
        overlap = query_tokens & searchable
        if overlap:
            score = len(overlap) / max(len(query_tokens), 1)
            hits.append((score, {
                "disease_name": dis.disease_name,
                "disease_id": dis.disease_id,
                "description": dis.description,
                "prevalence": dis.prevalence,
                "pathogenic_mechanisms": dis.pathogenic_mechanisms,
                "key_cell_types": dis.key_cell_types,
                "associated_genes": dis.associated_genes[:10],
                "hla_associations": dis.hla_associations,
                "autoantibodies": dis.autoantibodies,
                "approved_therapies": dis.approved_therapies,
                "references": dis.key_references,
            }))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [h[1] for h in hits[:top_k]]


# ---------------------------------------------------------------------------
# Therapeutics search
# ---------------------------------------------------------------------------

def _search_therapeutics(query_tokens: set[str], top_k: int = 8) -> list[dict[str, Any]]:
    hits: list[tuple[float, dict]] = []
    for rx in STORE.therapeutics:
        searchable = {
            rx.drug_name.lower(), rx.brand_name.lower(),
            rx.target.lower(), rx.drug_class.lower(),
        }
        searchable |= _tokenize(rx.mechanism)
        for ind in rx.approved_indications:
            searchable |= _tokenize(ind.get("disease", ""))
        overlap = query_tokens & searchable
        if overlap:
            score = len(overlap) / max(len(query_tokens), 1)
            hits.append((score, {
                "drug_name": rx.drug_name,
                "brand_name": rx.brand_name,
                "drug_class": rx.drug_class,
                "target": rx.target,
                "mechanism": rx.mechanism,
                "approved_indications": rx.approved_indications,
                "pivotal_trials": rx.pivotal_trials[:3],
                "safety_signals": rx.safety_signals,
            }))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [h[1] for h in hits[:top_k]]


# ---------------------------------------------------------------------------
# Unified search (public API)
# ---------------------------------------------------------------------------

def search(query: str, top_k: int = 3, threshold: float = 0.05) -> list[ScoredEntry]:
    """Backward-compatible: return KB hits only (used by existing LLM service)."""
    tokens = _tokenize(query)
    if not tokens:
        return []
    return _search_kb(tokens, top_k=top_k, threshold=threshold)


def search_all(query: str) -> SearchResult:
    """Search across ALL data sources and return aggregated results."""
    tokens = _tokenize(query)
    if not tokens:
        return SearchResult()

    return SearchResult(
        kb_hits=_search_kb(tokens, top_k=3),
        cytokine_hits=_search_cytokines(tokens, top_k=10),
        pathway_hits=_search_pathways(tokens, top_k=3),
        disease_hits=_search_diseases(tokens, top_k=3),
        therapeutic_hits=_search_therapeutics(tokens, top_k=5),
    )
