"use client";

import { useEffect, useRef } from "react";
import type { Citation } from "@/hooks/useStreamingQuery";

const TYPE_COLORS: Record<string, string> = {
  cytokine_edge: "text-cytokine border-cytokine/30 bg-cytokine/5",
  pathway:       "text-pathway border-pathway/30 bg-pathway/5",
  pathway_node:  "text-pathway border-pathway/20 bg-pathway/5",
  disease:       "text-accent-400 border-accent-400/30 bg-accent-400/5",
  disease_gene:  "text-gene border-gene/30 bg-gene/5",
  therapeutic:   "text-target border-target/30 bg-target/5",
  kb_entry:      "text-cell border-cell/30 bg-cell/5",
  default:       "text-muted-light border-surface-4 bg-surface-2",
};

const TYPE_LABELS: Record<string, string> = {
  cytokine_edge: "Cytokine",
  pathway:       "Pathway",
  pathway_node:  "Pathway Node",
  disease:       "Disease",
  disease_gene:  "Disease Gene",
  therapeutic:   "Therapeutic",
  kb_entry:      "Knowledge Base",
  figure:        "Figure",
  table:         "Table",
};

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.max(score * 100, 0), 100);
  return (
    <div className="h-1 w-full rounded-full bg-surface-3 overflow-hidden">
      <div
        className="h-full rounded-full bg-accent-500 transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

interface Props {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
}

export default function CitationPanel({ citations, isOpen, onClose }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop (mobile) */}
      <div
        className="fixed inset-0 z-30 bg-black/40 lg:hidden"
        onClick={onClose}
      />

      {/* Panel */}
      <aside
        ref={panelRef}
        className="fixed right-0 top-0 z-40 h-full w-80 border-l border-surface-3 bg-surface-1 shadow-2xl animate-slide-in flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-3 px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-100">Retrieved Evidence</h3>
            <p className="text-[10px] text-muted mt-0.5">
              {citations.length} proposition{citations.length !== 1 ? "s" : ""} · multimodal hybrid
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Citations list */}
        <div className="flex-1 overflow-y-auto py-3 px-3 space-y-2">
          {citations.length === 0 ? (
            <p className="text-xs text-muted text-center py-8">No citations retrieved.</p>
          ) : (
            citations.map((c, i) => {
              const isImage = c.content_type === "image" && c.image_hash;
              const isTable = c.content_type === "table";
              const effectiveType = isImage ? "figure" : isTable ? "table" : c.type;
              const colorClass = TYPE_COLORS[effectiveType] ?? TYPE_COLORS.default;
              const label = TYPE_LABELS[effectiveType] ?? effectiveType;
              const relevancePct = c.rerank_score > 0
                ? c.rerank_score
                : c.score * 15;

              return (
                <div
                  key={`${i}-${c.image_hash || c.pmid || c.text.slice(0, 20)}`}
                  className={`rounded-lg border p-3 transition ${colorClass}`}
                >
                  {/* Type badge + rank */}
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
                      {label}{c.page ? ` · p.${c.page}` : ""}
                    </span>
                    <span className="text-[10px] font-mono text-muted">
                      #{i + 1}
                    </span>
                  </div>

                  {/* Source name if available */}
                  {c.source && (
                    <p className="text-[11px] font-medium text-current opacity-70 mb-1 truncate">
                      {c.source}
                    </p>
                  )}

                  {/* Figure thumbnail */}
                  {isImage && (
                    <a
                      href={`/api/images/${c.image_hash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block mb-2 overflow-hidden rounded border border-surface-3 bg-surface-2 hover:opacity-90 transition"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`/api/images/${c.image_hash}`}
                        alt={c.text.slice(0, 80)}
                        loading="lazy"
                        className="w-full h-32 object-contain bg-black/20"
                      />
                    </a>
                  )}

                  {/* Table markdown rendering */}
                  {isTable && c.table_markdown && (
                    <pre className="mb-2 max-h-40 overflow-auto rounded border border-surface-3 bg-surface-2 p-2 text-[10px] font-mono text-gray-300 whitespace-pre">
                      {c.table_markdown}
                    </pre>
                  )}

                  {/* Proposition text */}
                  <p className="text-xs text-gray-300 leading-relaxed line-clamp-4">
                    {c.text}
                  </p>

                  {/* Relevance bar */}
                  <div className="mt-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-muted">Relevance</span>
                      <span className="text-[10px] font-mono text-muted">
                        {(relevancePct * 100).toFixed(0)}%
                      </span>
                    </div>
                    <ScoreBar score={relevancePct} />
                  </div>

                  {/* PMID link */}
                  {c.pmid && (
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${c.pmid}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 flex items-center gap-1 text-[10px] text-accent-400 hover:text-accent-300 transition"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15,3 21,3 21,9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                      PMID:{c.pmid}
                    </a>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-surface-3 px-4 py-2.5">
          <p className="text-[10px] text-muted text-center">
            BM25 + Dense + CLIP · RRF k=60 · CrossEncoder reranked
          </p>
        </div>
      </aside>
    </>
  );
}
