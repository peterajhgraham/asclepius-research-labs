"""Retrieval service singleton — indexes propositions and exposes retrieve().

Initialization is lazy: the pipeline builds on the first retrieve() call.
Heavy ML models (sentence-transformers, FAISS) load in the background so
startup latency is not affected.

Indexing priority:
  1. SQLite database (propositions table) — used if populated
  2. Bundled KB + JSON datasets — fallback when DB is empty or unavailable
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path

from app.retrieval.pipeline import RetrievalPipeline, RetrievedProposition

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

    db_count = _index_from_db(pipeline)
    if db_count:
        logger.info("Retrieval: loaded %d documents from SQLite", db_count)
    else:
        logger.info("Retrieval: DB empty or unavailable — indexing bundled datasets")
        _index_knowledge_base(pipeline)
        _index_json_datasets(pipeline)

    pipeline.build()
    logger.info("Retrieval pipeline ready: %d documents indexed", pipeline.doc_count)
    return pipeline


# ------------------------------------------------------------------
# Indexing helpers
# ------------------------------------------------------------------

def _index_from_db(pipeline: RetrievalPipeline) -> int:
    """Load propositions (text + image + table) from SQLite into the pipeline.

    Each row is replayed with its `content_type`, `image_hash` and the
    persisted CLIP embedding (if any). We do *not* recompute embeddings on
    load — that would balloon startup time for large corpora — but we will
    re-embed on next ingest if a row is missing one.
    """
    try:
        import numpy as np
        from app.core.config import settings
        from app.storage.image_store import get_image_store

        url = settings.database_url
        if "sqlite" not in url:
            return 0

        db_path = url.split("///", 1)[-1]
        if not Path(db_path).exists():
            return 0

        conn = sqlite3.connect(db_path)
        try:
            # Defensive column probing — older DBs may not have multimodal columns
            cols = [row[1] for row in conn.execute("PRAGMA table_info(propositions)").fetchall()]
            has_mm = {"content_type", "image_hash", "clip_embedding"}.issubset(cols)
            if has_mm:
                cursor = conn.execute(
                    "SELECT text, metadata_json, content_type, image_hash, clip_embedding "
                    "FROM propositions"
                )
            else:
                cursor = conn.execute("SELECT text, metadata_json FROM propositions")
            rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return 0

        image_store = get_image_store()
        for row in rows:
            if has_mm:
                text, meta_json, content_type, image_hash, clip_blob = row
                content_type = content_type or "text"
            else:
                text, meta_json = row
                content_type, image_hash, clip_blob = "text", None, None

            meta: dict = json.loads(meta_json) if meta_json else {}
            meta["domain"] = meta.get("domain") or "general"

            clip_emb = None
            image_bytes = None
            if content_type in ("image", "table") and clip_blob:
                try:
                    clip_emb = np.frombuffer(clip_blob, dtype=np.float32).copy()
                except Exception:
                    clip_emb = None
            # Only load image bytes if we don't have a cached embedding —
            # otherwise the CLIP index just uses the precomputed vector.
            if content_type == "image" and clip_emb is None and image_hash:
                loaded = image_store.read(image_hash)
                if loaded is not None:
                    image_bytes = loaded[0]

            pipeline.add_document(
                text=text,
                metadata=meta,
                content_type=content_type,
                image_hash=image_hash,
                image_bytes=image_bytes,
                clip_embedding=clip_emb,
            )
        return len(rows)
    except Exception:
        logger.warning("DB load failed — will use bundled datasets", exc_info=True)
        return 0


def _index_knowledge_base(pipeline: RetrievalPipeline) -> None:
    try:
        from app.data.knowledge_base import ENTRIES

        for entry in ENTRIES:
            text = f"{entry.topic}: {entry.answer}"
            pipeline.add_document(text, {
                "domain": "general",
                "type": "kb_entry",
                "topic": entry.topic,
                "sources": entry.sources,
                "keywords": entry.keywords,
            })
        logger.info("Retrieval: indexed %d KB entries", len(ENTRIES))
    except Exception:
        logger.warning("Failed to index KB entries", exc_info=True)


def _index_json_datasets(pipeline: RetrievalPipeline) -> None:
    """Index bundled JSON datasets with generic domain labels."""
    try:
        from app.data.ingestion import STORE

        n = 0

        for edge in STORE.cytokine_edges:
            text = (
                f"{edge.source} {edge.edge_type} {edge.target} "
                f"via {edge.pathway}. {edge.description}"
            )
            pipeline.add_document(text, {
                "domain": "general",
                "type": "dataset_record",
                "source": "cytokine_network",
                "pmid": edge.pmid,
            })
            n += 1

        for pw in STORE.pathways:
            pipeline.add_document(
                f"{pw.pathway_name}: {pw.description}",
                {
                    "domain": "general",
                    "type": "dataset_record",
                    "source": "immune_pathways",
                    "id": pw.pathway_id,
                },
            )
            for node in pw.key_nodes[:10]:
                gene = node.get("gene", "")
                role = node.get("role", "")
                if gene and role:
                    pipeline.add_document(
                        f"{gene} in {pw.pathway_name}: {role}",
                        {
                            "domain": "general",
                            "type": "dataset_record",
                            "source": "immune_pathways",
                        },
                    )
            n += 1

        for dis in STORE.diseases:
            text = (
                f"{dis.disease_name}: {dis.description} "
                f"Key mechanisms: {', '.join(dis.pathogenic_mechanisms[:5])}."
            )
            pipeline.add_document(text, {
                "domain": "general",
                "type": "dataset_record",
                "source": "disease_associations",
                "id": dis.disease_id,
            })
            for gene_rec in dis.associated_genes[:15]:
                gene = gene_rec.get("gene", "")
                desc = gene_rec.get("description", "")
                if gene and desc:
                    pipeline.add_document(
                        f"{gene} is associated with {dis.disease_name}: {desc}",
                        {
                            "domain": "general",
                            "type": "dataset_record",
                            "source": "disease_associations",
                        },
                    )
            n += 1

        for rx in STORE.therapeutics:
            indications = [i.get("disease", "") for i in rx.approved_indications[:6]]
            text = (
                f"{rx.drug_name} ({rx.brand_name}) is a {rx.drug_class} "
                f"targeting {rx.target}. {rx.mechanism} "
                f"Approved indications: {', '.join(indications)}."
            )
            pipeline.add_document(text, {
                "domain": "general",
                "type": "dataset_record",
                "source": "therapeutic_targets",
            })
            n += 1

        logger.info("Retrieval: indexed %d records from bundled JSON datasets", n)
    except Exception:
        logger.warning("Failed to index bundled datasets", exc_info=True)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def retrieve(
    query: str,
    top_k: int = 8,
    query_image_bytes: bytes | None = None,
) -> list[RetrievedProposition]:
    """Retrieve top-k propositions for a query using the hybrid pipeline.

    Pass `query_image_bytes` to enable image→image retrieval via CLIP
    (used when the user uploads a probe figure with their question).
    """
    pipeline = get_pipeline()
    if not pipeline.is_ready:
        return []
    results = pipeline.retrieve(query, top_k=top_k, query_image_bytes=query_image_bytes)
    logger.debug("Retrieved %d propositions for query: %s", len(results), query[:60])
    return results


def warm_up() -> None:
    """Trigger pipeline initialization in a background thread (call at startup)."""
    t = threading.Thread(target=get_pipeline, daemon=True, name="retrieval-warmup")
    t.start()
    logger.info("Retrieval pipeline warm-up started in background")
