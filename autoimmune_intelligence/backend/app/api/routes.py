import logging
from fastapi import APIRouter, Depends, HTTPException
from app.models.schema import QueryRequest, QueryResponse
from app.services.llm_service import LLMService
from app.services.logger_service import log_query

logger = logging.getLogger(__name__)

router = APIRouter()


def get_llm_service() -> LLMService:
    return LLMService()


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, service: LLMService = Depends(get_llm_service)) -> QueryResponse:
    """Accept a natural language question and return a structured AI-generated answer."""
    log_query(request.question)
    try:
        return service.query(request.question)
    except Exception as exc:
        logger.exception("Unhandled error in /query")
        raise HTTPException(
            status_code=500,
            detail="Internal server error — check server logs for details",
        ) from exc
