"""Retrieval service singleton — indexes KB + datasets and exposes retrieve().

Initialization is lazy: the pipeline builds on the first retrieve() call.
Heavy ML models (sentence-transformers, FAISS) load in the background so
startup latency is not affected.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from app.retrieval.pipeline import RetrievalPipeline, RetrievedProposition

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_pipeline: RetrievalPipeline | None = None
_build_lock = threading.Lock()
_build_started = False


def get_pipeline() -> RetrievalPipeline:
    """Return the shared pipeline, building it on first call (thread-safe)."""
    global _pipeline, _build_started
    if _pipeline is not None and _pipeline.is_ready:
        return _pipeline
    with _build_lock:
        if _pipeline is not None and _pipeline.is_ready:
            return _pipeline
        if not _build_started:
            _build_started = True
            _pipeline = _build_pipeline()
    return _pipeline or RetrievalPipeline()


def _build_pipeline() -> RetrievalPipeline:
    pipeline = RetrievalPipeline()
    _index_knowledge_base(pipeline)
    _index_datasets(pipeline)
    pipeline.build()
    logger.info(
        "Retrieval pipeline ready: %d documents indexed",
        pipeline.doc_count,
    )
    return pipeline


# ------------------------------------------------------------------
# Indexing helpers
# ------------------------------------------------------------------

def _index_knowledge_base(pipeline: RetrievalPipeline) -> None:
    try:
        from app.data.knowledge_base import ENTRIES

        for entry in ENTRIES:
            text = f"{entry.topic}: {entry.answer}"
            pipeline.add_document(text, {
                "type": "kb_entry",
                "topic": entry.topic,
                "sources": entry.sources,
                "keywords": entry.keywords,
            })
        logger.info("Retrieval: indexed %d KB entries", len(ENTRIES))
    except Exception:
        logger.warning("Failed to index KB entries", exc_info=True)


def _index_datasets(pipeline: RetrievalPipeline) -> None:
    try:
        from app.data.ingestion import STORE

        # Cytokine network edges
        n = 0
        for edge in STORE.cytokine_edges:
            text = (
                f"{edge.source} {edge.edge_type} {edge.target} "
                f"via {edge.pathway}. {edge.description}"
            )
            pipeline.add_document(text, {
                "type": "cytokine_edge",
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "pathway": edge.pathway,
                "pmid": edge.pmid,
                "diseases": edge.diseases,
                "confidence": edge.confidence,
            })
            n += 1
        logger.info("Retrieval: indexed %d cytokine edges", n)

        # Immune pathways
        n = 0
        for pw in STORE.pathways:
            # Index pathway description
            pipeline.add_document(
                f"{pw.pathway_name}: {pw.description}",
                {
                    "type": "pathway",
                    "pathway_id": pw.pathway_id,
                    "pathway_name": pw.pathway_name,
                    "disease_relevance": pw.disease_relevance,
                    "references": pw.key_references,
                },
            )
            # Index individual key nodes for finer-grained retrieval
            for node in pw.key_nodes[:10]:
                gene = node.get("gene", "")
                role = node.get("role", "")
                if gene and role:
                    pipeline.add_document(
                        f"{gene} in {pw.pathway_name}: {role}",
                        {
                            "type": "pathway_node",
                            "gene": gene,
                            "pathway_name": pw.pathway_name,
                            "pathway_id": pw.pathway_id,
                        },
                    )
            n += 1
        logger.info("Retrieval: indexed %d pathways", n)

        # Disease-gene associations
        n = 0
        for dis in STORE.diseases:
            text = (
                f"{dis.disease_name}: {dis.description} "
                f"Key mechanisms: {', '.join(dis.pathogenic_mechanisms[:5])}. "
                f"Key immune cells: {', '.join(dis.key_cell_types[:6])}. "
                f"HLA associations: {', '.join(dis.hla_associations[:4])}."
            )
            pipeline.add_document(text, {
                "type": "disease",
                "disease_id": dis.disease_id,
                "disease_name": dis.disease_name,
                "prevalence": dis.prevalence,
                "references": dis.key_references,
            })
            # Index each gene entry separately for precision
            for gene_rec in dis.associated_genes[:15]:
                gene = gene_rec.get("gene", "")
                desc = gene_rec.get("description", "")
                if gene and desc:
                    pipeline.add_document(
                        f"{gene} is associated with {dis.disease_name}: {desc}",
                        {
                            "type": "disease_gene",
                            "gene": gene,
                            "disease_name": dis.disease_name,
                            "score": gene_rec.get("score", 0.0),
                        },
                    )
            n += 1
        logger.info("Retrieval: indexed %d disease entries", n)

        # Therapeutics
        n = 0
        for rx in STORE.therapeutics:
            indications = [i.get("disease", "") for i in rx.approved_indications[:6]]
            text = (
                f"{rx.drug_name} ({rx.brand_name}) is a {rx.drug_class} "
                f"targeting {rx.target}. {rx.mechanism} "
                f"Approved indications: {', '.join(indications)}."
            )
            pipeline.add_document(text, {
                "type": "therapeutic",
                "drug_name": rx.drug_name,
                "brand_name": rx.brand_name,
                "target": rx.target,
                "drug_class": rx.drug_class,
                "mechanism": rx.mechanism,
            })
            n += 1
        logger.info("Retrieval: indexed %d therapeutics", n)

    except Exception:
        logger.warning("Failed to index datasets into retrieval pipeline", exc_info=True)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def retrieve(query: str, top_k: int = 8) -> list[RetrievedProposition]:
    """Retrieve top-k propositions for a query using the hybrid pipeline."""
    pipeline = get_pipeline()
    if not pipeline.is_ready:
        return []
    results = pipeline.retrieve(query, top_k=top_k)
    logger.debug("Retrieved %d propositions for query: %s", len(results), query[:60])
    return results


def warm_up() -> None:
    """Trigger pipeline initialization in a background thread (call at startup)."""
    t = threading.Thread(target=get_pipeline, daemon=True, name="retrieval-warmup")
    t.start()
    logger.info("Retrieval pipeline warm-up started in background")
