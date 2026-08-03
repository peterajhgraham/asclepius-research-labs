"""Disease Mechanism Report builder for DMI.

Pipeline:
1. Fetch literature from PubMed
2. Run extraction prompt (LLM or fallback) on all articles
3. Validate and assemble structured report
4. Aggregate PMIDs into all_citations
"""

from __future__ import annotations

import logging

from app.dmi.schemas import (
    CorePathway,
    DiseaseReportResponse,
    FailedTarget,
    MechanisticContradiction,
    ValidatedTarget,
)
from app.dmi.pubmed import fetch_disease_literature, fetch_preprints
from app.dmi.extractor import extract_disease_mechanisms
from app.dmi.citation_utils import deduplicate_pmids

logger = logging.getLogger(__name__)


def generate_disease_report(
    disease_name: str,
    vertical: str,
) -> DiseaseReportResponse:
    """Generate a full mechanism report."""
    logger.info("Generating disease report: disease=%r vertical=%s", disease_name, vertical)

    # 1. Fetch literature (PubMed + bioRxiv/medRxiv preprints)
    articles = fetch_disease_literature(disease_name, max_results=75)
    preprints = fetch_preprints(f"{disease_name} mechanism", max_results=10)
    articles = articles + [p for p in preprints if p.pmid not in {a.pmid for a in articles}]

    if not articles:
        return DiseaseReportResponse(
            disease_summary=(
                f"No literature found for '{disease_name}'. "
                f"Please verify the disease name and try again."
            ),
        )

    # 2. Run extraction directly on all articles
    extracted = extract_disease_mechanisms(disease_name, vertical, articles)

    # 3. Assemble response
    all_pmids: list[str] = []

    core_pathways = []
    for pw in extracted.get("core_pathways", []):
        pmids = pw.get("evidence_pmids", [])
        all_pmids.extend(pmids)
        core_pathways.append(CorePathway(
            name=pw.get("name", ""),
            description=pw.get("description", ""),
            evidence_pmids=pmids,
        ))

    validated_targets = []
    for vt in extracted.get("validated_targets", []):
        pmids = vt.get("evidence_pmids", [])
        all_pmids.extend(pmids)
        validated_targets.append(ValidatedTarget(
            target=vt.get("target", ""),
            mechanism=vt.get("mechanism", ""),
            evidence_pmids=pmids,
        ))

    failed_targets = []
    for ft in extracted.get("failed_targets", []):
        pmids = ft.get("evidence_pmids", [])
        all_pmids.extend(pmids)
        failed_targets.append(FailedTarget(
            target=ft.get("target", ""),
            stage_failed=ft.get("stage_failed", "phase2"),
            mechanistic_reason=ft.get("mechanistic_reason", ""),
            evidence_pmids=pmids,
        ))

    contradictions = []
    for mc in extracted.get("mechanistic_contradictions", []):
        pmids = mc.get("evidence_pmids", [])
        all_pmids.extend(pmids)
        contradictions.append(MechanisticContradiction(
            description=mc.get("description", ""),
            evidence_pmids=pmids,
        ))

    # Also collect PMIDs from articles used
    for a in articles:
        if a.pmid:
            all_pmids.append(a.pmid)

    return DiseaseReportResponse(
        disease_summary=extracted.get("disease_summary", ""),
        core_pathways=core_pathways,
        causal_genes=extracted.get("causal_genes", []),
        key_cell_types=extracted.get("key_cell_types", []),
        validated_targets=validated_targets,
        failed_targets=failed_targets,
        mechanistic_contradictions=contradictions,
        biomarkers=extracted.get("biomarkers", []),
        unresolved_questions=extracted.get("unresolved_questions", []),
        all_citations=deduplicate_pmids(all_pmids),
    )
