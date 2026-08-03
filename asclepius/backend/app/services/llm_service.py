"""LLM service — answers scientific queries using the full retrieval pipeline.

Retrieval pipeline:
  1. Hybrid BM25 + Dense → RRF → CrossEncoder (retrieval_service)
  2. Structured dataset search (query_engine.search_all)
  3. Optional live PubMed
  4. Causal knowledge graph propagation

LLM routing:
  - Primary: Anthropic 4-tier (Haiku → Sonnet → Opus) via routing.router
  - Fallback: local structured answer if ANTHROPIC_API_KEY is not set
"""

from __future__ import annotations

import json
import logging
from typing import Any, Generator, Optional

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
    "You are Asclepius, a scientific research assistant specializing in immunology, "
    "autoimmune disease, and molecular biology. You synthesize information from retrieved "
    "literature to give precise, well-cited answers. Express uncertainty when the evidence "
    "is unclear rather than speculating."
)

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
            logger.warning("Failed to decode image_base64; CLIP retrieval will be text-only")
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

            if not full_text:
                return QueryResponse(
                    answer="Image analysis returned no output.",
                    sources=sources,
                    image_analysis=None,
                )

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
    # Streaming query — yields SSE-ready dicts
    # ------------------------------------------------------------------

    def stream_query(
        self,
        question: str,
        *,
        include_pubmed: bool = False,
    ) -> Generator[dict, None, None]:
        """Yield SSE-ready event dicts for a streaming query.

        Protocol: citations → token* → done
        Matches the /query/stream SSE event types exactly.
        """
        # 1. Retrieval
        propositions = self._retrieve_propositions(question)
        sr = search_all(question)

        pubmed_articles: list[PubMedResult] = []
        if include_pubmed:
            pubmed_articles = self._fetch_pubmed(question)

        graph_context = self._get_graph_context(sr)

        # 2. Build citation data and emit immediately so the frontend can
        #    show the citations panel while the answer is still streaming.
        citation_data = [
            {
                "text": p.text,
                "score": round(p.score, 4),
                "rerank_score": round(p.rerank_score, 4),
                "type": p.metadata.get("type", "knowledge"),
                "pmid": p.metadata.get("pmid", ""),
                "source": (
                    p.metadata.get("drug_name")
                    or p.metadata.get("disease_name")
                    or p.metadata.get("pathway_name")
                    or p.metadata.get("topic")
                    or p.metadata.get("filename", "")
                ),
                "content_type": p.content_type,
                "image_hash": p.image_hash,
                "image_url": f"/images/{p.image_hash}" if p.image_hash else None,
                "page": p.metadata.get("page"),
                "table_markdown": (
                    p.metadata.get("table_markdown") if p.content_type == "table" else None
                ),
            }
            for p in propositions
        ]
        yield {"type": "citations", "data": citation_data}

        # 3. Build LLM prompt context
        context, sources = self._build_context(propositions, sr, pubmed_articles, graph_context)

        _STREAM_SYSTEM = (
            "You are Asclepius, a scientific research assistant. "
            "Answer using ONLY the provided context. Structure your response with sections "
            "appropriate to the query domain (e.g., Overview, Key Mechanisms, Pathways, "
            "Key Entities, Intervention Targets, Open Research Gaps)."
        )
        messages = [
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {question}\n\n"
                    "Provide a detailed, structured scientific answer."
                ),
            }
        ]

        # 4. Stream tokens from the LLM
        model_used = "local"
        cost = 0.0

        if settings.anthropic_api_key:
            from app.routing.router import stream_with_routing

            for item in stream_with_routing(
                messages=messages,
                system=_STREAM_SYSTEM,
                query_preview=question[:100],
            ):
                if isinstance(item, dict) and item.get("_done"):
                    model_used = item.get("model", model_used)
                    cost = item.get("cost", 0.0)
                else:
                    yield {"type": "token", "text": item}
        else:
            from app.routing.router import call_with_routing

            answer, model_used, cost = call_with_routing(
                messages=messages,
                system=_STREAM_SYSTEM,
                query_preview=question[:100],
            )
            if answer:
                for word in answer.split(" "):
                    yield {"type": "token", "text": word + " "}
            else:
                local_resp = self._local_answer(
                    question, propositions, sr, pubmed_articles, graph_context
                )
                for word in local_resp.answer.split(" "):
                    yield {"type": "token", "text": word + " "}

        yield {"type": "done", "model": model_used, "cost": cost, "sources": sources[:20]}

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
                    rerank_score=round(h.rerank_score, 6) if h.rerank_score is not None else 0.0,
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

    # Hard cap on assembled context: ~80K chars ≈ 20K tokens.
    # Sonnet has a 200K-token window; this leaves ample room for the system
    # prompt (~3K tokens) and the generated answer (~4K tokens) while
    # preventing silent overflow when a large document corpus is indexed.
    _CONTEXT_BUDGET = 80_000

    @staticmethod
    def _build_context(
        propositions: list[RetrievedPropositionSchema],
        sr: SearchResult,
        pubmed_articles: list[PubMedResult],
        graph_context: Optional[dict[str, Any]],
    ) -> tuple[str, list[str]]:
        """Build the context string and collect sources.

        Sections are added in priority order. Each section is skipped once the
        character budget is exhausted — higher-value evidence (propositions,
        KB) is always included; lower-value enrichment (graph, therapeutics)
        is dropped first under pressure.
        """
        blocks: list[str] = []
        sources: list[str] = []
        budget = LLMService._CONTEXT_BUDGET

        def try_add(block: str, block_sources: list[str] | None = None) -> bool:
            nonlocal budget
            if len(block) > budget:
                return False
            blocks.append(block)
            budget -= len(block)
            if block_sources:
                sources.extend(block_sources)
            return True

        # 1. Retrieved propositions — highest priority, always try to include.
        # Tables get rendered as full markdown; figures get caption + marker.
        if propositions:
            prop_lines: list[str] = []
            prop_sources: list[str] = []
            for p in propositions[:8]:
                ctype = p.content_type
                if ctype == "table" and p.table_markdown:
                    prop_lines.append(
                        f"- [table p.{p.metadata.get('page', '?')}]\n{p.table_markdown}"
                    )
                elif ctype == "image":
                    prop_lines.append(
                        f"- [figure p.{p.metadata.get('page', '?')}] {p.text} (figure — see caption)"
                    )
                else:
                    label = p.metadata.get("type", "knowledge")
                    prop_lines.append(f"- [{label}] {p.text}")
            for p in propositions:
                pmid = p.metadata.get("pmid", "")
                if pmid:
                    prop_sources.append(f"PMID:{pmid}")
            try_add("### Retrieved Evidence\n" + "\n".join(prop_lines), prop_sources)

        # 2. Knowledge base entries
        for hit in sr.kb_hits:
            try_add(f"### {hit.entry.topic}\n{hit.entry.answer}", list(hit.entry.sources))

        # 3. Disease context
        for dis in sr.disease_hits[:2]:
            block = (
                f"### Disease: {dis['disease_name']}\n{dis['description']}\n"
                f"Mechanisms: {', '.join(dis.get('pathogenic_mechanisms', []))}\n"
                f"Cell types: {', '.join(dis.get('key_cell_types', []))}\n"
                f"Genes: {json.dumps(dis.get('associated_genes', [])[:8])}"
            )
            try_add(block, list(dis.get("references", [])))

        # 4. PubMed literature — more abstracts than before now that we track budget
        if pubmed_articles:
            pm_lines = [
                f"- [{a.year}] {a.title} ({a.journal}). {a.abstract[:300]}"
                for a in pubmed_articles[:8]
            ]
            pm_sources = [f"PMID:{a.pmid}" for a in pubmed_articles]
            try_add("### Latest PubMed Literature\n" + "\n".join(pm_lines), pm_sources)

        # 5. Pathway context
        for pw in sr.pathway_hits[:2]:
            block = (
                f"### Pathway: {pw['pathway_name']} ({pw['pathway_id']})\n"
                f"{pw['description']}\n"
                f"Key nodes: {json.dumps(pw.get('key_nodes', [])[:6])}\n"
                f"Therapeutic targets: {json.dumps(pw.get('therapeutic_targets', []))}"
            )
            try_add(block, list(pw.get("references", [])))

        # 6. Cytokine network
        if sr.cytokine_hits:
            edges = "\n".join(
                f"- {e['source']} → {e['target']} ({e['edge_type']}): {e['description']}"
                for e in sr.cytokine_hits[:8]
            )
            cyto_sources = [f"PMID:{e['pmid']}" for e in sr.cytokine_hits[:8] if e.get("pmid")]
            try_add(f"### Cytokine Network\n{edges}", cyto_sources)

        # 7. Therapeutics
        if sr.therapeutic_hits:
            rx_lines = []
            rx_sources: list[str] = []
            for rx in sr.therapeutic_hits[:4]:
                inds = [i["disease"] for i in rx.get("approved_indications", [])]
                rx_lines.append(
                    f"- {rx['drug_name']} ({rx['brand_name']}): {rx['drug_class']}, "
                    f"target={rx['target']}, {rx['mechanism'][:120]}. "
                    f"Indications: {', '.join(inds[:4])}"
                )
                for trial in rx.get("pivotal_trials", [])[:1]:
                    if trial.get("pmid"):
                        rx_sources.append(f"PMID:{trial['pmid']}")
            try_add("### Therapeutics\n" + "\n".join(rx_lines), rx_sources)

        # 8. Causal graph — lowest priority, dropped first under budget pressure
        if graph_context and graph_context.get("causal_downstream"):
            causal = [
                f"- {item['node']}: downstream impact={item['score']}"
                for item in graph_context["causal_downstream"][:8]
            ]
            try_add("### Causal Network Analysis\n" + "\n".join(causal))

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
            key=lambda p: p.rerank_score if p.rerank_score is not None else p.score,
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
                f"<retrieved_context>\n{context}\n</retrieved_context>\n\n"
                f"<question>\n{question}\n</question>\n\n"
                "<instructions>\n"
                "Answer the question using only the retrieved context above. "
                "Cite specific sources by their PMID or source type where available. "
                "Structure your response with sections appropriate to the question domain. "
                "When retrieved figures or tables are relevant, ground specific quantitative "
                "claims in what you can see in them. If the evidence is limited or ambiguous, "
                "say so directly.\n"
                "</instructions>"
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
    # Local answer — no ANTHROPIC_API_KEY configured
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


