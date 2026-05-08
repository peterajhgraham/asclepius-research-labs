"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation, StreamState } from "@/hooks/useStreamingQuery";

interface Props {
  state: StreamState;
  onShowCitations: () => void;
}

function TypingCursor() {
  return (
    <span className="inline-block w-0.5 h-4 bg-accent-400 ml-0.5 animate-pulse align-text-bottom" />
  );
}

function SourceBadge({ source }: { source: string }) {
  const isPmid = source.startsWith("PMID:");
  if (isPmid) {
    const pmid = source.slice(5);
    return (
      <a
        href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono border border-accent-700/50 bg-accent-900/30 text-accent-400 hover:text-accent-300 hover:border-accent-500/50 transition"
      >
        {source}
      </a>
    );
  }
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono border border-surface-4 bg-surface-2 text-muted-light">
      {source}
    </span>
  );
}

function ModelBadge({ model, cost }: { model: string; cost: number }) {
  const shortName = model.includes("haiku")
    ? "Haiku"
    : model.includes("sonnet")
      ? "Sonnet"
      : model.includes("opus")
        ? "Opus"
        : model.split("-")[0] || model;

  return (
    <div className="flex items-center gap-1.5 text-[10px] text-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
      <span className="font-mono">{shortName}</span>
      {cost > 0 && (
        <>
          <span className="text-surface-4">·</span>
          <span className="font-mono">${cost.toFixed(5)}</span>
        </>
      )}
    </div>
  );
}

export default function StreamingResponse({ state, onShowCitations }: Props) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const { text, citations, done, isStreaming, error } = state;

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (!text && !isStreaming) return null;

  const sources = done?.sources ?? [];
  const displayedSources = sourcesExpanded ? sources : sources.slice(0, 6);

  return (
    <div className="rounded-xl border border-surface-3 bg-surface-1 overflow-hidden animate-fade-in">
      {/* Answer body */}
      <div className="px-5 py-4">
        <div className="prose prose-invert prose-sm max-w-none
          prose-headings:text-gray-100 prose-headings:font-semibold prose-headings:tracking-tight
          prose-p:text-gray-300 prose-p:leading-relaxed
          prose-strong:text-gray-100 prose-strong:font-semibold
          prose-code:text-accent-300 prose-code:bg-surface-2 prose-code:rounded prose-code:px-1 prose-code:text-xs
          prose-ul:text-gray-300 prose-li:my-0.5
          prose-h2:text-base prose-h3:text-sm prose-h4:text-xs">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {text}
          </ReactMarkdown>
          {isStreaming && <TypingCursor />}
        </div>
      </div>

      {/* Footer bar */}
      <div className="border-t border-surface-3 bg-surface-0/50 px-5 py-2.5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {/* Citation count button */}
          {citations.length > 0 && (
            <button
              onClick={onShowCitations}
              className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-muted-light hover:text-gray-200 hover:border-accent-600/50 transition"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <line x1="10" y1="9" x2="8" y2="9" />
              </svg>
              {citations.length} source{citations.length !== 1 ? "s" : ""}
            </button>
          )}

          {/* Sources inline (collapsed) */}
          {sources.length > 0 && done && (
            <div className="flex flex-wrap items-center gap-1">
              {displayedSources.map((s, i) => (
                <SourceBadge key={i} source={s} />
              ))}
              {sources.length > 6 && (
                <button
                  onClick={() => setSourcesExpanded(!sourcesExpanded)}
                  className="text-[10px] text-muted hover:text-gray-300 transition"
                >
                  {sourcesExpanded ? "less" : `+${sources.length - 6} more`}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Model + cost badge */}
        <div className="shrink-0">
          {done ? (
            <ModelBadge model={done.model} cost={done.cost} />
          ) : isStreaming ? (
            <div className="flex items-center gap-1.5 text-[10px] text-muted">
              <span className="flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-1 w-1 rounded-full bg-accent-500 animate-pulse-dot"
                    style={{ animationDelay: `${i * 0.16}s` }}
                  />
                ))}
              </span>
              <span>Generating…</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
