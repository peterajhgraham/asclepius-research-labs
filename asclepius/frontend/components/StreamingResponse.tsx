"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { StreamState } from "@/hooks/useStreamingQuery";
import { modelDisplayName, pmidToUrl, PROSE_CLS } from "@/lib/utils";

interface Props {
  state: StreamState;
  onShowCitations: () => void;
}

function TypingCursor() {
  return (
    <span className="inline-block w-0.5 h-[14px] bg-accent-400 ml-0.5 animate-pulse align-text-bottom" />
  );
}

function SourceBadge({ source }: { source: string }) {
  const pmidMatch = source.match(/PMID:\s*(\d+)/i);
  if (pmidMatch) {
    return (
      <a
        href={pmidToUrl(pmidMatch[1])}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/40 bg-accent-900/20 text-accent-400 hover:text-accent-300 transition"
      >
        {source}
      </a>
    );
  }
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-3 bg-surface-2 text-muted-light">
      {source}
    </span>
  );
}

export default function StreamingResponse({ state, onShowCitations }: Props) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const { text, citations, done, isStreaming, error } = state;

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/25 bg-red-500/5 px-4 py-3 text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (!text && !isStreaming) return null;

  const sources = done?.sources ?? [];
  const displayedSources = sourcesExpanded ? sources : sources.slice(0, 5);

  return (
    <div className="rounded-lg border border-surface-3 bg-surface-1 overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-surface-3 px-4 py-2.5">
        <div className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-1 px-2 py-1 text-[11px] font-medium text-muted-light">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
          <span className="font-mono tracking-tight">
            {done ? modelDisplayName(done.model) : "Asclepius"}
          </span>
          {done?.cost != null && done.cost > 0 && (
            <span className="text-muted font-mono opacity-70 ml-0.5">${done.cost.toFixed(5)}</span>
          )}
        </div>

        {isStreaming ? (
          <span className="flex items-center gap-1.5 text-[11px] text-muted">
            <span className="flex gap-0.5">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-1 w-1 rounded-full bg-accent-500 animate-pulse-dot"
                  style={{ animationDelay: `${i * 0.16}s` }}
                />
              ))}
            </span>
            Generating…
          </span>
        ) : done && citations.length > 0 ? (
          <span className="text-[11px] text-muted">
            {citations.length} source{citations.length !== 1 ? "s" : ""} retrieved
          </span>
        ) : null}

        {citations.length > 0 && (
          <button
            onClick={onShowCitations}
            aria-label={`View ${citations.length} retrieved citations`}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-surface-3 px-2 py-1 text-[11px] text-muted hover:text-gray-300 hover:border-accent-500/30 transition"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {citations.length} retrieved
          </button>
        )}
      </div>

      {/* Answer body */}
      <div className="px-5 py-4">
        <div className={PROSE_CLS}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
          {isStreaming && <TypingCursor />}
        </div>
      </div>

      {/* Sources footer */}
      {sources.length > 0 && done && (
        <div className="border-t border-surface-3 bg-surface-0/40 px-4 py-2.5 flex flex-wrap items-center gap-1.5">
          {displayedSources.map((s) => (
            <SourceBadge key={s} source={s} />
          ))}
          {sources.length > 5 && (
            <button
              onClick={() => setSourcesExpanded(!sourcesExpanded)}
              className="text-[10px] text-muted hover:text-gray-300 transition"
            >
              {sourcesExpanded ? "show less" : `+${sources.length - 5} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
