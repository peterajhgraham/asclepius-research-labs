"use client";

import { useEffect, useRef } from "react";
import type { Citation } from "@/hooks/useStreamingQuery";

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

interface Props {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
}

export default function CitationPanel({ citations, isOpen, onClose }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <>
      {/* Backdrop — mobile overlay only, shown when panel is open */}
      {isOpen && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}

      {/* Panel — hidden on mobile when closed; at lg+ always shown as persistent column */}
      <aside
        ref={panelRef}
        className={`${isOpen ? "flex fixed" : "hidden"} right-0 top-0 z-40 h-full w-[340px] border-l border-line bg-bg-2 shadow-card animate-slide-in flex-col
                   lg:flex lg:relative lg:right-auto lg:top-auto lg:z-auto lg:shadow-none lg:flex-shrink-0`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div>
            <h3 className="font-display text-ink text-display-m leading-none">
              Sources <span className="text-green tabular-nums">· {citations.length}</span>
            </h3>
            <p className="mt-1.5 font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.12em" }}>
              multimodal hybrid · RRF reranked
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close sources"
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-bg-3 hover:text-ink transition"
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
              const label = TYPE_LABELS[effectiveType] ?? effectiveType;

              return (
                <div
                  key={`${i}-${c.image_hash || c.pmid || c.text.slice(0, 20)}`}
                  id={`cite-${i + 1}`}
                  className="rounded-lg border border-line bg-bg-2 p-3 transition hover:bg-bg-3"
                >
                  {/* Ref number + figure thumbnail (images only) + meta */}
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 pt-0.5 font-mono text-[11px] font-semibold tabular-nums text-green" style={{ minWidth: 24 }}>
                      [{i + 1}]
                    </span>
                    {isImage && (
                      <a
                        href={`/api/images/${c.image_hash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block h-12 w-12 shrink-0 overflow-hidden rounded border border-line bg-bg-4 hover:opacity-90 transition"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/api/images/${c.image_hash}`}
                          alt={c.text.slice(0, 80)}
                          loading="lazy"
                          className="h-full w-full object-cover"
                        />
                      </a>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.12em" }}>
                        {label}{c.page ? ` · p.${c.page}` : ""}
                      </p>
                      {c.source && (
                        <p className="mt-0.5 text-[11px] font-medium text-ink-2 truncate">{c.source}</p>
                      )}
                      {c.pmid && (
                        <p className="mt-0.5 font-mono tabular-nums text-muted" style={{ fontSize: 10 }}>
                          PMID:{c.pmid}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Table markdown rendering */}
                  {isTable && c.table_markdown && (
                    <pre className="mt-2 max-h-40 overflow-auto rounded border border-line bg-bg-3 p-2 text-[10px] font-mono text-ink-2 whitespace-pre">
                      {c.table_markdown}
                    </pre>
                  )}

                  {/* Proposition text: italic caption */}
                  <p className="mt-2 text-xs italic text-muted leading-relaxed line-clamp-4">{c.text}</p>

                  {/* PMID link */}
                  {c.pmid && (
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${c.pmid}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 flex items-center gap-1 text-[10px] font-mono text-green hover:brightness-110 transition"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15,3 21,3 21,9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                      View on PubMed
                    </a>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-line px-4 py-2.5">
          <p className="text-center font-mono text-faint" style={{ fontSize: 10 }}>
            BM25 + Dense + CLIP · RRF k=60 · CrossEncoder reranked
          </p>
        </div>
      </aside>
    </>
  );
}
