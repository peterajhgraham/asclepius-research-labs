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

import concurrent.futures
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generator

from app.core.config import settings

logger = logging.getLogger(__name__)

_PLANNER_MODEL = "claude-sonnet-4-6"
_ANSWERER_MODEL = "claude-sonnet-4-6"

# Budgets. The backend is a long-lived service (uvicorn on Railway), not a
# serverless function, and the SSE route emits a 15s heartbeat keepalive, so an
# in-flight run is *not* torn down by an idle-connection timeout. The real
# constraints are therefore (a) never letting a single model/tool call stall the
# stream unboundedly, and (b) keeping total latency within a researcher's
# patience. We still bound every call individually and reserve time at the end
# for the closing synthesis so a usable answer is always emitted — but the
# overall budget is generous enough for genuine multi-hop research instead of
# cutting the agent off after three turns.
#
# Two things blow the budget when left unbounded, and earlier fixes missed both:
#   1. The Anthropic SDK defaults to a 600s per-request timeout with retries —
#      one slow or overloaded call can stall the stream for minutes.
#   2. Tool calls (notably PubMed, which retries NCBI requests, and a cold-start
#      retriever build) are unbounded; a single call can block for a minute+.
# We bound both, and — crucially — run the tool calls a planner emits in one
# turn *concurrently*, so a turn that fans out to four retrievals costs one tool
# timeout, not four.
MAX_ITERS = 6
WALL_CLOCK_BUDGET_S = 180      # hard ceiling for the whole run
FINALIZE_RESERVE_S = 35        # time held back for the closing synthesis call
PER_CALL_TIMEOUT_S = 45.0      # per-request timeout on each Anthropic call
TOOL_TIMEOUT_S = 25.0          # hard cap on any single tool call (cold retriever, PubMed)
WARMUP_TIMEOUT_S = 45.0        # bounded wait for the retriever to finish building
MAX_ANSWER_TOKENS = 2048      # closing-answer size; fits inside PER_CALL_TIMEOUT_S
MAX_TOOL_OUTPUT_CHARS = 6000  # keep the planner's context lean


# Tools run in a side thread pool so a slow call (e.g. a stalled PubMed
# request) can be abandoned without blocking the agent past its deadline.
_TOOL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=16, thread_name_prefix="agent-tool"
)


