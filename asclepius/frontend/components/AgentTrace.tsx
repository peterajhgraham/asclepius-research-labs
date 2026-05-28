"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";

import ClaudeBadge from "@/components/ClaudeBadge";
import { PROSE_CLS } from "@/lib/utils";
import type { AgentState } from "@/hooks/useAgentStream";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge_base: "Search knowledge base",
  search_pubmed: "Search PubMed",
  causal_propagate: "Causal propagation",
  rank_interventions: "Rank interventions",
  compare_topics: "Compare topics",
  final_answer: "Compose answer",
};

const TOOL_ICONS: Record<string, JSX.Element> = {
  search_knowledge_base: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
    </svg>
  ),
  search_pubmed: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  ),
  causal_propagate: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="6" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><path d="M7.5 7.5L16.5 16.5" />
    </svg>
  ),
  rank_interventions: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />
    </svg>
  ),
  compare_topics: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="3" y="3" width="7" height="18" /><rect x="14" y="3" width="7" height="18" />
    </svg>
  ),
  final_answer: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
};

const VERDICT_STYLE: Record<string, { label: string; cls: string }> = {
  supported: { label: "All claims supported", cls: "text-green border-green/30 bg-green-faint" },
  partially_supported: { label: "Some claims unverified", cls: "text-amber border-amber/30 bg-amber/5" },
  unsupported: { label: "Claims not supported by figures", cls: "text-risk border-risk/30 bg-risk/5" },
  no_images: { label: "No figures cited, verification skipped", cls: "text-muted border-line bg-bg-3" },
};

interface Props {
  state: AgentState;
  question?: string;
}