# ---------------------------------------------------------------------------
# QueryPipeline — single entry point for all query execution paths
# ---------------------------------------------------------------------------

class QueryPipeline:
    """Single entry point for all query execution paths.

    Routes use this instead of calling LLMService internals directly.
    The pipeline owns the mode-dispatch logic (standard vs. research vs. image)
    and delegates to the appropriate LLMService method.
    """

    def __init__(self) -> None:
        self._svc = LLMService()

    def run(
        self,
        question: str,
        *,
        mode: str = "standard",
        include_pubmed: bool = False,
        verify: bool = False,
        image_base64: Optional[str] = None,
        image_media_type: str = "image/jpeg",
    ) -> QueryResponse:
        """Execute a query and return a complete response."""
        if image_base64:
            return self._svc.query_with_image(
                question,
                image_base64,
                image_media_type,
                include_pubmed=include_pubmed,
            )
        if mode == "research":
            return self._run_agent(question, verify=verify)
        return self._svc.query(question, include_pubmed=include_pubmed, verify=verify)

    def stream(
        self,
        question: str,
        *,
        include_pubmed: bool = False,
    ) -> Generator[dict, None, None]:
        """Yield SSE-ready dicts for a streaming query."""
        return self._svc.stream_query(question, include_pubmed=include_pubmed)

    def _run_agent(self, question: str, verify: bool = False) -> QueryResponse:
        """Drain the agent event stream into a non-streaming QueryResponse."""
        from app.services.agent_service import run_agent

        final_answer = ""
        image_hashes: list[str] = []
        model_used = "agent:claude-sonnet-4-6"
        cost = 0.0
        iterations = 0
        trace: list[dict] = []

        for evt in run_agent(question):
            if evt.type == "tool_call":
                trace.append({"tool": evt.data.get("tool"), "args": evt.data.get("args")})
            elif evt.type == "final":
                final_answer = evt.data.get("answer", "")
                image_hashes = list(evt.data.get("image_hashes") or [])
            elif evt.type == "done":
                iterations = evt.data.get("iterations", 0)
                cost = evt.data.get("cost_usd", 0.0)
            elif evt.type == "error":
                final_answer = final_answer or f"Agent error: {evt.data.get('message')}"

        response = QueryResponse(
            answer=final_answer or "(agent produced no output)",
            sources=[],
            model_used=model_used,
            cost_usd=cost,
            retrieved_propositions=[],
        )
        # Stash the agent trace into graph_context for the frontend to render
        response.graph_context = {"agent_trace": trace, "iterations": iterations}

        if verify and final_answer and image_hashes:
            from app.services.verification_service import verify_against_figures
            try:
                v = verify_against_figures(final_answer, image_hashes)
                response.verification = v.to_dict()
                if v.verdict in ("partially_supported", "unsupported") and v.revised_answer:
                    response.answer = v.revised_answer
            except Exception:
                logger.warning("Agent verification failed", exc_info=True)

        return response


# Module-level singleton — routes import this directly
pipeline = QueryPipeline()
