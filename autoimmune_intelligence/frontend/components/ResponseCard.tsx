"use client";

import { useState } from "react";
import type { QueryResponse, StructuredReasoning } from "@/lib/api";
import PubMedPanel from "./PubMedPanel";

function formatPubMedLink(source: string): { text: string; href: string | null } {
  const pmidMatch = source.match(/PMID:\s*(\d+)/i);
  if (pmidMatch) {
    return { text: source, href: `https://pubmed.ncbi.nlm.nih.gov/${pmidMatch[1]}/` };
  }
  return { text: source, href: null };
}

function ReasoningSection({
  icon,
  label,
  subtitle,
  items,
  accentClass,
  borderClass,
}: {
  icon: string;
  label: string;
  subtitle: string;
  items: string[];
  accentClass: string;
  borderClass: string;
}) {
  if (!items.length) return null;
  return (
    <div className={`rounded-xl border ${borderClass} overflow-hidden`}>
      <div className="flex items-center gap-2.5 px-4 py-3 bg-surface-2">
        <span className="text-base leading-none">{icon}</span>
        <div>
          <p className={`text-xs font-bold uppercase tracking-widest ${accentClass}`}>{label}</p>
          <p className="text-[10px] text-muted mt-0.5">{subtitle}</p>
        </div>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[9px] font-bold ${accentClass} opacity-70`}>
          {items.length}
        </span>
      </div>
      <ul className="px-4 py-3 space-y-1.5 bg-surface-1/50">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-gray-300">
            <span className={`mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full opacity-70`}
              style={{ backgroundColor: "currentColor" }}
            />
            <span className={accentClass.replace("text-", "").length > 0 ? "" : ""}>
              <span className="text-gray-300">{item}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CausalNetworkSection({ graphContext }: { graphContext: QueryResponse["graph_context"] }) {
  const [expanded, setExpanded] = useState(false);
  if (!graphContext?.causal_downstream?.length) return null;
  const shown = expanded ? graphContext.causal_downstream : graphContext.causal_downstream.slice(0, 5);
  return (
    <div className="rounded-xl border border-accent-500/20 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-surface-2">
        <span className="text-base">⚡</span>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-accent-400">Causal Network Impact</p>
          <p className="text-[10px] text-muted mt-0.5">Predicted downstream effects on the immune network</p>
        </div>
        {graphContext.node_count > 0 && (
          <span className="ml-auto text-[10px] text-muted font-mono">
            {graphContext.node_count}n · {graphContext.edge_count}e
          </span>
        )}
      </div>
      <div className="px-4 py-3 bg-surface-1/50 space-y-2">
        {shown.map((item, i) => {
          const barWidth = Math.min(Math.abs(item.score) * 100, 100);
          return (
            <div key={i} className="flex items-center gap-3">
              <span className="w-24 text-xs text-gray-300 font-mono truncate">{item.node}</span>
              <div className="flex-1 h-2 rounded-full bg-surface-3 overflow-hidden">
                <div
                  className={`h-full rounded-full ${item.score >= 0 ? "bg-accent-500" : "bg-red-500"}`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <span className={`text-[10px] font-mono w-14 text-right ${item.score >= 0 ? "text-accent-400" : "text-red-400"}`}>
                {item.score >= 0 ? "+" : ""}{item.score.toFixed(3)}
              </span>
            </div>
          );
        })}
        {graphContext.causal_downstream.length > 5 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-accent-400 hover:text-accent-300 transition mt-1"
          >
            {expanded ? "Show less" : `Show ${graphContext.causal_downstream.length - 5} more nodes`}
          </button>
        )}
      </div>
    </div>
  );
}

export default function ResponseCard({ data }: { data: QueryResponse }) {
  const r: StructuredReasoning | undefined = data.reasoning;
  const hasReasoning =
    r &&
    (r.key_cells.length > 0 ||
      r.key_cytokines.length > 0 ||
      r.pathways.length > 0 ||
      r.therapeutic_targets.length > 0 ||
      r.open_questions.length > 0 ||
      r.genes.length > 0);

  return (
    <div className="space-y-3">
      {/* Disease context banner */}
      {r?.disease_context && (
        <div className="rounded-xl border border-surface-3 bg-surface-1 px-5 py-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-2">Disease Context</p>
          <p className="text-sm leading-relaxed text-gray-300">{r.disease_context}</p>
        </div>
      )}

      {/* Summary narrative */}
      {r?.summary && (
        <div className="rounded-xl border border-accent-500/15 bg-accent-600/5 px-5 py-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-1.5 w-1.5 rounded-full bg-accent-400" />
            <p className="text-[10px] font-bold uppercase tracking-widest text-accent-400">Mechanistic Summary</p>
          </div>
          <p className="text-sm leading-relaxed text-gray-200 whitespace-pre-wrap">{r.summary}</p>
        </div>
      )}

      {/* Structured reasoning grid */}
      {hasReasoning && (
        <div className="grid gap-3 sm:grid-cols-2">
          <ReasoningSection
            icon="🔬"
            label="Key Immune Cells"
            subtitle="Cellular drivers of pathology"
            items={r.key_cells}
            accentClass="text-cell"
            borderClass="border-cell/20"
          />
          <ReasoningSection
            icon="🔥"
            label="Cytokines"
            subtitle="Inflammatory mediators"
            items={r.key_cytokines}
            accentClass="text-cytokine"
            borderClass="border-cytokine/20"
          />
          <ReasoningSection
            icon="🧠"
            label="Dysregulated Pathways"
            subtitle="Signaling cascades altered in disease"
            items={r.pathways}
            accentClass="text-pathway"
            borderClass="border-pathway/20"
          />
          <ReasoningSection
            icon="🧬"
            label="Genetic Risk Loci"
            subtitle="Disease-associated variants and genes"
            items={r.genes}
            accentClass="text-gene"
            borderClass="border-gene/20"
          />
          <ReasoningSection
            icon="💊"
            label="Therapeutic Targets"
            subtitle="Actionable intervention points"
            items={r.therapeutic_targets}
            accentClass="text-target"
            borderClass="border-target/20"
          />
          <ReasoningSection
            icon="❓"
            label="Open Hypotheses"
            subtitle="Mechanistic gaps worth investigating"
            items={r.open_questions}
            accentClass="text-hypothesis"
            borderClass="border-hypothesis/20"
          />
        </div>
      )}

      {/* Causal network context */}
      <CausalNetworkSection graphContext={data.graph_context} />

      {/* PubMed articles */}
      {data.pubmed_articles && data.pubmed_articles.length > 0 && (
        <PubMedPanel articles={data.pubmed_articles} />
      )}

      {/* Sources */}
      {data.sources.length > 0 && (
        <div className="rounded-xl border border-surface-3 bg-surface-1 px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-2.5">Literature References</p>
          <div className="flex flex-wrap gap-1.5">
            {data.sources.map((src, i) => {
              const { text, href } = formatPubMedLink(src);
              return href ? (
                <a
                  key={i}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-lg border border-surface-4 bg-surface-2 px-2.5 py-1 text-xs text-accent-400 transition hover:border-accent-500/40 hover:text-accent-300"
                >
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-60">
                    <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
                  </svg>
                  {text}
                </a>
              ) : (
                <span
                  key={i}
                  className="inline-block rounded-lg border border-surface-4 bg-surface-2 px-2.5 py-1 text-xs text-muted-light"
                >
                  {text}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
