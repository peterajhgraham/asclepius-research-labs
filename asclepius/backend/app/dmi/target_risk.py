"""Target Risk Report builder for DMI.

Pipeline:
1. Fetch target-specific literature
2. Extract target assessment (LLM or fallback) on all articles
3. Apply heuristic scoring rules
4. Return structured risk report
"""

from __future__ import annotations

import logging

from app.dmi.schemas import (
    HistoricalFailure,
    TargetRiskResponse,
)
from app.dmi.pubmed import fetch_target_literature, fetch_preprints
from app.dmi.extractor import extract_target_assessment
from app.dmi.scoring import (
    compute_mechanistic_risk,
    compute_overall_risk,
    compute_translational_risk,
)
from app.dmi.citation_utils import deduplicate_pmids

logger = logging.getLogger(__name__)


def generate_target_risk_report(
    disease_name: str,
    target_name: str,
    vertical: str,
) -> TargetRiskResponse:
    """Generate a target risk assessment report."""
    logger.info(
        "Generating target risk report: disease=%r target=%r vertical=%s",
        disease_name,
        target_name,
        vertical,
    )

    # 1. Fetch literature (PubMed + bioRxiv/medRxiv preprints)
    articles = fetch_target_literature(disease_name, target_name, max_results=50)
    preprints = fetch_preprints(f"{target_name} {disease_name}", max_results=10)
    articles = articles + [p for p in preprints if p.pmid not in {a.pmid for a in articles}]

    if not articles:
        return TargetRiskResponse(
            target=target_name,
            disease=disease_name,
            risk_explanation=(
                f"No literature found for target '{target_name}' in the context of "
                f"'{disease_name}'. Unable to assess risk."
            ),
        )

    # 2. Extract target assessment directly on all articles
    extracted = extract_target_assessment(
        disease_name, target_name, vertical, articles
    )

    # 4. Build historical failures
    historical_failures = []
    all_pmids: list[str] = []
    for hf in extracted.get("historical_failures", []):
        pmids = hf.get("evidence_pmids", [])
        all_pmids.extend(pmids)
        historical_failures.append(HistoricalFailure(
            program=hf.get("program", ""),
            failure_stage=hf.get("failure_stage", ""),
            reason=hf.get("reason", ""),
            evidence_pmids=pmids,
        ))

    # 5. Extract scoring inputs
    pathway_position = extracted.get("pathway_position", "midstream")
    redundancy_level = extracted.get("redundancy_level", "medium")
    biomarker_alignment = extracted.get("biomarker_alignment", "moderate")
    contradictory_evidence = extracted.get("contradictory_evidence", False)
    phase2_failures = extracted.get("phase2_failures", 0)

    # 6. Compute risk scores
    mech_risk = compute_mechanistic_risk(
        pathway_position=pathway_position,
        redundancy_level=redundancy_level,
        contradictory_evidence=contradictory_evidence,
    )
    trans_risk = compute_translational_risk(
        phase2_failures=phase2_failures,
        biomarker_alignment=biomarker_alignment,
        historical_failure_count=len(historical_failures),
    )
    overall_risk = compute_overall_risk(mech_risk, trans_risk)

    # Collect all PMIDs
    for a in articles:
        if a.pmid:
            all_pmids.append(a.pmid)

    risk_explanation = extracted.get("risk_explanation", "")
    if not risk_explanation:
        risk_explanation = (
            f"{target_name} in {disease_name}: "
            f"pathway position is {pathway_position}, "
            f"redundancy is {redundancy_level}, "
            f"biomarker alignment is {biomarker_alignment}. "
            f"{len(historical_failures)} historical failure(s) identified. "
            f"Overall risk score: {overall_risk}/100."
        )

    return TargetRiskResponse(
        target=target_name,
        disease=disease_name,
        pathway_position=pathway_position,
        redundancy_level=redundancy_level,
        historical_failures=historical_failures,
        biomarker_alignment=biomarker_alignment,
        mechanistic_risk_score=mech_risk,
        translational_risk_score=trans_risk,
        overall_risk_score=overall_risk,
        risk_explanation=risk_explanation,
        citations=deduplicate_pmids(all_pmids),
    )
