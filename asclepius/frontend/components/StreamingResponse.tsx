"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { StreamState } from "@/hooks/useStreamingQuery";
import { Logo } from "@/components/Logo";
import { modelDisplayName, pmidToUrl, PROSE_CLS } from "@/lib/utils";

interface Props {
  state: StreamState;
  onShowCitations: () => void;
}

function SourceBadge({ source }: { source: string }) {
  const pmidMatch = source.match(/PMID:\s*(\d+)/i);
  if (pmidMatch) {
    return (
      <a
        href={pmidToUrl(pmidMatch[1])}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono tabular-nums border border-green/30 bg-green-faint text-green hover:brightness-110 transition"
      >
        {source}
      </a>
    );
  }
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono border border-line bg-bg-3 text-muted">
      {source}
    </span>
  );
}

export default function StreamingResponse({ state, onShowCitations }: Props) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const { text, citations, done, isStreaming, error } = state;

  if (error) {
    return (
      <div className="rounded-md border border-risk/25 bg-risk/5 px-3 py-2 text-sm text-risk">
        {error}
      </div>
    );
  }

  if (!text && !isStreaming) return null;

  const sources = done?.sources ?? [];
  const displayedSources = sourcesExpanded ? sources : sources.slice(0, 5);

  return (
    <div className="animate-fade-in">
      {/* Assistant turn header — ⏺ marker + model + status */}
      <div className="mb-2 flex items-center gap-2 text-[11px]">
        <span className={`cc-dot ${isStreaming ? "is-active" : "is-done"}`} aria-hidden="true" />
        <Logo size={13} />
        <span className="font-sans tracking-tight text-ink-2">
          {done ? modelDisplayName(done.model) : "Asclepius"}
        </span>
        {done?.cost != null && done.cost > 0 && (
          <span className="font-mono tabular-nums text-faint">${done.cost.toFixed(5)}</span>
        )}

        {isStreaming ? (
          <span className="hx-spin ml-1" aria-label="Generating" />
        ) : done && citations.length > 0 ? (
          <span className="flex items-center gap-1 rounded-full border border-green/30 bg-green-faint px-1.5 py-0.5 text-[10px] font-medium text-green">
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Verified
          </span>
        ) : null}

        {citations.length > 0 && (
          <button
            onClick={onShowCitations}
            aria-label={`View ${citations.length} retrieved citations`}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-line px-2 py-0.5 font-mono text-[10px] text-muted transition hover:border-green/30 hover:text-ink-2"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {citations.length} sources
          </button>
        )}
      </div>

      {/* Answer body */}
      <div className="pl-[18px]">
        <div className={PROSE_CLS}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
          {isStreaming && <span className="hx-cursor" />}
        </div>

        {/* Sources */}
        {sources.length > 0 && done && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-2.5">
            {displayedSources.map((s) => (
              <SourceBadge key={s} source={s} />
            ))}
            {sources.length > 5 && (
              <button
                onClick={() => setSourcesExpanded(!sourcesExpanded)}
                className="font-mono text-[10px] text-muted transition hover:text-ink-2"
              >
                {sourcesExpanded ? "show less" : `+${sources.length - 5} more`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
