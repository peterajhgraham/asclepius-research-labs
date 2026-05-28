"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ClaudeBadge from "@/components/ClaudeBadge";
import type { Citation } from "@/hooks/useStreamingQuery";
import type { ConversationEntry } from "@/lib/types";
import { pmidToUrl, PROSE_CLS } from "@/lib/utils";

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

  return (
    <div className="rounded-xl border border-line bg-bg-2 shadow-card overflow-hidden">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2.5">
        <ClaudeBadge
          model={entry.streamedModel}
          cost={entry.streamedCost}
          sourceCount={entry.streamedCitations?.length ?? 0}
        />
        {(entry.streamedCitations?.length ?? 0) > 0 && (
          <button
            onClick={() => onShowCitations(entry.streamedCitations!)}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-line px-2 py-1 text-[11px] text-muted hover:text-ink-2 hover:border-green/30 transition"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {entry.streamedCitations!.length} retrieved
          </button>
        )}
      </div>

      <div className="px-5 py-4">
        <div className={PROSE_CLS}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.streamedText || ""}</ReactMarkdown>
        </div>
      </div>

      {sources.length > 0 && (
        <div className="border-t border-line bg-bg/40 px-4 py-2.5 flex flex-wrap items-center gap-1.5">
          {displayed.map((s) => (
            <SourceBadge key={s} source={s} />
          ))}
          {sources.length > 5 && (
            <button
              onClick={() => setSourcesExpanded(!sourcesExpanded)}
              className="text-[10px] text-muted hover:text-ink-2 transition"
            >
              {sourcesExpanded ? "show less" : `+${sources.length - 5} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