def _execute_tool(fn, args: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Run a tool function with a hard wall-clock timeout.

    The call is dispatched to a worker thread and abandoned if it exceeds
    ``timeout_s`` (raising ``concurrent.futures.TimeoutError``); the orphaned
    thread finishes on its own without holding up the SSE stream. Exceptions
    raised by the tool itself propagate normally to the caller.
    """
    future = _TOOL_EXECUTOR.submit(lambda: fn(**args))
    return future.result(timeout=timeout_s)


def _ensure_retriever_ready(timeout_s: float = WARMUP_TIMEOUT_S) -> bool:
    """Block until the retrieval pipeline has finished building, bounded by
    ``timeout_s``.

    The pipeline builds lazily on first use (loading sentence-transformers +
    FAISS and indexing the corpus), which can take far longer than a single
    tool-call timeout on a cold instance. Without this gate, the *first*
    iteration's retrievals each trip the per-tool timeout while the build is
    still in flight, wasting the early budget on calls that return nothing.

    Paying the cold-start cost once, here, means every in-loop retrieval is
    fast. Returns True if the pipeline is ready, False if it didn't build in
    time (in which case retrieval tools degrade to empty results rather than
    blocking). Cheap and idempotent once warm.
    """
    try:
        from app.services.retrieval_service import get_pipeline

        future = _TOOL_EXECUTOR.submit(get_pipeline)
        pipeline = future.result(timeout=timeout_s)
        return bool(getattr(pipeline, "is_ready", False))
    except concurrent.futures.TimeoutError:
        logger.warning("Retriever warm-up exceeded %ss; proceeding uninitialized", timeout_s)
        return False
    except Exception:
        logger.warning("Retriever warm-up failed", exc_info=True)
        return False


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
    "  • Vary your queries — if a result is marked as already retrieved, re-target "
    "    rather than repeating it. Stop as soon as you have enough evidence; do not "
    "    pad with extra tool calls.\n"
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


def _fingerprint(text: str) -> str:
    """Stable fingerprint of a proposition's text for cross-call dedup.

    Lowercased, whitespace-collapsed, and capped — two retrieval hits whose
    leading text is identical (the common case when the same dominant document
    keeps resurfacing for different queries) collapse to the same key.
    """
    norm = " ".join((text or "").lower().split())[:200]
    return norm


def _dedup_search_results(
    payload: dict[str, Any], seen: set[str]
) -> dict[str, Any]:
    """Suppress knowledge-base hits already returned earlier this run.

    The planner often fans out several overlapping queries; without this, the
    same dominant document comes back on each one, padding the planner's context
    and tricking it into thinking it has more evidence than it does.

    The earlier version *dropped* every repeat — but on a small corpus several
    distinct sub-queries (efficacy, safety, biomarkers) legitimately surface the
    same top documents, so whole turns came back empty and the planner (and the
    closing synthesis, which reads the transcript) were left with nothing to work
    with. That is the failure mode this guards against now: we prefer the fresh
    hits, but when *every* hit is a repeat we keep the top few rather than
    returning an empty set, annotating them so the planner still knows to vary
    its query or finalize.
    """
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return payload
    fresh: list[dict[str, Any]] = []
    repeats: list[dict[str, Any]] = []
    for r in results:
        fp = _fingerprint(r.get("text", ""))
        if fp and fp in seen:
            repeats.append(r)
            continue
        if fp:
            seen.add(fp)
        fresh.append(r)

    if fresh:
        payload["results"] = fresh
        payload["count"] = len(fresh)
        if repeats:
            payload["note"] = (
                f"{len(repeats)} result(s) omitted — already returned by an earlier "
                "search this run. Broaden or re-target the query for new evidence, or "
                "call final_answer if you have enough."
            )
        return payload

    # Everything overlapped prior retrievals. Keep the top hits anyway so the
    # turn isn't blind — but flag the overlap so the planner re-targets or wraps up.
    kept = repeats[: min(3, len(repeats))]
    payload["results"] = kept
    payload["count"] = len(kept)
    payload["note"] = (
        f"All {len(repeats)} hit(s) overlap evidence already retrieved this run — "
        "shown again for grounding. Vary the query for new evidence, or call "
        "final_answer if you have enough."
    )
    return payload


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
        # Distinguish a genuine "no hits" from "couldn't reach NCBI" — otherwise
        # the planner reads a transport failure as an authoritative empty result
        # and wrongly concludes the literature has nothing to say.
        if not articles and pubmed.last_error:
            return {
                "error": pubmed.last_error,
                "results": [],
                "count": 0,
                "note": (
                    "PubMed was unreachable — this is an infrastructure error, not "
                    "an empty result. Rely on search_knowledge_base for grounding."
                ),
            }
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

        # The planner names seeds the way a paper does ("TNF-alpha", "IL-17A"),
        # but the graph keys nodes by HGNC symbol ("TNF", "IL17A"). Resolve each
        # seed to its canonical node first — otherwise propagation starts from a
        # node with no outgoing edges and returns nothing but the seeds back.
        seed_scores: dict[str, float] = {}
        resolved: dict[str, str] = {}
        unresolved: list[str] = []
        for n in seed_nodes:
            node_id = knowledge_graph.resolve_node_id(n)
            if node_id is None:
                unresolved.append(n)
            else:
                resolved[n] = node_id
                seed_scores[node_id] = 1.0

        if not seed_scores:
            return {
                "error": f"No seed nodes matched the knowledge graph: {seed_nodes}",
                "ranked": [],
                "unresolved": unresolved,
            }

        scores = knowledge_graph.propagate_signal(seed_scores, direction=direction)
        # Rank the *downstream impact* — exclude the seeds themselves, which
        # trivially carry the strongest signal and aren't what the caller asked for.
        ranked = sorted(
            ((k, v) for k, v in scores.items() if k not in seed_scores),
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:20]
        out: dict[str, Any] = {
            "seeds_used": resolved,
            "ranked": [{"node": k, "score": round(v, 4)} for k, v in ranked],
        }
        if unresolved:
            out["unresolved"] = unresolved
        return out
    except Exception as e:
        logger.warning("causal_propagate failed for seeds=%s", seed_nodes, exc_info=True)
        return {"error": f"{type(e).__name__}: {e}", "ranked": []}


def _tool_rank_interventions(target_node: str, top_k: int = 10) -> dict[str, Any]:
    try:
        from app.services.graph_service import knowledge_graph
        ranked = knowledge_graph.rank_interventions(target_node=target_node, top_k=int(top_k))
        return {"target": target_node, "interventions": ranked}
    except Exception as e:
        logger.warning("rank_interventions failed for target=%s", target_node, exc_info=True)
        return {"error": f"{type(e).__name__}: {e}", "interventions": []}


def _tool_compare_topics(topic_a: str, topic_b: str) -> dict[str, Any]:
    try:
        from app.services.comparative_service import (
            compare_diseases,
            list_available_diseases,
        )
        result = compare_diseases(topic_a, topic_b)
        if result is None:
            # This tool compares two *diseases* in the curated dataset. The
            # planner sometimes hands it drug-class phrases ("TNF blockade in
            # psoriatic arthritis") instead — tell it which names exist and what
            # this tool is for so it can re-target or fall back to
            # search_knowledge_base rather than dead-ending on "not found".
            return {
                "error": f"One or both topics not found: {topic_a}, {topic_b}",
                "available_diseases": list_available_diseases(),
                "hint": (
                    "compare_topics only compares two diseases from the list above. "
                    "For a within-disease comparison (e.g. two drug classes), use "
                    "search_knowledge_base instead."
                ),
            }
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

    # Bound every call and disable the SDK's long exponential-backoff retries:
    # the defaults (600s timeout, retries) can silently block for minutes
    # mid-stream until an upstream proxy drops the connection.
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=PER_CALL_TIMEOUT_S,
        max_retries=1,
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    image_hashes_used: list[str] = []
    # Fingerprints of knowledge-base hits already shown to the planner, so a
    # later overlapping query doesn't re-feed the same documents.
    seen_fingerprints: set[str] = set()
    started = time.monotonic()
    total_cost = 0.0

    # Stop planning early enough to leave room for the closing synthesis call,
    # so the agent always emits a `final` answer before the request deadline.
    plan_deadline = max(1, timeout_s - FINALIZE_RESERVE_S)

    yield AgentEvent("planner_step", {"iteration": 0, "status": "starting"})

    # Pay any cold-start retriever build cost up front, outside the per-tool
    # timeout, so the first iteration's retrievals don't all trip the cap while
    # the index is still building. The wait is bounded and counts against the
    # planning budget; if it doesn't finish in time the loop still runs (tools
    # degrade gracefully) rather than hanging.
    warm_budget = min(WARMUP_TIMEOUT_S, max(1.0, plan_deadline - (time.monotonic() - started)))
    if not _ensure_retriever_ready(warm_budget):
        yield AgentEvent("planner_step", {
            "iteration": 0,
            "status": "knowledge base still warming — proceeding",
        })

    for it in range(1, max_iters + 1):
        if time.monotonic() - started > plan_deadline:
            # Out of planning time — don't fail. Break to the forced-finalization
            # path below so the user gets a usable answer from the evidence
            # gathered so far instead of a "budget exceeded" error.
            logger.info("Agent hit planning budget (%ss); forcing finalization", plan_deadline)
            break
        if not check_budget():
            yield AgentEvent("error", {"message": "Daily budget exhausted mid-loop"})
            return

        try:
            response = client.messages.create(
                model=_PLANNER_MODEL,
                max_tokens=MAX_ANSWER_TOKENS,
                system=_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            # A transient or slow planner call shouldn't sink the whole run.
            # Once some evidence has been gathered, fall through to forced
            # finalization; only error out if the very first call fails.
            if it == 1:
                yield AgentEvent("error", {"message": f"Planner call failed: {e}"})
                return
            logger.warning("Planner call failed on iter %s; forcing finalization", it, exc_info=True)
            break

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

        # Announce every call first (in the planner's emitted order) so the UI
        # shows the full fan-out, then dispatch the real tools concurrently.
        for tu in tool_uses:
            yield AgentEvent("tool_call", {"iteration": it, "tool": tu.name, "args": tu.input or {}})

        # Kick off all non-terminal tool calls at once. A turn that fans out to
        # several retrievals then costs a single tool timeout instead of the sum
        # of them — the difference between staying inside budget and blowing it.
        running: dict[str, concurrent.futures.Future] = {}
        for tu in tool_uses:
            if tu.name == "final_answer":
                args = tu.input or {}
                final_payload = {
                    "answer": args.get("answer", "").strip() or "(empty answer)",
                    "image_hashes": list(args.get("image_hashes") or []) + image_hashes_used,
                }
                finished = True
                continue
            fn = _TOOL_FNS.get(tu.name)
            if fn is not None:
                running[tu.id] = _TOOL_EXECUTOR.submit(lambda fn=fn, a=tu.input or {}: fn(**a))

        # Collect results in the planner's original order. Each call gets up to
        # TOOL_TIMEOUT_S, but since they run in parallel the batch wall-time is
        # bounded by the slowest call, not their sum.
        batch_deadline = time.monotonic() + TOOL_TIMEOUT_S
        for tu in tool_uses:
            name = tu.name
            if name == "final_answer":
                # Anthropic requires a tool_result for every tool_use block.
                tool_results_for_planner.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": "ok",
                })
                continue

            fut = running.get(tu.id)
            if fut is None:
                payload = {"error": f"unknown tool: {name}"}
            else:
                remaining = max(0.0, batch_deadline - time.monotonic())
                try:
                    payload = fut.result(timeout=remaining)
                except concurrent.futures.TimeoutError:
                    logger.warning("Tool %s timed out after %ss", name, TOOL_TIMEOUT_S)
                    payload = {"error": f"{name} timed out after {TOOL_TIMEOUT_S:g}s"}
                except TypeError as e:
                    payload = {"error": f"bad tool args: {e}"}
                except Exception as e:
                    logger.warning("Tool %s failed", name, exc_info=True)
                    payload = {"error": str(e)}

            # Drop documents already retrieved this run, then harvest image
            # hashes from what's genuinely new for citation.
            if name == "search_knowledge_base" and isinstance(payload, dict):
                payload = _dedup_search_results(payload, seen_fingerprints)
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
            max_tokens=MAX_ANSWER_TOKENS,
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
