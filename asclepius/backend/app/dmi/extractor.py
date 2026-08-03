"""LLM-based mechanism extraction for DMI reports.

Uses structured prompting with domain-adaptive templates to extract
mechanism data from PubMed abstracts.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.ai_client import get_client as _get_anthropic_client
from app.routing.cost_tracker import record_query
from app.services.pubmed_service import PubMedArticle

logger = logging.getLogger(__name__)

_DMI_EXTRACTION_MODEL = "claude-haiku-4-5"


# ------------------------------------------------------------------
# Domain-adaptive prompt templates
# ------------------------------------------------------------------

_DOMAIN_FOCUS: dict[str, str] = {
    "immunology": """
Focus your extraction on immunology-specific mechanisms:
- Cytokine cascades (IL-1, IL-6, IL-17, IL-23, TNF, IFN-gamma, etc.)
- T cell and B cell dynamics (Th1/Th2/Th17/Treg balance, B cell hyperactivation)
- Immune dysregulation patterns (autoantibody production, complement activation)
- Innate vs adaptive immunity interplay
- Tolerance breakdown mechanisms
- HLA associations and genetic susceptibility
""",
    "oncology": """
Focus your extraction on oncology-specific mechanisms:
- Driver mutations and oncogenes (TP53, KRAS, BRAF, EGFR, etc.)
- Tumor microenvironment (TME) composition and signaling
- Immune evasion mechanisms (PD-L1, checkpoint pathways)
- Resistance mechanisms (primary and acquired)
- Angiogenesis pathways (VEGF signaling)
- DNA damage repair deficiencies
- Metabolic reprogramming (Warburg effect)
""",
    "neuroscience": """
Focus your extraction on neuroscience-specific mechanisms:
- Neuronal signaling pathways and synaptic transmission
- Glial cell dynamics (astrocytes, microglia, oligodendrocytes)
- Neuroinflammation and blood-brain barrier dysfunction
- Protein aggregation and proteostasis mechanisms
- Neurodegeneration and axonal degeneration
- Neurotransmitter systems (dopamine, serotonin, glutamate, GABA)
""",
}

_GENERAL_FOCUS = """
Extract the core mechanisms and pathways relevant to this condition or topic.
Focus on: key molecular actors, signaling pathways, validated targets, failed interventions,
conflicting evidence, and open research questions. Be domain-agnostic and comprehensive.
"""


def _get_domain_focus(vertical: str) -> str:
    return _DOMAIN_FOCUS.get(vertical.lower(), _GENERAL_FOCUS)


# ------------------------------------------------------------------
# JSON fence stripping
# ------------------------------------------------------------------

def _strip_json_fence(text: str) -> str:
    text = text.strip()
    # Remove opening fence (with optional language tag like ```json)
    text = re.sub(r'^```[a-z]*\n?', '', text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r'\n?```$', '', text)
    return text.strip()


# ------------------------------------------------------------------
# Disease mechanism extraction
# ------------------------------------------------------------------

_DISEASE_SYSTEM_PROMPT = """You are a biomedical knowledge extractor. Given scientific text, extract structured disease mechanism information as JSON.

Extraction rules:
- Every biological claim must have at least one PMID from the provided literature.
- Only use PMIDs explicitly present in the provided abstracts. If a claim lacks PMID support, omit it.
- Be specific and mechanistic, not generic.

