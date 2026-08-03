import asyncio
import json
import logging
from contextlib import contextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.models.schema import (
    AddToDossierRequest,
    CausalPropagateRequest,
    CompareRequest,
    CompareResponse,
    CreateDossierRequest,
    DocumentIngestResponse,
    GraphSubgraphRequest,
    HypothesisEntry,
    HypothesisRequest,
    HypothesisResponse,
    ImageQueryRequest,
    InterventionRankRequest,
    PubMedResult,
    PubMedSearchRequest,
    PubMedSearchResponse,
    QueryRequest,
    QueryResponse,
    UpdateNotesRequest,
)
from app.services.llm_service import pipeline
from app.services.logger_service import log_query

logger = logging.getLogger(__name__)

router = APIRouter()


@contextmanager
def _route_guard(name: str):
    """Catch-all exception handler for route bodies.

    Re-raises HTTPException as-is so intentional 4xx/5xx errors pass through.
    Any other exception is logged and converted to a generic 500.
    """
    try:
        yield
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error in %s", name)
        raise HTTPException(status_code=500, detail="Internal server error")


# ------------------------------------------------------------------
# Core query endpoint (enhanced with PubMed + graph)
# ------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """Accept a natural language question and return a structured AI-generated answer.

    `mode="research"` dispatches to the tool-using agent (multi-step retrieval +
    PubMed + graph). `verify=True` runs a figure-grounded verification pass after
    generation, attaching a `verification` block to the response with claim-level
    annotations.
    """
    log_query(request.question)
    mode = (request.mode or "").lower()
    if mode not in ("standard", "research", ""):
        raise HTTPException(status_code=400, detail="Unknown mode. Valid modes: standard, research")
    try:
        return pipeline.run(
            request.question,
            mode=mode,
            include_pubmed=request.include_pubmed,
            verify=request.verify,
        )
    except Exception as exc:
        logger.exception("Unhandled error in /query")
        raise HTTPException(
            status_code=500,
            detail="Internal server error — check server logs for details",
        ) from exc


# ------------------------------------------------------------------
# Multimodal image query endpoint
# ------------------------------------------------------------------

@router.post("/query/images", response_model=QueryResponse)
def query_with_image(request: ImageQueryRequest) -> QueryResponse:
    """Accept a research question + base64 image and return a vision-grounded answer."""
    log_query(f"IMAGE: {request.question}")
    try:
        return pipeline.run(
            request.question,
            include_pubmed=request.include_pubmed,
            image_base64=request.image_base64,
            image_media_type=request.media_type,
        )
    except Exception as exc:
        logger.exception("Unhandled error in /query/images")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# ------------------------------------------------------------------
# PDF document ingestion endpoint
# ------------------------------------------------------------------

@router.post("/ingest/document", response_model=DocumentIngestResponse)
async def ingest_document_endpoint(
    file: UploadFile = File(..., description="PDF file to ingest into the retrieval pipeline"),
) -> DocumentIngestResponse:
    """Ingest a PDF document into the retrieval pipeline.

    Extracts text and figures, chunks into propositions via Claude Haiku,
    captions figures via Haiku vision, stores in SQLite, and rebuilds the
    BM25+FAISS index so subsequent queries can retrieve from this document.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    from app.services.ingestion_service import ingest_document

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="PDF too large (max 50 MB)")

    with _route_guard("ingest document"):
        result = await ingest_document(pdf_bytes, file.filename or "upload.pdf")
    return DocumentIngestResponse(
        **result,
        message=(
            f"Indexed {result['propositions_indexed']} text propositions, "
            f"{result['images_captioned']} figure captions, "
            f"and {result.get('tables_indexed', 0)} tables across {result['pages']} pages."
        ),
    )


# ------------------------------------------------------------------
# Multimodal asset serving — content-addressed image retrieval
# ------------------------------------------------------------------

