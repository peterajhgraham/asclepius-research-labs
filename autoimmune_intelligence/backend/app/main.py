import logging
import logging.config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.dmi.routes import router as dmi_router
from app.core.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Disease Mechanism Intelligence — AI system that maps causal disease biology and generates mechanistically grounded target risk assessments from primary literature.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(dmi_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": settings.app_name}
