"""LLM service that answers autoimmune-disease questions.

Searches across ALL data sources (knowledge base, cytokine network,
immune pathways, disease-gene associations, therapeutics) and composes
a rich, structured answer.

When an OpenAI API key is configured the matched context is sent to the
LLM for synthesis.  Without a key the service returns a locally composed
answer — no external dependency required.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.config import settings
from app.models.schema import QueryResponse, StructuredReasoning
from app.services.query_engine import search_all, SearchResult

logger = logging.getLogger(__name__)

# Optional OpenAI integration
_openai_client: Optional[object] = None

if settings.openai_api_key:
    try:
        from openai import OpenAI  # type: ignore[import-untyped]

        _openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialised (model=%s)", settings.llm_model)
    except ImportError:
        logger.warning("openai package not installed — falling back to knowledge-base mode")
    except Exception:
        logger.warning("Failed to initialise OpenAI client — falling back", exc_info=True)


class LLMService:
    """Handles queries for the Autoimmune Intelligence API."""

    def query(self, question: str) -> QueryResponse:
        logger.info("LLMService.query called with question=%r", question)

        results = search_all(question)

        if not results.has_results:
            return QueryResponse(
                answer=(
                    "I could not find a match for your query in the current "
                    "datasets. Try asking about a specific autoimmune disease "
                    "(e.g., rheumatoid arthritis, lupus, multiple sclerosis), "
                    "a cytokine pathway (e.g., JAK-STAT, NF-κB, IL-17), or "
                    "a therapeutic (e.g., adalimumab, tofacitinib)."
                ),
                sources=[],
            )

        if _openai_client is not None:
            return self._llm_answer(question, results)

        return self._local_answer(question, results)

    # ------------------------------------------------------------------
    # Structured reasoning extraction from search results
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_reasoning(sr: SearchResult) -> StructuredReasoning:
        """Extract structured immune reasoning from aggregated search hits."""
        cells: list[str] = []
        cytokines: list[str] = []
        pathways: list[str] = []
        targets: list[str] = []
        genes: list[str] = []
        open_qs: list[str] = []
        summary_parts: list[str] = []
        disease_ctx = ""

        # From disease hits
        if sr.disease_hits:
            dis = sr.disease_hits[0]
            disease_ctx = dis["description"]
            if dis.get("prevalence"):
                disease_ctx += f" Prevalence: {dis['prevalence']}."
            cells.extend(dis.get("key_cell_types", []))
            for mech in dis.get("pathogenic_mechanisms", []):
                summary_parts.append(mech)
            for g in dis.get("associated_genes", [])[:8]:
                label = g["gene"]
                if g.get("description"):
                    label += f" — {g['description']}"
                genes.append(label)
            for rx in dis.get("approved_therapies", []):
                targets.append(f"{rx['drug']} ({rx['class']})")

        # From pathway hits
        for pw in sr.pathway_hits[:3]:
            pathways.append(f"{pw['pathway_name']} — {pw['description'][:120]}")
            for tgt in pw.get("therapeutic_targets", [])[:3]:
                entry = f"{tgt.get('drug', '?')} targeting {tgt.get('target', '?')}"
                if tgt.get("mechanism"):
                    entry += f" ({tgt['mechanism']})"
                if entry not in targets:
                    targets.append(entry)

        # From cytokine hits
        seen_cytokines: set[str] = set()
        for edge in sr.cytokine_hits[:10]:
            src, tgt = edge["source"], edge["target"]
            desc = edge["description"]
            if src not in seen_cytokines:
                seen_cytokines.add(src)
                cytokines.append(f"{src} — {desc[:100]}")
            if tgt not in seen_cytokines and len(cytokines) < 10:
                seen_cytokines.add(tgt)

        # From therapeutic hits
        for rx in sr.therapeutic_hits[:5]:
            indications = [i["disease"] for i in rx.get("approved_indications", [])[:3]]
            entry = (
                f"{rx['drug_name']} ({rx['brand_name']}) — {rx['drug_class']}, "
                f"targets {rx['target']}. {rx['mechanism'][:120]}. "
                f"Approved for: {', '.join(indications)}"
            )
            if entry not in targets:
                targets.append(entry)

        # From KB hits — build summary
        if sr.kb_hits:
            summary_parts.insert(0, sr.kb_hits[0].entry.answer)

        # Generate open questions / hypotheses
        if sr.disease_hits:
            dis = sr.disease_hits[0]
            name = dis["disease_name"]
            open_qs.append(
                f"What environmental triggers initiate tolerance breakdown in {name}?"
            )
            if dis.get("associated_genes"):
                top_gene = dis["associated_genes"][0]["gene"]
                open_qs.append(
                    f"How do {top_gene} risk variants interact with epigenetic "
                    f"modifications to drive disease onset?"
                )
            if dis.get("key_cell_types"):
                open_qs.append(
                    f"Can Treg-based cell therapy restore immune tolerance in {name}?"
                )
        if sr.pathway_hits:
            pw = sr.pathway_hits[0]
            open_qs.append(
                f"Are there undiscovered feedback loops in {pw['pathway_name']} "
                f"that could be therapeutically exploited?"
            )
        if sr.therapeutic_hits:
            rx = sr.therapeutic_hits[0]
            open_qs.append(
                f"Could combination therapy with {rx['drug_name']} and a "
                f"pathway-specific agent improve treatment response?"
            )

        summary = "\n\n".join(summary_parts) if summary_parts else ""

        return StructuredReasoning(
            summary=summary,
            key_cells=cells,
            key_cytokines=cytokines,
            pathways=pathways,
            therapeutic_targets=targets,
            open_questions=open_qs,
            genes=genes,
            disease_context=disease_ctx,
        )

    # ------------------------------------------------------------------
    # Local answer — no external API required
    # ------------------------------------------------------------------
    @staticmethod
    def _local_answer(question: str, sr: SearchResult) -> QueryResponse:
        """Compose a structured answer from all matched data sources."""
        sections: list[str] = []
        sources: list[str] = []

        # 1. Primary KB narrative
        if sr.kb_hits:
            primary = sr.kb_hits[0].entry
            sections.append(primary.answer)
            for hit in sr.kb_hits:
                sources.extend(hit.entry.sources)
            for hit in sr.kb_hits[1:]:
                if hit.score > 0.1:
                    sections.append(
                        f"\n**Related — {hit.entry.topic}:**\n{hit.entry.answer}"
                    )

        # 2. Disease context
        if sr.disease_hits:
            dis = sr.disease_hits[0]
            parts = [f"\n**Disease context — {dis['disease_name']}:**"]
            parts.append(dis["description"])
            if dis.get("prevalence"):
                parts.append(f"Prevalence: {dis['prevalence']}.")
            sections.append("\n".join(parts))
            for ref in dis.get("references", []):
                sources.append(ref)

        # 3. Pathway context
        if sr.pathway_hits:
            pw = sr.pathway_hits[0]
            parts = [f"\n**Pathway — {pw['pathway_name']}** ({pw['pathway_id']}):"]
            parts.append(pw["description"])
            sections.append("\n".join(parts))
            for ref in pw.get("references", []):
                sources.append(ref)

        # 4. Cytokine network interactions
        if sr.cytokine_hits:
            parts = ["\n**Relevant cytokine interactions:**"]
            for edge in sr.cytokine_hits[:6]:
                parts.append(
                    f"{edge['source']} -> {edge['target']} "
                    f"({edge['edge_type']}) — {edge['description']}"
                )
                if edge.get("pmid"):
                    sources.append(f"PMID:{edge['pmid']}")
            sections.append("\n".join(parts))

        # 5. Therapeutics
        if sr.therapeutic_hits:
            parts = ["\n**Relevant therapeutics:**"]
            for rx in sr.therapeutic_hits[:4]:
                indications = [
                    ind["disease"] for ind in rx.get("approved_indications", [])
                ]
                parts.append(
                    f"{rx['drug_name']} ({rx['brand_name']}) — "
                    f"{rx['drug_class']}. Target: {rx['target']}. "
                    f"Approved for: {', '.join(indications[:5])}."
                )
                for trial in rx.get("pivotal_trials", [])[:1]:
                    if trial.get("pmid"):
                        sources.append(f"PMID:{trial['pmid']}")
            sections.append("\n".join(parts))

        # Deduplicate sources
        seen: set[str] = set()
        unique_sources: list[str] = []
        for s in sources:
            if s not in seen:
                seen.add(s)
                unique_sources.append(s)

        reasoning = LLMService._extract_reasoning(sr)

        return QueryResponse(
            answer="\n".join(sections),
            sources=unique_sources,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # LLM-augmented answer (OpenAI)
    # ------------------------------------------------------------------
    @staticmethod
    def _llm_answer(question: str, sr: SearchResult) -> QueryResponse:
        """Send full dataset context to OpenAI for synthesis."""
        context_blocks: list[str] = []
        sources: list[str] = []

        # KB context
        for hit in sr.kb_hits:
            context_blocks.append(
                f"### {hit.entry.topic}\n{hit.entry.answer}\n"
                f"Sources: {'; '.join(hit.entry.sources)}"
            )
            sources.extend(hit.entry.sources)

        # Disease context
        for dis in sr.disease_hits[:2]:
            context_blocks.append(
                f"### Disease: {dis['disease_name']}\n{dis['description']}\n"
                f"Mechanisms: {', '.join(dis.get('pathogenic_mechanisms', []))}\n"
                f"Cell types: {', '.join(dis.get('key_cell_types', []))}\n"
                f"Genes: {json.dumps(dis.get('associated_genes', [])[:8])}"
            )
            sources.extend(dis.get("references", []))

        # Pathway context
        for pw in sr.pathway_hits[:2]:
            context_blocks.append(
                f"### Pathway: {pw['pathway_name']} ({pw['pathway_id']})\n"
                f"{pw['description']}\n"
                f"Key nodes: {json.dumps(pw.get('key_nodes', [])[:8])}\n"
                f"Therapeutic targets: {json.dumps(pw.get('therapeutic_targets', []))}"
            )
            sources.extend(pw.get("references", []))

        # Cytokine context
        if sr.cytokine_hits:
            edges_str = "\n".join(
                f"- {e['source']} -> {e['target']} ({e['edge_type']}): {e['description']}"
                for e in sr.cytokine_hits[:8]
            )
            context_blocks.append(f"### Cytokine Network\n{edges_str}")
            for e in sr.cytokine_hits[:8]:
                if e.get("pmid"):
                    sources.append(f"PMID:{e['pmid']}")

        # Therapeutics context
        if sr.therapeutic_hits:
            rx_strs = []
            for rx in sr.therapeutic_hits[:4]:
                indications = [i["disease"] for i in rx.get("approved_indications", [])]
                rx_strs.append(
                    f"- {rx['drug_name']} ({rx['brand_name']}): {rx['drug_class']}, "
                    f"target={rx['target']}, {rx['mechanism']}. "
                    f"Indications: {', '.join(indications[:5])}"
                )
                for trial in rx.get("pivotal_trials", [])[:1]:
                    if trial.get("pmid"):
                        sources.append(f"PMID:{trial['pmid']}")
            context_blocks.append("### Therapeutics\n" + "\n".join(rx_strs))

        context = "\n\n".join(context_blocks)

        try:
            response = _openai_client.chat.completions.create(  # type: ignore[union-attr]
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Autoimmune Intelligence, a research assistant "
                            "that synthesises immunological evidence from curated "
                            "datasets. Answer using ONLY the provided context. "
                            "Structure your answer with clear sections. Cite sources "
                            "by PMID or author/journal. Be precise and evidence-based."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Context:\n{context}\n\n"
                            f"Question: {question}\n\n"
                            "Provide a detailed, structured answer covering disease "
                            "mechanisms, relevant pathways, cytokine interactions, "
                            "and available therapeutics where applicable."
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            answer = response.choices[0].message.content or ""
        except Exception:
            logger.warning("OpenAI call failed — falling back to local", exc_info=True)
            return LLMService._local_answer(question, sr)

        if not answer:
            return LLMService._local_answer(question, sr)

        # Deduplicate sources
        seen: set[str] = set()
        unique_sources = [s for s in sources if s not in seen and not seen.add(s)]  # type: ignore[func-returns-value]

        reasoning = LLMService._extract_reasoning(sr)

        return QueryResponse(answer=answer, sources=unique_sources, reasoning=reasoning)
