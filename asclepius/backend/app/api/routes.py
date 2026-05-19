import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
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
    RetrievedPropositionSchema,
    UpdateNotesRequest,
)
from app.services.llm_service import LLMService
from app.services.logger_service import log_query

logger = logging.getLogger(__name__)

router = APIRouter()

_llm_service = LLMService()


# ------------------------------------------------------------------
# Core query endpoint (enhanced with PubMed + graph)
# ------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """Accept a natural language question and return a structured AI-generated answer."""
    log_query(request.question)
    try:
        return _llm_service.query(
            request.question,
            include_pubmed=request.include_pubmed,
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
        return _llm_service.query_with_image(
            question=request.question,
            image_base64=request.image_base64,
            media_type=request.media_type,
            include_pubmed=request.include_pubmed,
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

    result = await ingest_document(pdf_bytes, file.filename or "upload.pdf")
    return DocumentIngestResponse(
        **result,
        message=f"Indexed {result['propositions_indexed']} text propositions and {result['images_captioned']} figure captions.",
    )


# ------------------------------------------------------------------
# SSE streaming query endpoint
# ------------------------------------------------------------------

@router.get("/query/stream")
async def query_stream(
    question: str = Query(..., min_length=1),
    include_pubmed: bool = Query(False),
) -> StreamingResponse:
    """Stream a query response as Server-Sent Events.

    Event types:
      - start:     {"type":"start","question":"..."}
      - citations: {"type":"citations","data":[...]}
      - token:     {"type":"token","text":"..."}
      - done:      {"type":"done","model":"...","cost":0.00,"sources":[...]}
    """

    async def event_gen() -> AsyncGenerator[str, None]:
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        try:
            log_query(question)
            yield sse({"type": "start", "question": question})

            from app.services.retrieval_service import retrieve
            from app.services.query_engine import search_all

            # Run CPU-bound ML retrieval off the async event loop
            propositions = await run_in_threadpool(lambda: retrieve(question, top_k=8))
            sr = await run_in_threadpool(lambda: search_all(question))

            pubmed_articles: list[PubMedResult] = []
            graph_context = LLMService._get_graph_context(sr)

            # Send citations immediately — frontend shows the panel while answer streams
            citation_data = [
                {
                    "text": p.text,
                    "score": round(p.score, 4),
                    "rerank_score": round(p.rerank_score, 4),
                    "type": p.metadata.get("type", "knowledge"),
                    "pmid": p.metadata.get("pmid", ""),
                    "source": p.metadata.get("drug_name")
                        or p.metadata.get("disease_name")
                        or p.metadata.get("pathway_name")
                        or p.metadata.get("topic")
                        or "",
                }
                for p in propositions
            ]
            yield sse({"type": "citations", "data": citation_data})

            # Build context for the LLM prompt
            props_schema = [
                RetrievedPropositionSchema(
                    text=p.text,
                    score=p.score,
                    rerank_score=p.rerank_score,
                    metadata=p.metadata,
                )
                for p in propositions
            ]
            context, sources = LLMService._build_context(
                props_schema, sr, pubmed_articles, graph_context
            )

            system = (
                "You are Asclepius, a scientific research assistant. "
                "Answer using ONLY the provided context. Structure your response with sections "
                "appropriate to the query domain (e.g., Overview, Key Mechanisms, Pathways, "
                "Key Entities, Intervention Targets, Open Research Gaps)."
            )
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Context:\n{context}\n\n"
                        f"Question: {question}\n\n"
                        "Provide a detailed, structured scientific answer."
                    ),
                }
            ]

            model_used = "local"
            cost = 0.0

            if settings.anthropic_api_key:
                from app.routing.router import stream_with_routing

                for item in stream_with_routing(
                    messages=messages,
                    system=system,
                    query_preview=question[:100],
                ):
                    if isinstance(item, dict) and item.get("_done"):
                        model_used = item.get("model", model_used)
                        cost = item.get("cost", 0.0)
                    else:
                        yield sse({"type": "token", "text": item})
            else:
                # Fallback: use non-streaming call and emit answer as a single chunk
                from app.routing.router import call_with_routing

                answer, model_used, cost = call_with_routing(
                    messages=messages,
                    system=system,
                    query_preview=question[:100],
                )
                if answer:
                    # Simulate streaming by word to keep UX consistent
                    for word in answer.split(" "):
                        yield sse({"type": "token", "text": word + " "})
                else:
                    # Pure local fallback
                    local_resp = LLMService._local_answer(
                        question, props_schema, sr, pubmed_articles, graph_context
                    )
                    for word in local_resp.answer.split(" "):
                        yield sse({"type": "token", "text": word + " "})

            yield sse({
                "type": "done",
                "model": model_used,
                "cost": cost,
                "sources": sources[:20],
            })

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
    entry = dossier_store.add_to_dossier(
        dossier_id=dossier_id,
        query=request.query,
        response=request.response,
        notes=request.notes,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Dossier not found")
    return entry


@router.put("/dossiers/{dossier_id}/entries/{entry_id}/notes")
def update_entry_notes(dossier_id: str, entry_id: str, request: UpdateNotesRequest) -> dict:
    """Update notes on a dossier entry."""
    from app.services.dossier_service import dossier_store
    dossier = dossier_store.get_dossier(dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")
    success = dossier.update_entry_notes(entry_id, request.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
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