{vertical_focus}"""


_DISEASE_SCHEMA = """{
  "disease_summary": "string — 2-4 sentence mechanistic overview",
  "core_pathways": [
    {
      "name": "string — pathway name",
      "description": "string — mechanistic role in disease",
      "evidence_pmids": ["string"]
    }
  ],
  "causal_genes": ["string — gene symbols"],
  "key_cell_types": ["string — specific cell types involved"],
  "validated_targets": [
    {
      "target": "string — molecular target",
      "mechanism": "string — how it's targeted",
      "evidence_pmids": ["string"]
    }
  ],
  "failed_targets": [
    {
      "target": "string",
      "stage_failed": "preclinical | phase1 | phase2 | phase3",
      "mechanistic_reason": "string",
      "evidence_pmids": ["string"]
    }
  ],
  "mechanistic_contradictions": [
    {
      "description": "string — conflicting evidence",
      "evidence_pmids": ["string"]
    }
  ],
  "biomarkers": ["string — relevant biomarkers"],
  "unresolved_questions": ["string — key unknowns"]
}"""


def extract_disease_mechanisms(
    disease_name: str,
    vertical: str,
    articles: list[PubMedArticle],
) -> dict[str, Any]:
    """Extract structured disease mechanism data from articles.

    Returns an empty structure with ``_fallback: True`` when the Anthropic
    client is unavailable or extraction fails — never fabricates stub data.
    """
    if _get_anthropic_client() is None:
        logger.warning("Anthropic client unavailable (set ANTHROPIC_API_KEY) — skipping extraction for disease=%r", disease_name)
        return {
            "disease_summary": "",
            "core_pathways": [],
            "causal_genes": [],
            "key_cell_types": [],
            "validated_targets": [],
            "failed_targets": [],
            "mechanistic_contradictions": [],
            "biomarkers": [],
            "unresolved_questions": [],
            "_fallback": True,
        }

    context = _build_literature_context(articles)
    system_prompt = _DISEASE_SYSTEM_PROMPT.format(
        vertical_focus=_get_domain_focus(vertical)
    )

    user_prompt = (
        f"<context>\n{context}\n</context>\n\n"
        f"<task>\nExtract disease mechanism information for {disease_name} from the context above.\n</task>\n\n"
        f"<output_format>\nOutput only a single valid JSON object with this exact schema. "
        f"No markdown fences, no commentary.\n\n{_DISEASE_SCHEMA}\n</output_format>"
    )

    try:
        response = _get_anthropic_client().messages.create(
            model=_DMI_EXTRACTION_MODEL,
            max_tokens=3000,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        record_query(
            model=_DMI_EXTRACTION_MODEL,
            query=disease_name[:100],
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        raw = response.content[0].text or "{}"
        raw = _strip_json_fence(raw)

        return json.loads(raw)
    except Exception:
        logger.warning(
            "Claude extraction failed for disease=%r, returning empty structure",
            disease_name,
            exc_info=True,
        )
        return {
            "disease_summary": "",
            "core_pathways": [],
            "causal_genes": [],
            "key_cell_types": [],
            "validated_targets": [],
            "failed_targets": [],
            "mechanistic_contradictions": [],
            "biomarkers": [],
            "unresolved_questions": [],
            "_fallback": True,
        }


# ------------------------------------------------------------------
# Target-specific extraction
# ------------------------------------------------------------------

_TARGET_SYSTEM_PROMPT = """You are a biomedical knowledge extractor. Given scientific text, assess a drug target's viability as JSON.

Extraction rules:
- Every claim must have PMID support from the provided literature.
- Do not fabricate PMIDs.
- Be specific about mechanisms and failure reasons.

{vertical_focus}"""


_TARGET_SCHEMA = """{
  "pathway_position": "upstream | midstream | downstream",
  "redundancy_level": "low | medium | high",
  "historical_failures": [
    {
      "program": "string — drug/program name",
      "failure_stage": "string — phase of failure",
      "reason": "string — mechanistic reason",
      "evidence_pmids": ["string"]
    }
  ],
  "biomarker_alignment": "strong | moderate | weak",
  "parallel_pathways_count": 0,
  "contradictory_evidence": false,
  "biomarker_mentions": 0,
  "phase2_failures": 0,
  "risk_explanation": "string — 2-3 sentence risk summary"
}"""


def extract_target_assessment(
    disease_name: str,
    target_name: str,
    vertical: str,
    articles: list[PubMedArticle],
) -> dict[str, Any]:
    """Extract target risk assessment data from articles.

    Returns an empty structure with ``_fallback: True`` when the Anthropic
    client is unavailable or extraction fails — never fabricates stub data.
    """
    if _get_anthropic_client() is None:
        logger.warning(
            "Anthropic client unavailable — skipping target extraction for disease=%r target=%r",
            disease_name, target_name,
        )
        return {
            "pathway_position": "",
            "redundancy_level": "",
            "historical_failures": [],
            "biomarker_alignment": "",
            "parallel_pathways_count": 0,
            "contradictory_evidence": False,
            "biomarker_mentions": 0,
            "phase2_failures": 0,
            "risk_explanation": "",
            "_fallback": True,
        }

    context = _build_literature_context(articles)
    system_prompt = _TARGET_SYSTEM_PROMPT.format(
        vertical_focus=_get_domain_focus(vertical)
    )

    user_prompt = (
        f"<context>\n{context}\n</context>\n\n"
        f"<task>\nAssess {target_name} as a therapeutic target for {disease_name}. "
        f"Evaluate pathway position, redundancy, historical failures, and biomarker alignment "
        f"from the context above.\n</task>\n\n"
        f"<output_format>\nOutput only a single valid JSON object with this exact schema. "
        f"No markdown fences, no commentary.\n\n{_TARGET_SCHEMA}\n</output_format>"
    )

    try:
        response = _get_anthropic_client().messages.create(
            model=_DMI_EXTRACTION_MODEL,
            max_tokens=2000,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        record_query(
            model=_DMI_EXTRACTION_MODEL,
            query=f"{disease_name} / {target_name}"[:100],
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        raw = response.content[0].text or "{}"
        raw = _strip_json_fence(raw)

        return json.loads(raw)
    except Exception:
        logger.warning(
            "Claude target extraction failed for disease=%r target=%r, returning empty structure",
            disease_name,
            target_name,
            exc_info=True,
        )
        return {
            "pathway_position": "",
            "redundancy_level": "",
            "historical_failures": [],
            "biomarker_alignment": "",
            "parallel_pathways_count": 0,
            "contradictory_evidence": False,
            "biomarker_mentions": 0,
            "phase2_failures": 0,
            "risk_explanation": "",
            "_fallback": True,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_literature_context(articles: list[PubMedArticle], max_chars: int = 20000) -> str:
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


