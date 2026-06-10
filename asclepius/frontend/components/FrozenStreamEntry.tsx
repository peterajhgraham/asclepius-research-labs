"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Logo } from "@/components/Logo";
import type { Citation } from "@/hooks/useStreamingQuery";
import type { ConversationEntry } from "@/lib/types";
import { modelDisplayName, pmidToUrl, PROSE_CLS } from "@/lib/utils";

interface Props {
  entry: ConversationEntry;
  onShowCitations: (citations: Citation[]) => void;
}

function SourceBadge({ source }: { source: string }) {
  const pmidMatch = source.match(/PMID:\s*(\d+)/i);
  if (pmidMatch) {
    return (
      <a
        href={pmidToUrl(pmidMatch[1])}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded px-1.5 py-0.5 text-[10px] font-mono tabular-nums border border-green/30 bg-green-faint text-green hover:brightness-110 transition"
      >
        {source}
      </a>
    );
  }
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-mono border border-line bg-bg-3 text-muted">
      {source}
    </span>
  );
}

export default function FrozenStreamEntry({ entry, onShowCitations }: Props) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const sources = entry.streamedSources ?? [];
  const displayed = sourcesExpanded ? sources : sources.slice(0, 5);
  const citationCount = entry.streamedCitations?.length ?? 0;

  return (
    <div>
      {/* Assistant turn header — ⏺ marker + model */}
      <div className="mb-2 flex items-center gap-2 text-[11px]">
        <span className="cc-dot is-done" aria-hidden="true" />
        <Logo size={13} />
        <span className="font-sans tracking-tight text-ink-2">
          {entry.streamedModel ? modelDisplayName(entry.streamedModel) : "Asclepius"}
        </span>
        {entry.streamedCost != null && entry.streamedCost > 0 && (
          <span className="font-mono tabular-nums text-faint">${entry.streamedCost.toFixed(5)}</span>
        )}
        {citationCount > 0 && (
          <button
            onClick={() => onShowCitations(entry.streamedCitations!)}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-line px-2 py-0.5 font-mono text-[10px] text-muted transition hover:border-green/30 hover:text-ink-2"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {citationCount} retrieved
          </button>
        )}
      </div>

      <div className="pl-[18px]">
        <div className={PROSE_CLS}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.streamedText || ""}</ReactMarkdown>
        </div>

        {sources.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-2.5">
            {displayed.map((s) => (
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
