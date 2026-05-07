import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.dmi.routes import router as dmi_router
from app.observability.logging import configure_structlog

configure_structlog()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description=(
        "Disease Mechanism Intelligence — AI system that maps causal disease biology "
        "and generates mechanistically grounded target risk assessments from primary literature."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(dmi_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Kick off retrieval pipeline warm-up in the background."""
    from app.services.retrieval_service import warm_up
    warm_up()
    logger.info("Retrieval pipeline warm-up initiated")


@app.get("/health")
def health() -> dict[str, str]:
    from app.services.retrieval_service import get_pipeline
    pipeline = get_pipeline()
    retrieval_status = "ready" if pipeline.is_ready else "warming_up"
    return {
        "status": "healthy",
        "service": settings.app_name,
        "retrieval": retrieval_status,
        "docs_indexed": str(pipeline.doc_count),
    }


@app.get("/metrics")
def metrics() -> dict:
    """Return current cost and pipeline stats."""
    from app.routing.cost_tracker import get_daily_total, check_budget
    from app.services.retrieval_service import get_pipeline

    pipeline = get_pipeline()
    return {
        "daily_cost_usd": round(get_daily_total(), 4),
        "budget_ok": check_budget(),
        "retrieval_docs": pipeline.doc_count,
        "retrieval_ready": pipeline.is_ready,
    }
