"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Logo } from "@/components/Logo";
import { PROSE_CLS, modelDisplayName } from "@/lib/utils";
import type { AgentState, AgentToolCall, AgentToolResult } from "@/lib/types";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge_base: "search knowledge base",
  search_pubmed: "search PubMed",
  causal_propagate: "causal propagation",
  rank_interventions: "rank interventions",
  compare_topics: "compare topics",
  final_answer: "compose answer",
};

const VERDICT_STYLE: Record<string, { label: string; cls: string }> = {
  supported: { label: "All claims supported", cls: "text-green border-green/30 bg-green-faint" },
  partially_supported: { label: "Some claims unverified", cls: "text-amber border-amber/30 bg-amber/5" },
  unsupported: { label: "Claims not supported by figures", cls: "text-risk border-risk/30 bg-risk/5" },
  no_images: { label: "No figures cited, verification skipped", cls: "text-muted border-line bg-bg-3" },
};

interface Props {
  state: AgentState;
}

/** Render a tool call's args inline, terminal-style: name(key: value, …). */
function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args);
  if (!entries.length) return "";
  return entries
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(", ")
    .slice(0, 120);
}

function ToolRow({
  call,
  result,
  active,
}: {
  call: AgentToolCall;
  result?: AgentToolResult;
  active: boolean;
}) {
  const [open, setOpen] = useState(false);
  const isFinal = call.tool === "final_answer";
  const args = formatArgs(call.args);
  const preview = result?.result_preview ?? "";
  const done = !!result || isFinal;

  return (
    <div className="cc-row py-1">
      {/* The ⏺ call line */}
      <div className="flex items-start gap-2.5">
        <span
          className={`cc-dot mt-[6px] ${
            isFinal ? "is-final" : active && !done ? "is-active" : done ? "is-done" : ""
          }`}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <p className="text-[12px] leading-relaxed text-ink-2">
            <span className="text-ink">{call.tool}</span>
            {args && <span className="text-faint">({args})</span>}
          </p>

          {/* The ⎿ result branch */}
          {isFinal ? (
            <p className="cc-branch mt-0.5 text-[11px] text-muted">composing final answer…</p>
          ) : result ? (
            <div className="cc-branch mt-0.5">
              <button
                type="button"
                onClick={() => preview.length > 140 && setOpen((v) => !v)}
                className={`text-left text-[11px] leading-relaxed text-muted ${
                  preview.length > 140 ? "hover:text-ink-2 transition" : "cursor-default"
                } ${open ? "" : "line-clamp-2"}`}
              >
                {preview || "(no output)"}
              </button>
            </div>
          ) : active ? (
            <p className="cc-branch mt-0.5 flex items-center gap-1.5 text-[11px] text-faint">
              <span className="hx-spin" /> running…
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function AgentTrace({ state }: Props) {
  const [traceOpen, setTraceOpen] = useState(true);

  // Group calls/results/thinking by planner iteration, preserving order.
  const grouped = new Map<
    number,
    { calls: AgentToolCall[]; results: AgentToolResult[]; thinking?: string }
  >();
  const ensure = (it: number) => {
    let e = grouped.get(it);
    if (!e) {
      e = { calls: [], results: [] };
      grouped.set(it, e);
    }
    return e;
  };
  for (const step of state.steps) if (step.iteration > 0) ensure(step.iteration).thinking = step.thinking;
  for (const c of state.toolCalls) ensure(c.iteration).calls.push(c);
  for (const r of state.toolResults) ensure(r.iteration).results.push(r);
  const iters = [...grouped.keys()].sort((a, b) => a - b);
  const stepCount = iters.length;

  const model = state.done?.model ?? "claude-sonnet-4-6";

  return (
    <div className="mt-3 animate-fade-in">
      {/* Assistant turn header — a single ⏺ marker, model + run meta */}
      <div className="mb-2 flex items-center gap-2 text-[11px]">
        <span className={`cc-dot ${state.isStreaming ? "is-active" : "is-done"}`} aria-hidden="true" />
        <Logo size={13} />
        <span className="font-sans tracking-tight text-ink-2">Research Agent</span>
        <span className="font-mono text-faint">· {modelDisplayName(model)}</span>
        {state.done && (
          <span className="ml-auto font-mono tabular-nums text-faint">
            {state.done.iterations} iter · ${(state.done.cost_usd ?? 0).toFixed(4)}
          </span>
        )}
        {state.isStreaming && <span className="hx-spin ml-auto" aria-label="Working" />}
      </div>

      {/* Tool transcript — flat ⏺/⎿ stream, collapsible */}
      <div className="rounded-lg border border-line bg-bg-2/60">
        <button
          type="button"
          onClick={() => setTraceOpen((v) => !v)}
          className="flex w-full items-center gap-2 px-3 py-2 font-mono text-[11px] text-muted transition hover:text-ink-2"
        >
          <svg
            width="10" height="10" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2"
            className={`transition-transform ${traceOpen ? "rotate-90" : ""}`}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          {stepCount > 0 ? `${stepCount} step${stepCount !== 1 ? "s" : ""}` : "planning"}
          <span className="text-faint">· tool calls</span>
        </button>

          {traceOpen && (
            <div className="overflow-hidden animate-fade-in">
              <div className="border-t border-line px-3 py-2">
                {iters.map((iter, idx) => {
                  const g = grouped.get(iter)!;
                  const isLastIter = idx === iters.length - 1;
                  return (
                    <div key={iter} className={idx > 0 ? "mt-1.5" : ""}>
                      {g.thinking && (
                        <p className="mb-1 pl-[18px] text-[11px] italic leading-relaxed text-muted">
                          {g.thinking}
                        </p>
                      )}
                      {g.calls.map((c, i) => {
                        const sameToolBefore = g.calls.slice(0, i).filter((x) => x.tool === c.tool).length;
                        const result = g.results.filter((r) => r.tool === c.tool)[sameToolBefore];
                        const active =
                          state.isStreaming && isLastIter && i === g.calls.length - 1;
                        return (
                          <ToolRow key={`${iter}-${i}`} call={c} result={result} active={active} />
                        );
                      })}
                    </div>
                  );
                })}

                {iters.length === 0 && state.isStreaming && (
                  <p className="flex items-center gap-2 py-1 font-mono text-[11px] text-muted">
                    <span className="hx-spin" /> planner thinking…
                  </p>
                )}
              </div>
            </div>
          )}
      </div>

      {/* Final answer */}
      {state.finalAnswer && (
        <div className="mt-3 pl-[18px]">
          <div className={PROSE_CLS}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.finalAnswer}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Verification banner */}
      {state.verification && (
        <div
          className={`mt-3 ml-[18px] rounded-md border px-3 py-2 text-[11px] ${
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
                · conf {((state.verification.confidence ?? 0) * 100).toFixed(0)}%
              </span>
            )}
          </div>
          {state.verification.notes && (
            <p className="mt-1 leading-relaxed text-current opacity-80">{state.verification.notes}</p>
          )}
        </div>
      )}

      {/* Streaming placeholder before any final answer */}
      {state.isStreaming && !state.finalAnswer && (
        <p className="mt-3 pl-[18px] text-xs text-muted">Reasoning across the corpus and live tools…</p>
      )}

      {/* Error */}
      {state.error && (
        <div className="mt-3 ml-[18px] rounded-md border border-risk/25 bg-risk/8 px-3 py-2 text-xs text-risk">
          {state.error}
        </div>
      )}
    </div>
  );
}
