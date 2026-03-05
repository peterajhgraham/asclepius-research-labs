"""LLM-based mechanism extraction for DMI reports.

Uses structured prompting with vertical-specific templates to extract
disease mechanism data from PubMed abstracts.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.config import settings
from app.services.pubmed_service import PubMedArticle
from app.dmi.schemas import Vertical

logger = logging.getLogger(__name__)

_openai_client: Optional[Any] = None

if settings.openai_api_key:
    try:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("DMI extractor: OpenAI client initialised")
    except ImportError:
        logger.warning("openai package not installed — DMI extractor will use fallback mode")


# ------------------------------------------------------------------
# Vertical-specific prompt templates
# ------------------------------------------------------------------

_IMMUNOLOGY_FOCUS = """
Focus your extraction on immunology-specific mechanisms:
- Cytokine cascades (IL-1, IL-6, IL-17, IL-23, TNF, IFN-gamma, etc.)
- T cell and B cell dynamics (Th1/Th2/Th17/Treg balance, B cell hyperactivation)
- Immune dysregulation patterns (autoantibody production, complement activation)
- Innate vs adaptive immunity interplay
- Tolerance breakdown mechanisms
- HLA associations and genetic susceptibility
"""

_ONCOLOGY_FOCUS = """
Focus your extraction on oncology-specific mechanisms:
- Driver mutations and oncogenes (TP53, KRAS, BRAF, EGFR, etc.)
- Tumor microenvironment (TME) composition and signaling
- Immune evasion mechanisms (PD-L1, checkpoint pathways)
- Resistance mechanisms (primary and acquired)
- Angiogenesis pathways (VEGF signaling)
- DNA damage repair deficiencies
- Metabolic reprogramming (Warburg effect)
"""


def _get_vertical_focus(vertical: Vertical) -> str:
    if vertical == Vertical.immunology:
        return _IMMUNOLOGY_FOCUS
    return _ONCOLOGY_FOCUS


# ------------------------------------------------------------------
# Disease mechanism extraction
# ------------------------------------------------------------------

_DISEASE_SYSTEM_PROMPT = """You are a biomedical research analyst specializing in disease mechanism extraction.
You MUST return ONLY valid JSON matching the exact schema below. No markdown, no explanation outside JSON.

CRITICAL RULES:
1. Every biological claim MUST have at least one PMID from the provided literature
2. Do NOT fabricate PMIDs — only use PMIDs explicitly mentioned in the provided abstracts
3. If a claim cannot be supported by provided PMIDs, omit it
4. Be specific and mechanistic, not generic

{vertical_focus}

OUTPUT JSON SCHEMA:
{{
  "disease_summary": "string — 2-4 sentence mechanistic overview",
  "core_pathways": [
    {{
      "name": "string — pathway name",
      "description": "string — mechanistic role in disease",
      "evidence_pmids": ["string"]
    }}
  ],
  "causal_genes": ["string — gene symbols"],
  "key_cell_types": ["string — specific cell types involved"],
  "validated_targets": [
    {{
      "target": "string — molecular target",
      "mechanism": "string — how it's targeted",
      "evidence_pmids": ["string"]
    }}
  ],
  "failed_targets": [
    {{
      "target": "string",
      "stage_failed": "preclinical | phase1 | phase2 | phase3",
      "mechanistic_reason": "string",
      "evidence_pmids": ["string"]
    }}
  ],
  "mechanistic_contradictions": [
    {{
      "description": "string — conflicting evidence",
      "evidence_pmids": ["string"]
    }}
  ],
  "biomarkers": ["string — relevant biomarkers"],
  "unresolved_questions": ["string — key unknowns"]
}}"""


def extract_disease_mechanisms(
    disease_name: str,
    vertical: Vertical,
    articles: list[PubMedArticle],
) -> dict[str, Any]:
    """Extract structured disease mechanism data from articles."""
    if _openai_client is None:
        return _fallback_disease_extraction(disease_name, vertical, articles)

    context = _build_literature_context(articles)
    system_prompt = _DISEASE_SYSTEM_PROMPT.format(
        vertical_focus=_get_vertical_focus(vertical)
    )

    user_prompt = (
        f"Disease: {disease_name}\n"
        f"Vertical: {vertical.value}\n\n"
        f"Literature context (abstracts with PMIDs):\n{context}\n\n"
        f"Extract the structured disease mechanism report for {disease_name}. "
        f"Only include claims supported by the provided PMIDs."
    )

    try:
        response = _openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        raw = response.choices[0].message.content or "{}"
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        return json.loads(raw)
    except Exception:
        logger.warning("LLM extraction failed, using fallback", exc_info=True)
        return _fallback_disease_extraction(disease_name, vertical, articles)


# ------------------------------------------------------------------
# Target-specific extraction
# ------------------------------------------------------------------

_TARGET_SYSTEM_PROMPT = """You are a biomedical analyst specializing in drug target assessment.
You MUST return ONLY valid JSON matching the exact schema below. No markdown, no explanation.