export default function AgentTrace({ state }: Props) {
  const [traceOpen, setTraceOpen] = useState(true);
  const groupedByIter = new Map<number, { calls: typeof state.toolCalls; results: typeof state.toolResults; step?: typeof state.steps[0] }>();
  for (const step of state.steps) {
    if (step.iteration > 0) {
      const e = groupedByIter.get(step.iteration) ?? { calls: [], results: [] };
      e.step = step;
      groupedByIter.set(step.iteration, e);
    }
  }
  for (const c of state.toolCalls) {
    const e = groupedByIter.get(c.iteration) ?? { calls: [], results: [] };
    e.calls = [...e.calls, c];
    groupedByIter.set(c.iteration, e);
  }
  for (const r of state.toolResults) {
    const e = groupedByIter.get(r.iteration) ?? { calls: [], results: [] };
    e.results = [...e.results, r];
    groupedByIter.set(r.iteration, e);
  }
  const iters = [...groupedByIter.keys()].sort((a, b) => a - b);

  return (
    <div className="mt-3 rounded-xl border border-line bg-bg-2 shadow-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <ClaudeBadge model={state.done?.model ?? "claude-sonnet-4-6"} isStreaming={state.isStreaming} />
        {state.isStreaming && (
          <span className="flex items-center gap-1.5 text-[11px] text-green font-mono">
            <span className="hx-live" />
            Planning
          </span>
        )}
        <span className="text-[11px] text-muted font-mono">research agent</span>
        {state.done && (
          <span className="text-[10px] text-muted ml-auto font-mono tabular-nums">
            {state.done.iterations} iter · ${state.done.cost_usd.toFixed(4)}
          </span>
        )}
      </div>

      {/* Trace */}
      <div className="border-b border-line">
        <button
          type="button"
          onClick={() => setTraceOpen((v) => !v)}
          className="flex w-full items-center gap-2 px-4 py-2 text-[11px] font-mono text-muted hover:bg-bg-3/40 transition"
        >
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={`transition-transform ${traceOpen ? "rotate-90" : ""}`}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          Planner trace ({iters.length} step{iters.length !== 1 ? "s" : ""})
        </button>

        <AnimatePresence initial={false}>
          {traceOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 pt-1">
                {iters.map((iter, idx) => {
                  const g = groupedByIter.get(iter)!;
                  const isLast = idx === iters.length - 1;
                  const active = state.isStreaming && isLast;
                  return (
                    <div key={iter} className="relative flex gap-3 pb-4 last:pb-0">
                      {/* Connector line */}
                      {!isLast && (
                        <span className="absolute left-[15px] top-[30px] bottom-0 w-px bg-line" aria-hidden="true" />
                      )}
                      {/* Serif numeral bullet */}
                      <span
                        className={`relative z-10 flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border bg-bg-2 font-display tabular-nums ${
                          active ? "border-green text-green" : "border-line-2 text-muted"
                        }`}
                        style={active ? { boxShadow: "var(--glow-green)", fontSize: 15 } : { fontSize: 15 }}
                      >
                        {iter}
                      </span>
                      <div className="min-w-0 flex-1 pt-1">
                        <p className="font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.14em" }}>
                          Planner · iteration {iter}
                        </p>
                        {g.step?.thinking && (
                          <p className="mt-1 text-[12px] italic text-ink-2 leading-relaxed">{g.step.thinking}</p>
                        )}
                        {g.calls.map((c, i) => {
                          const result = g.results.find((r) => r.tool === c.tool && r.iteration === c.iteration);
                          const isFinal = c.tool === "final_answer";
                          return (
                            <div key={`${iter}-${i}`} className="mt-2">
                              <span className="inline-flex items-center gap-1.5 rounded-md border border-green/30 bg-green-faint px-2 py-1 font-mono text-[11px] text-green">
                                <span className="opacity-70">→</span>
                                <span className="shrink-0">{TOOL_ICONS[c.tool] ?? TOOL_ICONS.search_knowledge_base}</span>
                                {c.tool}
                              </span>
                              {!isFinal && Object.keys(c.args).length > 0 && (
                                <p className="mt-1 text-[10px] text-muted font-mono truncate">
                                  {Object.entries(c.args)
                                    .map(([k, v]) => `${k}=${JSON.stringify(v).slice(0, 40)}`)
                                    .join(" · ")}
                                </p>
                              )}
                              {result && (
                                <div className="mt-1.5 rounded-md border border-line bg-bg-3 px-3 py-2">
                                  <p className="font-mono uppercase text-faint mb-1" style={{ fontSize: 9, letterSpacing: "0.12em" }}>result</p>
                                  <p className="text-[11px] text-ink-2 leading-relaxed line-clamp-3">{result.result_preview}</p>
                                </div>
                              )}
                              {isFinal && (
                                <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-green font-mono">
                                  <span className="hx-live" />
                                  Synthesizing final answer
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}

                {iters.length === 0 && state.isStreaming && (
                  <p className="text-[11px] text-muted text-center py-2 font-mono">Planner thinking…</p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Final answer */}
      {state.finalAnswer && (
        <div className="px-5 py-4">
          <div className={PROSE_CLS}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.finalAnswer}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Verification banner */}
      {state.verification && (
        <div
          className={`border-t border-line px-4 py-2.5 text-[11px] ${
            VERDICT_STYLE[state.verification.verdict]?.cls ?? VERDICT_STYLE.no_images.cls
          }`}
        >
          <div className="flex items-center gap-2">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="font-semibold">
              Figure-grounded verification: {VERDICT_STYLE[state.verification.verdict]?.label ?? state.verification.verdict}
            </span>
            {state.verification.images_inspected > 0 && (
              <span className="font-mono opacity-70">
                · {state.verification.images_inspected} figure{state.verification.images_inspected !== 1 ? "s" : ""} inspected
                · conf {(state.verification.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          {state.verification.notes && (
            <p className="mt-1 text-current opacity-80 leading-relaxed">
              {state.verification.notes}
            </p>
          )}
        </div>
      )}

      {/* Streaming placeholder when no final answer yet */}
      {state.isStreaming && !state.finalAnswer && (
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="hx-live" />
            <span>Agent reasoning across the indexed corpus and live tools…</span>
          </div>
        </div>
      )}

      {/* Error */}
      {state.error && (
        <div className="border-t border-risk/25 bg-risk/8 px-4 py-2.5 text-xs text-risk">
          {state.error}
        </div>
      )}
    </div>
  );
}
