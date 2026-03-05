"""FastAPI routes for Disease Mechanism Intelligence (DMI)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.dmi.schemas import (
    DiseaseReportRequest,
    DiseaseReportResponse,
    TargetRiskRequest,
    TargetRiskResponse,
)
from app.dmi.disease_report import generate_disease_report
from app.dmi.target_risk import generate_target_risk_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dmi", tags=["DMI"])


@router.post("/disease-report", response_model=DiseaseReportResponse)
def disease_report(request: DiseaseReportRequest) -> DiseaseReportResponse:
    """Generate a structured, citation-backed Disease Mechanism Report.

    Supported verticals: immunology, oncology.
    """
    try:
        return generate_disease_report(
            disease_name=request.disease_name,
            vertical=request.vertical,
        )
    except Exception as exc:
        logger.exception("Error generating disease report")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate disease report: {exc}",
        ) from exc


@router.post("/target-risk", response_model=TargetRiskResponse)
def target_risk(request: TargetRiskRequest) -> TargetRiskResponse:
    """Generate a structured Target Risk Report with rule-based scoring.

    Supported verticals: immunology, oncology.
    """
    try:
        return generate_target_risk_report(
            disease_name=request.disease_name,
            target_name=request.target_name,
            vertical=request.vertical,
        )
    except Exception as exc:
        logger.exception("Error generating target risk report")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate target risk report: {exc}",
        ) from exc
