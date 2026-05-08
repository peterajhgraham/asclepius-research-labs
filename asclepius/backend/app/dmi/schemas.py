"""Pydantic schemas for Mechanism Intelligence (DMI) reports."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Disease Mechanism Report
# ------------------------------------------------------------------

class CorePathway(BaseModel):
    name: str
    description: str
    evidence_pmids: list[str] = Field(default_factory=list)


class ValidatedTarget(BaseModel):
    target: str
    mechanism: str
    evidence_pmids: list[str] = Field(default_factory=list)


class FailedTarget(BaseModel):
    target: str
    stage_failed: str = Field(
        ..., description="preclinical | phase1 | phase2 | phase3"
    )
    mechanistic_reason: str
    evidence_pmids: list[str] = Field(default_factory=list)


class MechanisticContradiction(BaseModel):
    description: str
    evidence_pmids: list[str] = Field(default_factory=list)


class DiseaseReportRequest(BaseModel):
    disease_name: str = Field(..., min_length=1)
    vertical: str = Field("general", description="Research domain (e.g., immunology, oncology, neuroscience)")


class DiseaseReportResponse(BaseModel):
    disease_summary: str = ""
    core_pathways: list[CorePathway] = Field(default_factory=list)
    causal_genes: list[str] = Field(default_factory=list)
    key_cell_types: list[str] = Field(default_factory=list)
    validated_targets: list[ValidatedTarget] = Field(default_factory=list)
    failed_targets: list[FailedTarget] = Field(default_factory=list)
    mechanistic_contradictions: list[MechanisticContradiction] = Field(
        default_factory=list
    )
    biomarkers: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    all_citations: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Target Risk Report
# ------------------------------------------------------------------

class HistoricalFailure(BaseModel):
    program: str
    failure_stage: str
    reason: str
    evidence_pmids: list[str] = Field(default_factory=list)


class TargetRiskRequest(BaseModel):
    disease_name: str = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)
    vertical: str = Field("general", description="Research domain (e.g., immunology, oncology, neuroscience)")


class TargetRiskResponse(BaseModel):
    target: str = ""
    disease: str = ""
    pathway_position: str = Field(
        "midstream", description="upstream | midstream | downstream"
    )
    redundancy_level: str = Field(
        "medium", description="low | medium | high"
    )
    historical_failures: list[HistoricalFailure] = Field(default_factory=list)
    biomarker_alignment: str = Field(
        "moderate", description="strong | moderate | weak"
    )
    mechanistic_risk_score: int = Field(0, ge=0, le=100)
    translational_risk_score: int = Field(0, ge=0, le=100)
    overall_risk_score: int = Field(0, ge=0, le=100)
    risk_explanation: str = ""
    citations: list[str] = Field(default_factory=list)
