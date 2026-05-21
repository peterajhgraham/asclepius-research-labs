"""LLM service — answers scientific queries using the full retrieval pipeline.

Retrieval pipeline:
  1. Hybrid BM25 + Dense → RRF → CrossEncoder (retrieval_service)
  2. Structured dataset search (query_engine.search_all)
  3. Optional live PubMed
  4. Causal knowledge graph propagation

LLM routing:
  - Primary: Anthropic 4-tier (Haiku → Sonnet → Opus) via routing.router
  - Fallback: OpenAI if ANTHROPIC_API_KEY not set
  - Fallback-fallback: local structured answer if no LLM key
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.config import settings
from app.models.schema import (
    PubMedResult,
    QueryResponse,
    RetrievedPropositionSchema,
    StructuredReasoning,
)
from app.services.query_engine import SearchResult, search_all

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Asclepius, a scientific research assistant that synthesises evidence from "
    "curated knowledge bases, live PubMed literature, and structured datasets. "
    "Answer using ONLY the provided context. Structure your response with clear sections "
    "appropriate to the query domain (e.g., Overview, Key Mechanisms, Pathways, "
    "Key Entities, Therapeutic or Intervention Targets, Open Research Gaps). "
    "Cite retrieved propositions by their source type when relevant. Be precise and evidence-based."
)

# ------------------------------------------------------------------
# OpenAI fallback client (kept for backward compatibility)
# ------------------------------------------------------------------
_openai_client: Optional[object] = None

if settings.openai_api_key and not settings.anthropic_api_key:
    try:
        from openai import OpenAI  # type: ignore[import-untyped]

        _openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI fallback client initialised (model=%s)", settings.llm_model)
    except ImportError:
        logger.warning("openai package not installed")
    except Exception:
        logger.warning("Failed to initialise OpenAI client", exc_info=True)


class LLMService:
    """Handles scientific queries for the Asclepius Research Labs API."""

    def query(
        self,
        question: str,
        include_pubmed: bool = False,
        verify: bool = False,
    ) -> QueryResponse:
        logger.info("LLMService.query: %r pubmed=%s verify=%s", question, include_pubmed, verify)

        # 1. Hybrid retrieval (proposition-level)
        propositions = self._retrieve_propositions(question)

        # 2. Structured dataset search (for reasoning + graph)
        sr = search_all(question)

        # 3. Optional PubMed
        pubmed_articles: list[PubMedResult] = []
        if include_pubmed:
            pubmed_articles = self._fetch_pubmed(question)

        # 4. Graph context
        graph_context = self._get_graph_context(sr)

        if not propositions and not sr.has_results and not pubmed_articles:
            return QueryResponse(
                answer=(
                    "I could not find relevant information for your query in the indexed knowledge base. "
                    "Try rephrasing your question, being more specific about the mechanism or pathway, "
                    "or enabling Live PubMed to search primary literature directly."
                ),
                sources=[],
            )

        # 5. Route to LLM
        if settings.anthropic_api_key:
            response = self._anthropic_answer(
                question, propositions, sr, pubmed_articles, graph_context
            )
        elif _openai_client is not None:
            response = self._openai_answer(
                question, propositions, sr, pubmed_articles, graph_context
            )
        else:
            response = self._local_answer(question, propositions, sr, pubmed_articles, graph_context)

        # 6. Optional figure-grounded verification pass
        if verify and response.answer:
            self._attach_verification(response, propositions)

        return response

    @staticmethod
    def _attach_verification(
        response: QueryResponse,
        propositions: list[RetrievedPropositionSchema],
    ) -> None:
        try:
            from app.services.verification_service import verify_against_figures
            image_hashes = [p.image_hash for p in propositions if p.image_hash]
            result = verify_against_figures(response.answer, image_hashes)
            response.verification = result.to_dict()
            # If anything was actually flagged, surface the revised answer to the user
            if result.verdict in ("partially_supported", "unsupported") and result.revised_answer:
                response.answer = result.revised_answer
        except Exception:
            logger.warning("Verification pass failed", exc_info=True)

    def query_with_image(
        self,
        question: str,
        image_base64: str,
        media_type: str = "image/jpeg",
        include_pubmed: bool = False,
    ) -> QueryResponse:
        """Answer a research question about an uploaded image using Claude vision."""
        logger.info("LLMService.query_with_image: %r", question)

        # CLIP image→image retrieval: find figures in the indexed corpus
        # that look like the user's uploaded probe image.
        import base64 as _b64
        try:
            probe_bytes = _b64.b64decode(image_base64)
        except Exception:
            probe_bytes = None
        propositions = self._retrieve_propositions(question, query_image_bytes=probe_bytes)
        sr = search_all(question)
        pubmed_articles: list[PubMedResult] = []
        if include_pubmed:
            pubmed_articles = self._fetch_pubmed(question)
        graph_context = self._get_graph_context(sr)
        context, sources = self._build_context(propositions, sr, pubmed_articles, graph_context)

        if not settings.anthropic_api_key:
            return QueryResponse(
                answer="Image analysis requires an Anthropic API key with vision support.",
                sources=[],
                image_analysis=None,
            )

        _VISION_MODEL = "claude-sonnet-4-6"
        try:
            import anthropic as _anthropic
            from app.routing.cost_tracker import record_query

            client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)

            image_prompt = (
                "## Image Observations\n"
                "Describe precisely what you see: measurements, labels, bands, patterns, "
                "cell morphology, axes, trends, statistical annotations, scale bars — "
                "any visual detail relevant to the research question.\n\n"
                "## Integrated Analysis\n"
                "Using ONLY the knowledge base context above and your image observations, "
                "answer the research question with sections: Overview, Key Findings, "
                "Mechanistic Interpretation, Implications."
            )

            # Also attach top retrieved figures from the indexed corpus so
            # the model can compare the user's probe against similar
            # archival images returned by CLIP image→image retrieval.
            retrieved_vision = self._vision_blocks_from_retrieved(propositions, max_images=3)

            content_blocks: list[dict[str, Any]] = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
            ]
            if retrieved_vision:
                content_blocks.append({
                    "type": "text",
                    "text": "Similar figures retrieved from the indexed corpus (for comparison):",
                })
                content_blocks.extend(retrieved_vision)
            content_blocks.append({
                "type": "text",
                "text": (
                    f"Knowledge base context:\n{context}\n\n"
                    f"Research Question: {question}\n\n"
                    f"{image_prompt}"
                ),
            })

            response = client.messages.create(
                model=_VISION_MODEL,
                max_tokens=2500,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content_blocks}],
            )

            full_text = response.content[0].text if response.content else ""

            # Split structured response into image observations vs integrated answer
            image_analysis: Optional[str] = None
            main_answer = full_text
            if "## Integrated Analysis" in full_text:
                parts = full_text.split("## Integrated Analysis", 1)
                image_analysis = parts[0].replace("## Image Observations", "").strip() or None
                main_answer = "## Integrated Analysis\n" + parts[1].strip()
            elif "## Image Observations" in full_text:
                obs = full_text.split("## Image Observations", 1)[-1].split("\n\n")[0].strip()
                image_analysis = obs or None

            usage = response.usage
            cost = record_query(
                model=_VISION_MODEL,
                query=question[:100],
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

            return QueryResponse(
                answer=main_answer,
                sources=sources,
                reasoning=self._extract_reasoning(sr),
                pubmed_articles=pubmed_articles,
                graph_context=graph_context,
                retrieved_propositions=propositions,
                model_used=_VISION_MODEL,
                cost_usd=round(cost, 6),
                image_analysis=image_analysis,
            )

        except Exception:
            logger.exception("Image query failed")
            raise

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @staticmethod
    def _retrieve_propositions(
        question: str,
        query_image_bytes: bytes | None = None,
    ) -> list[RetrievedPropositionSchema]:
        try:
            from app.observability.metrics import observe_hits
            from app.services.retrieval_service import retrieve

            hits = retrieve(question, top_k=8, query_image_bytes=query_image_bytes)
            observe_hits(len(hits))
            return [
                RetrievedPropositionSchema(
                    text=h.text,
                    score=round(h.score, 6),
                    rerank_score=round(h.rerank_score, 6),
                    metadata=h.metadata,
                    content_type=h.content_type,
                    image_hash=h.image_hash,
                    image_url=f"/images/{h.image_hash}" if h.image_hash else None,
                    table_markdown=h.metadata.get("table_markdown") if h.content_type == "table" else None,
                )
                for h in hits
            ]
        except Exception:
            logger.debug("Retrieval failed — continuing without propositions", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # PubMed
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_pubmed(question: str) -> list[PubMedResult]:
        try:
            from app.services.pubmed_service import pubmed

            articles = pubmed.search(question, max_results=5)
            return [
                PubMedResult(
                    pmid=a.pmid,
                    title=a.title,
                    abstract=a.abstract[:400],
                    authors=a.authors[:3],
                    journal=a.journal,
                    year=a.year,
                    doi=a.doi,
                    citation=a.citation,
                )
                for a in articles
            ]
        except Exception:
            logger.warning("PubMed fetch failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Graph context
    # ------------------------------------------------------------------

    @staticmethod
    def _get_graph_context(sr: SearchResult) -> Optional[dict[str, Any]]:
        try:
            from app.services.graph_service import knowledge_graph

            seed_nodes: list[str] = []
            for edge in sr.cytokine_hits[:5]:
                for node in (edge["source"], edge["target"]):
                    if node not in seed_nodes:
                        seed_nodes.append(node)
            for pw in sr.pathway_hits[:2]:
                for node in pw.get("key_nodes", [])[:3]:
                    gene = node.get("gene", "")
                    if gene and gene not in seed_nodes:
                        seed_nodes.append(gene)

            if not seed_nodes:
                return None

            subgraph = knowledge_graph.get_subgraph(seed_nodes[:8], hops=1)
            prop_scores = knowledge_graph.propagate_signal(
                {seed_nodes[0]: 1.0}, direction="downstream"
            )
            top_downstream = sorted(
                prop_scores.items(), key=lambda x: abs(x[1]), reverse=True
            )[:10]
            subgraph["causal_downstream"] = [
                {"node": k, "score": round(v, 4)} for k, v in top_downstream
            ]
            return subgraph
        except Exception:
            logger.debug("Graph context extraction failed", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Context builder (shared by all LLM backends)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(
        propositions: list[RetrievedPropositionSchema],
        sr: SearchResult,
        pubmed_articles: list[PubMedResult],
        graph_context: Optional[dict[str, Any]],
    ) -> tuple[str, list[str]]:
        """Build the context string and collect sources."""
        blocks: list[str] = []
        sources: list[str] = []

        # Retrieved propositions (highest priority — most semantically relevant).
        # Tables get rendered as their full markdown so the LLM can read cells
        # directly; figures get their caption text plus a marker that the
        # actual image is attached as a vision block below.
        if propositions:
            prop_lines: list[str] = []
            for p in propositions[:8]:
                ctype = p.content_type
                if ctype == "table" and p.table_markdown:
                    prop_lines.append(
                        f"- [table p.{p.metadata.get('page', '?')}]\n{p.table_markdown}"
                    )
                elif ctype == "image":
                    prop_lines.append(
                        f"- [figure p.{p.metadata.get('page', '?')}] {p.text} (image attached)"
                    )
                else:
                    label = p.metadata.get("type", "knowledge")
                    prop_lines.append(f"- [{label}] {p.text}")
            blocks.append("### Retrieved Evidence\n" + "\n".join(prop_lines))
            for p in propositions:
                pmid = p.metadata.get("pmid", "")
                if pmid:
                    sources.append(f"PMID:{pmid}")

        # KB entries
        for hit in sr.kb_hits:
            blocks.append(f"### {hit.entry.topic}\n{hit.entry.answer}")
            sources.extend(hit.entry.sources)

        # Disease context
        for dis in sr.disease_hits[:2]:
            blocks.append(
                f"### Disease: {dis['disease_name']}\n{dis['description']}\n"
                f"Mechanisms: {', '.join(dis.get('pathogenic_mechanisms', []))}\n"
                f"Cell types: {', '.join(dis.get('key_cell_types', []))}\n"
                f"Genes: {json.dumps(dis.get('associated_genes', [])[:8])}"
            )
            sources.extend(dis.get("references", []))

        # Pathway context
        for pw in sr.pathway_hits[:2]:
            blocks.append(
                f"### Pathway: {pw['pathway_name']} ({pw['pathway_id']})\n"
                f"{pw['description']}\n"
                f"Key nodes: {json.dumps(pw.get('key_nodes', [])[:6])}\n"
                f"Therapeutic targets: {json.dumps(pw.get('therapeutic_targets', []))}"
            )
            sources.extend(pw.get("references", []))

        # Cytokine network
        if sr.cytokine_hits:
            edges = "\n".join(
                f"- {e['source']} → {e['target']} ({e['edge_type']}): {e['description']}"
                for e in sr.cytokine_hits[:8]
            )
            blocks.append(f"### Cytokine Network\n{edges}")
            for e in sr.cytokine_hits[:8]:
                if e.get("pmid"):
                    sources.append(f"PMID:{e['pmid']}")

        # Therapeutics
        if sr.therapeutic_hits:
            rx_lines = []
            for rx in sr.therapeutic_hits[:4]:
                inds = [i["disease"] for i in rx.get("approved_indications", [])]
                rx_lines.append(
                    f"- {rx['drug_name']} ({rx['brand_name']}): {rx['drug_class']}, "
                    f"target={rx['target']}, {rx['mechanism'][:120]}. "
                    f"Indications: {', '.join(inds[:4])}"
                )
                for trial in rx.get("pivotal_trials", [])[:1]:
                    if trial.get("pmid"):
                        sources.append(f"PMID:{trial['pmid']}")
            blocks.append("### Therapeutics\n" + "\n".join(rx_lines))

        # PubMed literature
        if pubmed_articles:
            pm_lines = [
                f"- [{a.year}] {a.title} ({a.journal}). {a.abstract[:200]}"
                for a in pubmed_articles[:5]
            ]
            blocks.append("### Latest PubMed Literature\n" + "\n".join(pm_lines))
            for a in pubmed_articles:
                sources.append(f"PMID:{a.pmid}")

        # Causal graph
        if graph_context and graph_context.get("causal_downstream"):
            causal = [
                f"- {item['node']}: downstream impact={item['score']}"
                for item in graph_context["causal_downstream"][:8]
            ]
            blocks.append("### Causal Network Analysis\n" + "\n".join(causal))

        # Deduplicate sources
        seen: set[str] = set()
        unique_sources = [s for s in sources if s not in seen and not seen.add(s)]  # type: ignore[func-returns-value]

        return "\n\n".join(blocks), unique_sources

    # ------------------------------------------------------------------
    # Structured reasoning extractor (unchanged from original)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_reasoning(sr: SearchResult) -> StructuredReasoning:
        entities: list[str] = []
        mechanisms: list[str] = []
        pathways: list[str] = []
        targets: list[str] = []
        genes: list[str] = []
        open_qs: list[str] = []
        summary_parts: list[str] = []
        topic_ctx = ""

        if sr.disease_hits:
            dis = sr.disease_hits[0]
            topic_ctx = dis["description"]
            if dis.get("prevalence"):
                topic_ctx += f" Prevalence: {dis['prevalence']}."
            entities.extend(dis.get("key_cell_types", []))
            for mech in dis.get("pathogenic_mechanisms", []):
                summary_parts.append(mech)
            for g in dis.get("associated_genes", [])[:8]:
                label = g["gene"]
                if g.get("description"):
                    label += f" — {g['description']}"
                genes.append(label)
            for rx in dis.get("approved_therapies", []):
                targets.append(f"{rx['drug']} ({rx['class']})")

        for pw in sr.pathway_hits[:3]:
            pathways.append(f"{pw['pathway_name']} — {pw['description'][:120]}")
            for tgt in pw.get("therapeutic_targets", [])[:3]:
                entry = f"{tgt.get('drug', '?')} targeting {tgt.get('target', '?')}"
                if tgt.get("mechanism"):
                    entry += f" ({tgt['mechanism']})"
                if entry not in targets:
                    targets.append(entry)

        seen_mechanisms: set[str] = set()
        for edge in sr.cytokine_hits[:10]:
            src = edge["source"]
            if src not in seen_mechanisms:
                seen_mechanisms.add(src)
                mechanisms.append(f"{src} — {edge['description'][:100]}")

        for rx in sr.therapeutic_hits[:5]:
            indications = [i["disease"] for i in rx.get("approved_indications", [])[:3]]
            entry = (
                f"{rx['drug_name']} ({rx['brand_name']}) — {rx['drug_class']}, "
                f"targets {rx['target']}. {rx['mechanism'][:100]}. "
                f"Approved for: {', '.join(indications)}"
            )
            if entry not in targets:
                targets.append(entry)

        if sr.kb_hits:
            summary_parts.insert(0, sr.kb_hits[0].entry.answer)

        if sr.disease_hits:
            dis = sr.disease_hits[0]
            name = dis["disease_name"]
            open_qs.append(f"What are the primary drivers of {name} pathogenesis?")
            if dis.get("associated_genes"):
                top_gene = dis["associated_genes"][0]["gene"]
                open_qs.append(
                    f"How do {top_gene} variants contribute to {name} susceptibility?"
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

        return StructuredReasoning(
            summary="\n\n".join(summary_parts),
            key_entities=entities,
            key_mechanisms=mechanisms,
            pathways=pathways,
            therapeutic_targets=targets,
            open_questions=open_qs,
            genes=genes,
            topic_context=topic_ctx,
        )

    # ------------------------------------------------------------------
    # Multimodal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _vision_blocks_from_retrieved(
        propositions: list[RetrievedPropositionSchema],
        max_images: int = 4,
    ) -> list[dict[str, Any]]:
        """Build Anthropic vision content blocks for retrieved figures/tables.

        Only the top-N image/table propositions (by rerank_score) are
        attached so we stay well under the per-request size budget — each
        image costs ~250-1000 input tokens of vision encoding.
        """
        import base64
        from app.storage.image_store import get_image_store

        store = get_image_store()
        ranked = sorted(
            [p for p in propositions if p.image_hash and p.content_type in ("image", "table")],
            key=lambda p: p.rerank_score if p.rerank_score else p.score,
            reverse=True,
        )
        blocks: list[dict[str, Any]] = []
        for p in ranked[:max_images]:
            loaded = store.read(p.image_hash or "")
            if loaded is None:
                continue
            img_bytes, media_type = loaded
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(img_bytes).decode(),
                },
            })
        return blocks

    # ------------------------------------------------------------------
    # Anthropic answer (primary)
    # ------------------------------------------------------------------

    @staticmethod
    def _anthropic_answer(
        question: str,
        propositions: list[RetrievedPropositionSchema],
        sr: SearchResult,
        pubmed_articles: list[PubMedResult],
        graph_context: Optional[dict[str, Any]],
    ) -> QueryResponse:
        from app.routing.router import call_with_routing

        context, sources = LLMService._build_context(
            propositions, sr, pubmed_articles, graph_context
        )

        # If retrieval surfaced relevant figures or tables, attach them as
        # native vision content so the model can read what the captions only
        # gestured at — band intensities, axis values, table cell colors, etc.
        vision_blocks = LLMService._vision_blocks_from_retrieved(propositions)

        text_block = {
            "type": "text",
            "text": (
                f"Context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Provide a detailed, structured answer with sections appropriate to the query domain. "
                "When the retrieved figures or tables are relevant, ground specific quantitative claims "
                "in what you can see in them."
            ),
        }

        if vision_blocks:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Retrieved figures and tables from the indexed corpus:"},
                    *vision_blocks,
                    text_block,
                ],
            }]
        else:
            messages = [{"role": "user", "content": text_block["text"]}]

        answer, model_used, cost = call_with_routing(
            messages=messages,
            system=_SYSTEM_PROMPT,
            query_preview=question[:100],
        )

        if not answer:
            return LLMService._local_answer(
                question, propositions, sr, pubmed_articles, graph_context
            )

        return QueryResponse(
            answer=answer,
            sources=sources,
            reasoning=LLMService._extract_reasoning(sr),
            pubmed_articles=pubmed_articles,
            graph_context=graph_context,
            retrieved_propositions=propositions,
            model_used=model_used,
            cost_usd=round(cost, 6),
        )

    # ------------------------------------------------------------------
    # OpenAI fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _openai_answer(
        question: str,
        propositions: list[RetrievedPropositionSchema],
        sr: SearchResult,
        pubmed_articles: list[PubMedResult],
        graph_context: Optional[dict[str, Any]],
    ) -> QueryResponse:
        context, sources = LLMService._build_context(
            propositions, sr, pubmed_articles, graph_context
        )
        try:
            response = _openai_client.chat.completions.create(  # type: ignore[union-attr]
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Context:\n{context}\n\nQuestion: {question}\n\n"
                            "Provide a detailed structured scientific answer."
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            answer = response.choices[0].message.content or ""
        except Exception:
            logger.warning("OpenAI call failed — falling back to local", exc_info=True)
            return LLMService._local_answer(
                question, propositions, sr, pubmed_articles, graph_context
            )

        if not answer:
            return LLMService._local_answer(
                question, propositions, sr, pubmed_articles, graph_context
            )

        return QueryResponse(
            answer=answer,
            sources=sources,
            reasoning=LLMService._extract_reasoning(sr),
            pubmed_articles=pubmed_articles,
            graph_context=graph_context,
            retrieved_propositions=propositions,
            model_used=settings.llm_model,
        )

    # ------------------------------------------------------------------
    # Local answer — no LLM key required
    # ------------------------------------------------------------------

    @staticmethod
    def _local_answer(
        question: str,
        propositions: list[RetrievedPropositionSchema],
        sr: SearchResult,
        pubmed_articles: list[PubMedResult],
        graph_context: Optional[dict[str, Any]],
    ) -> QueryResponse:
        sections: list[str] = []
        sources: list[str] = []

        # Retrieved propositions
        if propositions:
            lines = [f"- {p.text}" for p in propositions[:6]]
            sections.append("**Retrieved Evidence:**\n" + "\n".join(lines))
            for p in propositions:
                if p.metadata.get("pmid"):
                    sources.append(f"PMID:{p.metadata['pmid']}")

        # KB narrative
        if sr.kb_hits:
            primary = sr.kb_hits[0].entry
            sections.append(primary.answer)
            for hit in sr.kb_hits:
                sources.extend(hit.entry.sources)
            for hit in sr.kb_hits[1:]:
                if hit.score > 0.1:
                    sections.append(f"\n**Related — {hit.entry.topic}:**\n{hit.entry.answer}")

        # Disease context
        if sr.disease_hits:
            dis = sr.disease_hits[0]
            parts = [f"\n**Disease — {dis['disease_name']}:**", dis["description"]]
            if dis.get("prevalence"):
                parts.append(f"Prevalence: {dis['prevalence']}.")
            sections.append("\n".join(parts))
            sources.extend(dis.get("references", []))

        # Pathway context
        if sr.pathway_hits:
            pw = sr.pathway_hits[0]
            sections.append(
                f"\n**Pathway — {pw['pathway_name']} ({pw['pathway_id']}):**\n{pw['description']}"
            )
            sources.extend(pw.get("references", []))

        # Cytokine interactions
        if sr.cytokine_hits:
            lines = ["\n**Cytokine interactions:**"]
            for edge in sr.cytokine_hits[:6]:
                lines.append(
                    f"{edge['source']} → {edge['target']} ({edge['edge_type']}) — {edge['description']}"
                )
                if edge.get("pmid"):
                    sources.append(f"PMID:{edge['pmid']}")
            sections.append("\n".join(lines))

        # Therapeutics
        if sr.therapeutic_hits:
            lines = ["\n**Therapeutics:**"]
            for rx in sr.therapeutic_hits[:4]:
                inds = [i["disease"] for i in rx.get("approved_indications", [])]
                lines.append(
                    f"{rx['drug_name']} ({rx['brand_name']}) — {rx['drug_class']}. "
                    f"Target: {rx['target']}. Approved for: {', '.join(inds[:4])}."
                )
                for trial in rx.get("pivotal_trials", [])[:1]:
                    if trial.get("pmid"):
                        sources.append(f"PMID:{trial['pmid']}")
            sections.append("\n".join(lines))

        # PubMed
        if pubmed_articles:
            lines = ["\n**Latest PubMed:**"]
            for a in pubmed_articles[:5]:
                lines.append(f"- {a.citation}")
                sources.append(f"PMID:{a.pmid}")
            sections.append("\n".join(lines))

        # Causal graph
        if graph_context and graph_context.get("causal_downstream"):
            lines = ["\n**Causal network:**"]
            for item in graph_context["causal_downstream"][:5]:
                lines.append(f"- {item['node']}: downstream impact {item['score']}")
            sections.append("\n".join(lines))

        seen: set[str] = set()
        unique_sources = [s for s in sources if s not in seen and not seen.add(s)]  # type: ignore[func-returns-value]

        return QueryResponse(
            answer="\n".join(sections),
            sources=unique_sources,
            reasoning=LLMService._extract_reasoning(sr),
            pubmed_articles=pubmed_articles,
            graph_context=graph_context,
            retrieved_propositions=propositions,
        )
