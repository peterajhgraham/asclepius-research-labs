"use client";

import { useState } from "react";
import type { HypothesisResponse, Hypothesis } from "@/lib/api";

const CATEGORY_CONFIG: Record<string, { color: string; icon: string; description: string }> = {
  "Target Discovery":    { color: "bg-accent-600/20 text-accent-400 border-accent-500/25",   icon: "🎯", description: "Novel therapeutic targets based on disease mechanisms" },
  "Drug Repurposing":    { color: "bg-purple-500/20 text-purple-400 border-purple-500/25",   icon: "💊", description: "Existing approved drugs with potential new indications" },
  "Network Mechanism":   { color: "bg-cyan-500/20 text-cyan-400 border-cyan-500/25",         icon: "🕸️", description: "Systems-level mechanistic insights from pathway analysis" },
  "Genetic Mechanism":   { color: "bg-pink-500/20 text-pink-400 border-pink-500/25",         icon: "🧬", description: "Genetic or epigenetic drivers of disease pathogenesis" },
  "Combination Therapy": { color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/25", icon: "⚗️", description: "Synergistic multi-target therapeutic approaches" },
};

const CONFIDENCE_CONFIG: Record<string, { pct: number; bar: string; label: string }> = {
  "High":        { pct: 92, bar: "bg-green-400",  label: "text-green-400" },
  "Medium-High": { pct: 70, bar: "bg-blue-400",   label: "text-blue-400" },
  "Medium":      { pct: 50, bar: "bg-yellow-400", label: "text-yellow-400" },
  "Low":         { pct: 25, bar: "bg-red-400",    label: "text-red-400" },
};

function CategoryBadge({ category }: { category: string }) {
  const cfg = CATEGORY_CONFIG[category] || { color: "bg-surface-3 text-muted-light border-surface-4", icon: "💡", description: "" };
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-bold ${cfg.color}`}>
      {category}
    </span>
  );
}

function ConfidenceMeter({ confidence }: { confidence: string }) {
  const cfg = CONFIDENCE_CONFIG[confidence] || CONFIDENCE_CONFIG["Medium"];
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className={`text-[10px] font-bold whitespace-nowrap ${cfg.label}`}>{confidence}</span>
      <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden" style={{ minWidth: 48 }}>
        <div
          className={`h-full rounded-full transition-all duration-700 ${cfg.bar}`}
          style={{ width: `${cfg.pct}%` }}
        />
      </div>
    </div>
  );
}

function SingleHypothesis({ h, index }: { h: Hypothesis; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`rounded-xl border overflow-hidden transition-all ${expanded ? "border-accent-500/30" : "border-surface-3"}`}>
      {/* Collapsed header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full px-5 py-4 text-left transition ${expanded ? "bg-surface-2" : "bg-surface-1 hover:bg-surface-2"}`}
      >
        <div className="flex items-start gap-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent-600/15 text-xs font-bold text-accent-400 mt-0.5">
            {index + 1}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-100 leading-relaxed">{h.hypothesis}</p>
            <div className="flex flex-wrap items-center gap-3 mt-2">
              <CategoryBadge category={h.category} />
              <ConfidenceMeter confidence={h.confidence} />
            </div>
          </div>
          <svg
            className={`h-4 w-4 shrink-0 text-muted transition-transform mt-1 ${expanded ? "rotate-180" : ""}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-surface-3 bg-surface-0/50 px-5 py-5 space-y-5">
          {/* Rationale */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-1.5">Scientific Rationale</p>
            <p className="text-sm text-gray-300 leading-relaxed">{h.rationale}</p>
          </div>

          {/* Experimental Design */}
          <div className="rounded-xl border border-line bg-bg-2 p-4 space-y-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted">
              Experimental Design
            </p>
            <div className="grid gap-3 sm:grid-cols-2 text-sm">
              <div className="rounded-lg border border-surface-3 bg-surface-1 px-3 py-2">
                <p className="text-[10px] text-muted font-semibold uppercase mb-1">Model System</p>
                <p className="text-gray-300">{h.experimental_design.model}</p>
              </div>
              <div className="rounded-lg border border-surface-3 bg-surface-1 px-3 py-2">
                <p className="text-[10px] text-muted font-semibold uppercase mb-1">Timeline</p>
                <p className="text-gray-300">{h.experimental_design.timeline}</p>
              </div>
            </div>
            <div className="rounded-lg border border-surface-3 bg-surface-1 px-3 py-2">
              <p className="text-[10px] text-muted font-semibold uppercase mb-1">Intervention</p>
              <p className="text-sm text-gray-300">{h.experimental_design.intervention}</p>
            </div>
            {h.experimental_design.readouts.length > 0 && (
              <div>
                <p className="text-[10px] text-muted font-semibold uppercase mb-1.5">Readouts</p>
                <ul className="space-y-1">
                  {h.experimental_design.readouts.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent-400/60" />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {h.experimental_design.controls.length > 0 && (
              <div>
                <p className="text-[10px] text-muted font-semibold uppercase mb-1.5">Controls</p>
                <ul className="space-y-1">
                  {h.experimental_design.controls.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gray-500" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Biomarkers & Confounders side by side */}
          <div className="grid gap-3 sm:grid-cols-2">
            {h.biomarkers.length > 0 && (
              <div className="rounded-xl border border-line bg-bg-2 p-3">
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-2">Biomarkers</p>
                <ul className="space-y-1">
                  {h.biomarkers.map((b, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-cell/60" />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {h.confounders.length > 0 && (
              <div className="rounded-xl border border-amber/20 p-3" style={{ backgroundColor: "rgba(245, 192, 98, 0.05)" }}>
                <p className="text-[10px] font-bold uppercase tracking-widest text-amber mb-2">Confounders</p>
                <ul className="space-y-1">
                  {h.confounders.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-yellow-400/60" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Supporting Evidence with clickable PubMed links */}
          {h.supporting_evidence.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-1.5">Supporting Evidence</p>
              <div className="flex flex-wrap gap-1.5">
                {h.supporting_evidence.map((cite, i) => {
                  const pmidMatch = cite.match(/(?:PMID:?\s*)?(\d{7,9})/i);
                  return pmidMatch ? (
                    <a
                      key={i}
                      href={`https://pubmed.ncbi.nlm.nih.gov/${pmidMatch[1]}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-mono border border-line-2 bg-bg-3 text-muted hover:text-green hover:border-green/40 transition"
                    >
                      {cite}
                      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
                      </svg>
                    </a>
                  ) : (
                    <span key={i} className="rounded px-2 py-0.5 text-[10px] border border-surface-3 bg-surface-2 text-muted-light">
                      {cite}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function HypothesisCard({ data }: { data: HypothesisResponse }) {
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const categories = Array.from(new Set(data.hypotheses.map((h) => h.category)));
  const filtered = categoryFilter
    ? data.hypotheses.filter((h) => h.category === categoryFilter)
    : data.hypotheses;

  return (
    <div className="space-y-4">
      {/* Evidence Context */}
      <div className="rounded-xl border border-surface-3 bg-surface-1 px-5 py-4">
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-3">Evidence Context</p>
        <div className="flex flex-wrap gap-4 text-xs text-gray-400">
          {data.context.diseases_matched.length > 0 && (
            <div>
              <span className="text-muted font-medium uppercase tracking-wider text-[9px]">Diseases matched</span>
              <p className="text-gray-300 mt-0.5">{data.context.diseases_matched.join(", ")}</p>
            </div>
          )}
          {data.context.pathways_matched.length > 0 && (
            <div>
              <span className="text-muted font-medium uppercase tracking-wider text-[9px]">Pathways</span>
              <p className="text-gray-300 mt-0.5">{data.context.pathways_matched.join(", ")}</p>
            </div>
          )}
          {data.context.therapeutics_matched.length > 0 && (
            <div>
              <span className="text-muted font-medium uppercase tracking-wider text-[9px]">Therapeutics</span>
              <p className="text-gray-300 mt-0.5">{data.context.therapeutics_matched.join(", ")}</p>
            </div>
          )}
        </div>
      </div>

      {/* Category filter */}
      {categories.length > 1 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-[10px] text-muted font-semibold uppercase tracking-wider">Filter:</span>
          <button
            onClick={() => setCategoryFilter(null)}
            className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
              categoryFilter === null
                ? "bg-surface-2 border-surface-4 text-gray-200"
                : "border-surface-3 text-muted hover:text-gray-300"
            }`}
          >
            All ({data.hypotheses.length})
          </button>
          {categories.map((cat) => {
            const cfg = CATEGORY_CONFIG[cat];
            const count = data.hypotheses.filter((h) => h.category === cat).length;
            return (
              <button
                key={cat}
                onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition ${
                  categoryFilter === cat
                    ? cfg?.color || "bg-surface-2 border-surface-4 text-gray-200"
                    : "border-surface-3 text-muted hover:text-gray-300"
                }`}
              >
                {cat} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Hypotheses list */}
      <div className="space-y-2">
        {filtered.map((h, i) => (
          <SingleHypothesis key={h.hypothesis.slice(0, 80)} h={h} index={i} />
        ))}
      </div>

      {data.total_generated === 0 && (
        <div className="rounded-xl border border-surface-3 bg-surface-1 px-5 py-8 text-center">
          <p className="text-sm text-muted leading-relaxed">
            No hypotheses could be generated for this topic. Try a more specific query involving a disease, pathway, or therapeutic target.
          </p>
        </div>
      )}
    </div>
  );
}