CRITICAL RULES:
1. Every claim MUST have PMID support from the provided literature
2. Do NOT fabricate PMIDs
3. Be specific about mechanisms and failure reasons

{vertical_focus}

OUTPUT JSON SCHEMA:
{{
  "pathway_position": "upstream | midstream | downstream",
  "redundancy_level": "low | medium | high",
  "historical_failures": [
    {{
      "program": "string — drug/program name",
      "failure_stage": "string — phase of failure",
      "reason": "string — mechanistic reason",
      "evidence_pmids": ["string"]
    }}
  ],
  "biomarker_alignment": "strong | moderate | weak",
  "parallel_pathways_count": 0,
  "contradictory_evidence": false,
  "biomarker_mentions": 0,
  "phase2_failures": 0,
  "risk_explanation": "string — 2-3 sentence risk summary"
}}"""


def extract_target_assessment(
    disease_name: str,
    target_name: str,
    vertical: Vertical,
    articles: list[PubMedArticle],
) -> dict[str, Any]:
    """Extract target risk assessment data from articles."""
    if _openai_client is None:
        return _fallback_target_extraction(disease_name, target_name, vertical, articles)

    context = _build_literature_context(articles)
    system_prompt = _TARGET_SYSTEM_PROMPT.format(
        vertical_focus=_get_vertical_focus(vertical)
    )

    user_prompt = (
        f"Disease: {disease_name}\n"
        f"Target: {target_name}\n"
        f"Vertical: {vertical.value}\n\n"
        f"Literature context (abstracts with PMIDs):\n{context}\n\n"
        f"Assess {target_name} as a therapeutic target for {disease_name}. "
        f"Evaluate pathway position, redundancy, historical failures, and biomarker alignment."
    )

    try:
        response = _openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content or "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        return json.loads(raw)
    except Exception:
        logger.warning("LLM target extraction failed, using fallback", exc_info=True)
        return _fallback_target_extraction(disease_name, target_name, vertical, articles)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_literature_context(articles: list[PubMedArticle], max_chars: int = 12000) -> str:
    """Build a literature context string from articles."""
    parts: list[str] = []
    total = 0
    for a in articles:
        entry = f"[PMID:{a.pmid}] {a.title}\n{a.abstract[:400]}\n"
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)
    return "\n".join(parts)


# ------------------------------------------------------------------
# Fallback extraction (no LLM)
# ------------------------------------------------------------------

def _fallback_disease_extraction(
    disease_name: str,
    vertical: Vertical,
    articles: list[PubMedArticle],
) -> dict[str, Any]:
    """Rule-based fallback when no LLM is available."""
    pmids = [a.pmid for a in articles if a.pmid][:20]

    all_text = " ".join(a.abstract for a in articles)

    # Simple keyword extraction for pathways
    pathway_keywords = {
        "immunology": [
            "JAK-STAT", "NF-kB", "IL-17/IL-23", "TNF signaling",
            "Th17 differentiation", "B cell receptor signaling",
        ],
        "oncology": [
            "PI3K/AKT/mTOR", "RAS/MAPK", "Wnt/beta-catenin",
            "p53 pathway", "VEGF signaling", "PD-1/PD-L1",
        ],
    }

    found_pathways = []
    for pw in pathway_keywords.get(vertical.value, []):
        pw_lower = pw.lower().replace("/", " ").replace("-", " ")
        if any(kw in all_text.lower() for kw in pw_lower.split()):
            found_pathways.append({
                "name": pw,
                "description": f"{pw} pathway involvement in {disease_name}",
                "evidence_pmids": pmids[:3],
            })

    return {
        "disease_summary": (
            f"{disease_name} is a complex disease with multiple underlying mechanisms. "
            f"Analysis based on {len(articles)} publications from PubMed."
        ),
        "core_pathways": found_pathways[:5],
        "causal_genes": [],
        "key_cell_types": [],
        "validated_targets": [],
        "failed_targets": [],
        "mechanistic_contradictions": [],
        "biomarkers": [],
        "unresolved_questions": [
            f"What are the primary drivers of {disease_name} pathogenesis?",
            f"Which therapeutic targets show the most promise for {disease_name}?",
        ],
    }


def _fallback_target_extraction(
    disease_name: str,
    target_name: str,
    vertical: Vertical,
    articles: list[PubMedArticle],
) -> dict[str, Any]:
    """Rule-based fallback for target assessment."""
    return {
        "pathway_position": "midstream",
        "redundancy_level": "medium",
        "historical_failures": [],
        "biomarker_alignment": "moderate",
        "parallel_pathways_count": 2,
        "contradictory_evidence": False,
        "biomarker_mentions": len([
            a for a in articles
            if "biomarker" in a.abstract.lower()
        ]),
        "phase2_failures": 0,
        "risk_explanation": (
            f"Assessment of {target_name} for {disease_name} based on "
            f"{len(articles)} publications. Further LLM-based analysis requires "
            f"an OpenAI API key."
        ),
    }
