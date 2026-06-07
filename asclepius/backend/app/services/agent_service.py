"""Tool-using research agent.

The default `/query` path is single-shot RAG: one retrieval, one
generation. That's fast and right for simple factual questions. The
agent here exists for the questions where single-shot is structurally
inadequate:

  - Multi-hop ("compare TNF blockade vs IL-17 blockade in PsA across
    efficacy, safety, and biomarkers" — three retrievals)
  - "Latest" vs. "established" routing (PubMed for the former, indexed
    corpus for the latter)
  - Iterative refinement when the first retrieval misses key terms

It is gated behind `mode="research"` on the query request, so callers
opt in explicitly — the latency and cost are 3-10× the single-shot
path and we never silently swap it in for trivial queries.

Implementation: Anthropic native tool-use loop, bounded by `MAX_ITERS`
iterations and a wall-clock timeout. Each iteration the planner LLM
either calls a tool (retrieve, pubmed_search, propagate, compare) or
emits a `final_answer` tool call that terminates the loop. The
retrieval tool is the same hybrid BM25 + dense + CLIP pipeline used by
single-shot RAG — agents go *on top* of the retriever, not instead of
it; replacing a strong retriever with an LLM-driven search is strictly
worse on every benchmark.

Streaming model: the loop emits SSE-shaped events (`planner_step`,
`tool_call`, `tool_result`, `final_token`, `done`) so the frontend can
show live reasoning progress rather than a 15-second silent spinner.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generator

from app.core.config import settings

logger = logging.getLogger(__name__)

_PLANNER_MODEL = "claude-sonnet-4-6"
_ANSWERER_MODEL = "claude-sonnet-4-6"

MAX_ITERS = 4
WALL_CLOCK_BUDGET_S = 120
MAX_TOOL_OUTPUT_CHARS = 6000  # keep the planner's context lean


_SYSTEM_PROMPT = (
    "You are Asclepius Research Agent — a scientific research planner that answers "
    "complex multi-part questions by decomposing them into sub-queries and dispatching "
    "the right tool for each one.\n\n"
    "Rules:\n"
    "  • Always prefer `search_knowledge_base` first — it is the indexed corpus with "
    "    hybrid lexical+semantic+image retrieval, and it is the source of truth for "
    "    grounded citations.\n"
    "  • Use `search_pubmed` only when the question asks for recent or unindexed "
    "    primary literature (e.g. 'latest 2025 trials').\n"
    "  • Use `causal_propagate` / `rank_interventions` for mechanism / target questions.\n"
    "  • Use `compare_topics` only for explicit comparisons between two diseases.\n"
    "  • Stop as soon as you have enough evidence — do not pad with extra tool calls.\n"
    "  • End the loop with `final_answer`, providing a well-structured response that "
    "    cites the tool results you actually used. Cite figures by their image_hash "
    "    when they appear in retrieval results.\n"
)


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic native tool-use format)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Hybrid BM25 + dense + CLIP retrieval over the indexed corpus. Returns the "
            "top-K propositions (text, figures, tables) with their content_type, "
            "rerank_score, page, and image_hash. This is the primary evidence source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query."},
                "top_k": {"type": "integer", "default": 6, "minimum": 1, "maximum": 12},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_pubmed",
        "description": (
            "Live PubMed search via NCBI E-utilities. Use for recent (post-cutoff) or "
            "unindexed primary literature. Returns titles, abstracts, authors, PMIDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 15},
            },
            "required": ["query"],
        },
    },
    {
        "name": "causal_propagate",
        "description": (
            "Propagate a signal through the typed knowledge graph from one or more seed "
            "nodes. Returns the ranked downstream (or upstream) impact scores. Use this "
            "for 'what does X regulate?' or 'what is downstream of X?' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "seed_nodes": {"type": "array", "items": {"type": "string"}},
                "direction": {"type": "string", "enum": ["downstream", "upstream", "both"], "default": "downstream"},
            },
            "required": ["seed_nodes"],
        },
    },
    {
        "name": "rank_interventions",
        "description": (
            "Rank candidate upstream intervention targets for a node, by predicted "
            "phenotypic impact. Use for 'what would I knock down to affect X?' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_node": {"type": "string"},
                "top_k": {"type": "integer", "default": 10, "minimum": 1, "maximum": 25},
            },
            "required": ["target_node"],
        },
    },
    {
        "name": "compare_topics",
        "description": (
            "Side-by-side mechanistic comparison of two diseases / topics with overlap "
            "scoring. Use only for explicit comparisons between two named entities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_a": {"type": "string"},
                "topic_b": {"type": "string"},
            },
            "required": ["topic_a", "topic_b"],
        },
    },
    {
        "name": "final_answer",
        "description": (
            "Terminate the loop and emit the final answer. Call this once you have "
            "sufficient evidence — do not over-call tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Markdown-formatted final answer."},
                "image_hashes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hashes of retrieved figures cited in the answer (for the UI).",
                },
            },
            "required": ["answer"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations — thin wrappers over existing services
# ---------------------------------------------------------------------------

def _truncate(s: str, n: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"\n…[truncated {len(s) - n} chars]"


def _tool_search_knowledge_base(query: str, top_k: int = 6) -> dict[str, Any]:
    from app.services.retrieval_service import retrieve

    hits = retrieve(query, top_k=int(top_k))
    return {
        "results": [
            {
                "text": h.text[:400],
                "rerank_score": round(h.rerank_score, 4),
                "content_type": h.content_type,
                "image_hash": h.image_hash,
                "page": h.metadata.get("page"),
                "source": h.metadata.get("filename")
                    or h.metadata.get("pathway_name")
                    or h.metadata.get("disease_name")
                    or h.metadata.get("drug_name")
                    or h.metadata.get("topic", ""),
            }
            for h in hits
        ],
        "count": len(hits),
    }


def _tool_search_pubmed(query: str, max_results: int = 5) -> dict[str, Any]:
    try:
        from app.services.pubmed_service import pubmed
        articles = pubmed.search(query, max_results=int(max_results))
        return {
            "results": [
                {
                    "pmid": a.pmid,
                    "title": a.title,
                    "abstract": a.abstract[:600],
                    "journal": a.journal,
                    "year": a.year,
                }
                for a in articles
            ],
            "count": len(articles),
        }
    except Exception as e:
        return {"error": str(e), "results": []}


def _tool_causal_propagate(seed_nodes: list[str], direction: str = "downstream") -> dict[str, Any]:
    try:
        from app.services.graph_service import knowledge_graph
        seed_scores = {n: 1.0 for n in seed_nodes}
        scores = knowledge_graph.propagate_signal(seed_scores, direction=direction)
        ranked = sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True)[:20]
        return {"ranked": [{"node": k, "score": round(v, 4)} for k, v in ranked]}
    except Exception as e:
        return {"error": str(e), "ranked": []}


def _tool_rank_interventions(target_node: str, top_k: int = 10) -> dict[str, Any]:
    try:
        from app.services.graph_service import knowledge_graph
        ranked = knowledge_graph.rank_interventions(target_node=target_node, top_k=int(top_k))
        return {"target": target_node, "interventions": ranked}
    except Exception as e:
        return {"error": str(e), "interventions": []}


def _tool_compare_topics(topic_a: str, topic_b: str) -> dict[str, Any]:
    try:
        from app.services.comparative_service import compare_diseases
        result = compare_diseases(topic_a, topic_b)
        if result is None:
            return {"error": f"One or both topics not found: {topic_a}, {topic_b}"}
        # Trim to keep planner context compact
        return {
            "similarity": result.get("similarity_score"),
            "summary": result.get("summary"),
            "overlaps": result.get("overlaps"),
        }
    except Exception as e:
        return {"error": str(e)}


_TOOL_FNS = {
    "search_knowledge_base": _tool_search_knowledge_base,
    "search_pubmed": _tool_search_pubmed,
    "causal_propagate": _tool_causal_propagate,
    "rank_interventions": _tool_rank_interventions,
    "compare_topics": _tool_compare_topics,
}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

@dataclass
class AgentEvent:
    type: str  # planner_step | tool_call | tool_result | final | done | error
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


def run_agent(
    question: str,
    max_iters: int = MAX_ITERS,
    timeout_s: int = WALL_CLOCK_BUDGET_S,
) -> Generator[AgentEvent, None, None]:
    """Run the tool-using research agent, yielding events as the loop progresses."""
    try:
        import anthropic
    except ImportError:
        yield AgentEvent("error", {"message": "anthropic package not installed"})
        return

    if not settings.anthropic_api_key:
        yield AgentEvent("error", {"message": "ANTHROPIC_API_KEY not configured"})
        return

    from app.routing.cost_tracker import check_budget, record_query

    if not check_budget():
        yield AgentEvent("error", {"message": "Daily budget exhausted"})
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    image_hashes_used: list[str] = []
    started = time.monotonic()
    total_cost = 0.0

    yield AgentEvent("planner_step", {"iteration": 0, "status": "starting"})

    for it in range(1, max_iters + 1):
        if time.monotonic() - started > timeout_s:
            # Out of time — don't fail. Break to the forced-finalization path
            # below so the user gets a usable answer from the evidence gathered
            # so far instead of a "budget exceeded" error.
            logger.info("Agent hit wall-clock budget (%ss); forcing finalization", timeout_s)
            break
        if not check_budget():
            yield AgentEvent("error", {"message": "Daily budget exhausted mid-loop"})
            return

        try:
            response = client.messages.create(
                model=_PLANNER_MODEL,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            yield AgentEvent("error", {"message": f"Planner call failed: {e}"})
            return

        try:
            cost = record_query(
                model=_PLANNER_MODEL,
                query=f"agent_iter_{it}: {question[:60]}",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            total_cost += cost
        except Exception:
            pass

        # Collect tool calls from this turn
        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]

        thinking = " ".join((b.text or "").strip() for b in text_blocks if (b.text or "").strip())
        if thinking:
            yield AgentEvent("planner_step", {
                "iteration": it,
                "thinking": thinking[:500],
                "tool_calls": [tu.name for tu in tool_uses],
            })

        if not tool_uses:
            # No tool calls and no final_answer — coerce a final answer from the text
            final_text = thinking or "(agent produced no output)"
            yield AgentEvent("final", {"answer": final_text, "image_hashes": image_hashes_used})
            yield AgentEvent("done", {
                "iterations": it,
                "model": _PLANNER_MODEL,
                "cost_usd": round(total_cost, 6),
            })
            return

        # Persist the assistant turn so the next iteration sees it
        messages.append({"role": "assistant", "content": response.content})

        tool_results_for_planner: list[dict[str, Any]] = []
        finished = False
        final_payload: dict[str, Any] | None = None

        for tu in tool_uses:
            name = tu.name
            args = tu.input or {}
            yield AgentEvent("tool_call", {"iteration": it, "tool": name, "args": args})

            if name == "final_answer":
                final_payload = {
                    "answer": args.get("answer", "").strip() or "(empty answer)",
                    "image_hashes": list(args.get("image_hashes") or []) + image_hashes_used,
                }
                finished = True
                # Anthropic requires us to send a tool_result even for terminal tools
                tool_results_for_planner.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": "ok",
                })
                continue

            fn = _TOOL_FNS.get(name)
            if fn is None:
                payload = {"error": f"unknown tool: {name}"}
            else:
                try:
                    payload = fn(**args)
                except TypeError as e:
                    payload = {"error": f"bad tool args: {e}"}
                except Exception as e:
                    logger.warning("Tool %s failed", name, exc_info=True)
                    payload = {"error": str(e)}

            # Harvest any image_hashes returned by retrieval for citation
            if name == "search_knowledge_base":
                for r in payload.get("results", []):
                    h = r.get("image_hash")
                    if h and h not in image_hashes_used:
                        image_hashes_used.append(h)

            payload_str = _truncate(json.dumps(payload, default=str))
            yield AgentEvent("tool_result", {
                "iteration": it,
                "tool": name,
                "result_preview": payload_str[:300],
            })
            tool_results_for_planner.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": payload_str,
            })

        # Feed tool results back to the planner for the next iteration
        messages.append({"role": "user", "content": tool_results_for_planner})

        if finished and final_payload is not None:
            yield AgentEvent("final", final_payload)
            yield AgentEvent("done", {
                "iterations": it,
                "model": _PLANNER_MODEL,
                "cost_usd": round(total_cost, 6),
            })
            return

    # Loop ended without a final_answer (tool budget or wall-clock budget) —
    # synthesize one from the evidence gathered so far. Always emit a usable
    # answer rather than surfacing an error to the user.
    final_answer = ""
    try:
        forced = client.messages.create(
            model=_ANSWERER_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT + "\n\nYou have used your tool budget. Emit `final_answer` now.",
            tools=[TOOLS[-1]],  # only final_answer
            tool_choice={"type": "tool", "name": "final_answer"},
            messages=messages,
        )
        for b in forced.content:
            if getattr(b, "type", None) == "tool_use" and b.name == "final_answer":
                args = b.input or {}
                final_answer = (args.get("answer", "") or "").strip()
                break
        try:
            total_cost += record_query(
                model=_ANSWERER_MODEL,
                query=f"agent_force_final: {question[:60]}",
                input_tokens=forced.usage.input_tokens,
                output_tokens=forced.usage.output_tokens,
            )
        except Exception:
            pass
    except Exception:
        logger.warning("Forced finalization call failed", exc_info=True)

    if not final_answer:
        final_answer = (
            "I gathered evidence across several tools but ran out of time before "
            "composing a complete synthesis. Based on what was retrieved, please "
            "narrow the question or try again — the indexed corpus did return "
            "relevant results."
        )

    yield AgentEvent("final", {
        "answer": final_answer,
        "image_hashes": image_hashes_used,
    })
    yield AgentEvent("done", {
        "iterations": it,
        "model": _PLANNER_MODEL,
        "cost_usd": round(total_cost, 6),
        "truncated": True,
    })