@router.get("/images/{image_hash}")
def get_image(image_hash: str) -> Response:
    """Serve a stored figure or table raster by SHA-256 hash.

    The hash is opaque to the client; it comes back inside the
    `retrieved_propositions[].image_hash` field of a query response.
    """
    from app.storage.image_store import get_image_store

    image_hash = image_hash.lower()
    # Defensive: hashes are 64 hex chars
    if not (16 <= len(image_hash) <= 128) or any(c not in "0123456789abcdef" for c in image_hash):
        raise HTTPException(status_code=400, detail="Invalid image hash")

    loaded = get_image_store().read(image_hash)
    if loaded is None:
        raise HTTPException(status_code=404, detail="Image not found")
    data, media_type = loaded
    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ------------------------------------------------------------------
# SSE streaming query endpoint
# ------------------------------------------------------------------

@router.get("/query/stream")
async def query_stream(
    question: str = Query(..., min_length=1),
    mode: str = Query("standard"),
    include_pubmed: bool = Query(False),
    verify: bool = Query(False),
) -> StreamingResponse:
    """Stream a query response as Server-Sent Events.

    Unified event protocol for both standard and research (agent) modes:
      start:        {"type":"start","question":"..."}
      citations:    {"type":"citations","data":[...]}           # standard only
      thinking:     {"type":"thinking","text":"..."}            # research only
      tool_call:    {"type":"tool_call","tool":"...","args":{},"iteration":N}  # research only
      tool_result:  {"type":"tool_result","tool":"...","result_preview":"...","iteration":N}
      final:        {"type":"final","answer":"...","image_hashes":[...]}       # research only
      verification: {"type":"verification",...}                 # research + verify=true
      token:        {"type":"token","text":"..."}               # standard only
      done:         {"type":"done","model":"...","cost":0.00,"sources":[...],"iterations":0}
      error:        {"type":"error","message":"..."}
    """
    HEARTBEAT_S = 15

    async def event_gen() -> AsyncGenerator[str, None]:
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, default=str)}\n\n"

        log_query(f"{'AGENT' if mode == 'research' else 'STREAM'}: {question}")
        yield sse({"type": "start", "question": question})

        if mode == "research":
            from app.services.agent_service import run_agent

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()
            _DONE = object()
            final_answer = ""
            image_hashes: list[str] = []

            def _producer() -> None:
                try:
                    for evt in run_agent(question):
                        loop.call_soon_threadsafe(queue.put_nowait, evt.to_dict())
                except Exception:
                    logger.exception("Agent loop crashed")
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "error", "message": "Internal agent error"},
                    )
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, _DONE)

            producer = asyncio.create_task(run_in_threadpool(_producer))
            producer.add_done_callback(lambda t: t.cancelled() or t.exception())
            pending_done: dict | None = None
            try:
                while True:
                    try:
                        evt = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_S)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue

                    if evt is _DONE:
                        break

                    etype = evt.get("type")
                    if etype == "done":
                        pending_done = evt
                        continue

                    yield sse(evt)
                    if etype == "final":
                        final_answer = evt.get("answer", "")
                        image_hashes = list(evt.get("image_hashes") or [])

                if verify and final_answer and image_hashes:
                    from app.services.verification_service import verify_against_figures
                    try:
                        v = await run_in_threadpool(
                            lambda: verify_against_figures(final_answer, image_hashes)
                        )
                        yield sse({"type": "verification", **v.to_dict()})
                    except Exception:
                        logger.warning("Agent verification failed", exc_info=True)

                if pending_done is not None:
                    yield sse({
                        "type": "done",
                        "model": pending_done.get("model", ""),
                        "cost": pending_done.get("cost_usd", 0),
                        "sources": [],
                        "iterations": pending_done.get("iterations", 0),
                    })
            finally:
                producer.cancel()
        else:
            try:
                loop = asyncio.get_running_loop()
                queue: asyncio.Queue = asyncio.Queue()
                _DONE = object()

                def _producer() -> None:
                    try:
                        for event_dict in pipeline.stream(question, include_pubmed=include_pubmed):
                            loop.call_soon_threadsafe(queue.put_nowait, event_dict)
                    except Exception as exc:
                        loop.call_soon_threadsafe(queue.put_nowait, exc)
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, _DONE)

                stream_task = asyncio.create_task(run_in_threadpool(_producer))
                stream_task.add_done_callback(lambda t: t.cancelled() or t.exception())
                try:
                    while True:
                        item = await queue.get()
                        if item is _DONE:
                            break
                        if isinstance(item, Exception):
                            raise item
                        yield sse(item)
                finally:
                    stream_task.cancel()
            except Exception:
                logger.exception("Streaming error")
                yield sse({"type": "error", "message": "Internal streaming error"})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ------------------------------------------------------------------
