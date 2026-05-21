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
  supported: { label: "All claims supported", cls: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5" },
  partially_supported: { label: "Some claims unverified", cls: "text-amber-400 border-amber-500/30 bg-amber-500/5" },
  unsupported: { label: "Claims not supported by figures", cls: "text-red-400 border-red-500/30 bg-red-500/5" },
  no_images: { label: "No figures cited — verification skipped", cls: "text-muted border-surface-3 bg-surface-2" },
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
    <div className="mt-3 rounded-lg border border-surface-3 bg-surface-1 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-surface-3 px-4 py-2.5">
        <ClaudeBadge model={state.done?.model ?? "claude-sonnet-4-6"} isStreaming={state.isStreaming} />
        <span className="text-[11px] text-muted font-mono">research agent</span>
        {state.done && (
          <span className="text-[10px] text-muted ml-auto font-mono">
            {state.done.iterations} iter · ${state.done.cost_usd.toFixed(4)}
          </span>
        )}
      </div>

      {/* Trace */}
      <div className="border-b border-surface-3">
        <button
          type="button"
          onClick={() => setTraceOpen((v) => !v)}
          className="flex w-full items-center gap-2 px-4 py-2 text-[11px] font-mono text-muted hover:bg-surface-2/40 transition"
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
          Reasoning trace ({iters.length} step{iters.length !== 1 ? "s" : ""})
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
              <div className="px-4 pb-3 space-y-2">
                {iters.map((iter) => {
                  const g = groupedByIter.get(iter)!;
                  return (
                    <div
                      key={iter}
                      className="rounded-md border border-surface-3 bg-surface-0/40 px-3 py-2"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted font-mono">
                          Step {iter}
                        </span>
                      </div>
                      {g.step?.thinking && (
                        <p className="text-[11px] text-gray-300 leading-relaxed mb-2 italic">
                          {g.step.thinking}
                        </p>
                      )}
                      {g.calls.map((c, i) => {
                        const result = g.results.find((r) => r.tool === c.tool && r.iteration === c.iteration);
                        return (
                          <div key={`${iter}-${i}`} className="flex items-start gap-2 mb-1.5 last:mb-0">
                            <div className="mt-0.5 shrink-0 text-accent-400">
                              {TOOL_ICONS[c.tool] ?? TOOL_ICONS.search_knowledge_base}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-[11px] font-medium text-gray-200">
                                {TOOL_LABELS[c.tool] ?? c.tool}
                              </p>
                              {c.tool !== "final_answer" && (
                                <p className="text-[10px] text-muted font-mono truncate">
                                  {Object.entries(c.args)
                                    .map(([k, v]) => `${k}=${JSON.stringify(v).slice(0, 40)}`)
                                    .join(" · ")}
                                </p>
                              )}
                              {result && (
                                <p className="mt-0.5 text-[10px] text-muted-light leading-relaxed line-clamp-2">
                                  {result.result_preview}
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}

                {iters.length === 0 && state.isStreaming && (
                  <p className="text-[11px] text-muted text-center py-2">Planner thinking…</p>
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
          className={`border-t border-surface-3 px-4 py-2.5 text-[11px] ${
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
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent-500" />
            <span>Agent reasoning across the indexed corpus and live tools…</span>
          </div>
        </div>
      )}

      {/* Error */}
      {state.error && (
        <div className="border-t border-red-500/25 bg-red-500/8 px-4 py-2.5 text-xs text-red-400">
          {state.error}
        </div>
      )}
    </div>
  );
}