# Comparative analysis
# ------------------------------------------------------------------

@router.post("/compare", response_model=CompareResponse)
def compare_diseases(request: CompareRequest) -> CompareResponse:
    """Compare two topics or conditions across all indexed dimensions."""
    from app.services.comparative_service import compare_diseases as do_compare

    log_query(f"COMPARE: {request.disease_a} vs {request.disease_b}")
    with _route_guard("/compare"):
        result = do_compare(request.disease_a, request.disease_b)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"One or both diseases not found: '{request.disease_a}', '{request.disease_b}'. "
                   f"Use GET /diseases to see available diseases.",
        )
    return CompareResponse(**result)


@router.get("/diseases")
def list_diseases() -> dict:
    """List all diseases available for comparison."""
    from app.services.comparative_service import list_available_diseases
    diseases = list_available_diseases()
    return {"diseases": diseases, "count": len(diseases)}


# ------------------------------------------------------------------
# Hypothesis generator
# ------------------------------------------------------------------

@router.post("/hypotheses", response_model=HypothesisResponse)
def generate_hypotheses(request: HypothesisRequest) -> HypothesisResponse:
    """Generate testable research hypotheses for a given topic."""
    from app.services.hypothesis_service import generate_hypotheses as do_generate

    log_query(f"HYPOTHESIS: {request.topic}")
    with _route_guard("/hypotheses"):
        result = do_generate(request.topic, max_hypotheses=request.max_hypotheses)
    return HypothesisResponse(
        topic=result["topic"],
        hypotheses=[HypothesisEntry(**h) for h in result["hypotheses"]],
        context=result["context"],
        total_generated=result["total_generated"],
    )


# ------------------------------------------------------------------
# Live PubMed search
# ------------------------------------------------------------------

@router.post("/pubmed/search", response_model=PubMedSearchResponse)
def search_pubmed(request: PubMedSearchRequest) -> PubMedSearchResponse:
    """Search PubMed for articles related to a query."""
    from app.services.pubmed_service import pubmed

    log_query(f"PUBMED: {request.query}")
    try:
        if request.domain_enriched:
            articles = pubmed.search_autoimmune(request.query, max_results=request.max_results)
        else:
            articles = pubmed.search(request.query, max_results=request.max_results)

        interactions = pubmed.extract_interactions(articles)

        return PubMedSearchResponse(
            query=request.query,
            articles=[
                PubMedResult(
                    pmid=a.pmid,
                    title=a.title,
                    abstract=a.abstract[:500],
                    authors=a.authors[:5],
                    journal=a.journal,
                    year=a.year,
                    doi=a.doi,
                    citation=a.citation,
                )
                for a in articles
            ],
            interactions=interactions[:20],
            total_found=len(articles),
        )
    except Exception as exc:
        logger.warning("PubMed search failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"PubMed search failed: {exc}",
        ) from exc


# ------------------------------------------------------------------
# Knowledge graph operations
# ------------------------------------------------------------------

@router.get("/graph/stats")
def graph_stats() -> dict:
    """Return summary statistics about the knowledge graph."""
    from app.services.graph_service import knowledge_graph
    return knowledge_graph.get_stats()


@router.post("/graph/subgraph")
def graph_subgraph(request: GraphSubgraphRequest) -> dict:
    """Extract a subgraph around seed nodes."""
    from app.services.graph_service import knowledge_graph
    return knowledge_graph.get_subgraph(request.seed_nodes, hops=request.hops)


@router.get("/graph/hubs")
def graph_hubs(n: int = 15) -> dict:
    """Return the most highly connected nodes in the graph."""
    from app.services.graph_service import knowledge_graph
    hubs = knowledge_graph.get_hubs(n=n)
    return {"hubs": hubs}


@router.post("/graph/propagate")
def causal_propagate(request: CausalPropagateRequest) -> dict:
    """Run causal signal propagation from seed nodes."""
    from app.services.graph_service import knowledge_graph
    scores = knowledge_graph.propagate_signal(
        request.seed_scores,
        direction=request.direction,
    )
    # Sort by absolute score descending
    ranked = sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True)
    return {
        "scores": {k: round(v, 6) for k, v in ranked[:50]},
        "total_nodes_affected": len([v for _, v in ranked if abs(v) > 0.001]),
    }


@router.post("/graph/interventions")
def rank_interventions(request: InterventionRankRequest) -> dict:
    """Rank upstream intervention targets for a given target node."""
    from app.services.graph_service import knowledge_graph
    rankings = knowledge_graph.rank_interventions(
        target_node=request.target_node,
        cell_type_context=request.cell_type_context,
        top_k=request.top_k,
    )
    return {"target": request.target_node, "interventions": rankings}


# ------------------------------------------------------------------
# Disease dossiers
# ------------------------------------------------------------------

@router.post("/dossiers")
def create_dossier(request: CreateDossierRequest) -> dict:
    """Create a new disease dossier."""
    from app.services.dossier_service import dossier_store
    dossier = dossier_store.create_dossier(
        name=request.name,
        description=request.description,
        tags=request.tags,
    )
    return dossier.to_summary()


@router.get("/dossiers")
def list_dossiers() -> dict:
    """List all disease dossiers."""
    from app.services.dossier_service import dossier_store
    return {"dossiers": dossier_store.list_dossiers()}


@router.get("/dossiers/{dossier_id}")
def get_dossier(dossier_id: str) -> dict:
    """Get a disease dossier with all entries."""
    from app.services.dossier_service import dossier_store
    dossier = dossier_store.get_dossier(dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")
    return dossier.to_dict()


@router.post("/dossiers/{dossier_id}/entries")
def add_to_dossier(dossier_id: str, request: AddToDossierRequest) -> dict:
    """Add a query result to a dossier."""
    from app.services.dossier_service import dossier_store
    dossier = dossier_store.get_dossier(dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")
    try:
        entry = dossier_store.add_to_dossier(
            dossier_id=dossier_id,
            query=request.query,
            response=request.response,
            notes=request.notes,
        )
    except Exception:
        logger.exception("Failed to add to dossier")
        raise HTTPException(status_code=500, detail="Failed to save entry")
    if entry is None:
        raise HTTPException(status_code=404, detail="Dossier not found")
    return entry


@router.put("/dossiers/{dossier_id}/entries/{entry_id}/notes")
def update_entry_notes(dossier_id: str, entry_id: str, request: UpdateNotesRequest) -> dict:
    """Update notes on a dossier entry."""
    from app.services.dossier_service import dossier_store
    success = dossier_store.update_entry_notes(dossier_id, entry_id, request.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Dossier or entry not found")
    return {"status": "updated"}


@router.delete("/dossiers/{dossier_id}")
def delete_dossier(dossier_id: str) -> dict:
    """Delete a disease dossier."""
    from app.services.dossier_service import dossier_store
    if not dossier_store.delete_dossier(dossier_id):
        raise HTTPException(status_code=404, detail="Dossier not found")
    return {"status": "deleted"}


@router.get("/dossiers/{dossier_id}/insights")
def get_dossier_insights(dossier_id: str) -> dict:
    """Get accumulated insights from a dossier."""
    from app.services.dossier_service import dossier_store
    insights = dossier_store.get_insights(dossier_id)
    if insights is None:
        raise HTTPException(status_code=404, detail="Dossier not found")
    return insights
