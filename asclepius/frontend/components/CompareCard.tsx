"use client";

import { useState } from "react";
import type { CompareResponse } from "@/lib/api";

interface CompareCardProps {
  data: CompareResponse;
}

type OverlapTab = "pathways" | "cytokines" | "cells" | "genes" | "therapeutics" | "mechanisms";

const OVERLAP_TABS: { key: OverlapTab; label: string; icon: string; accentClass: string }[] = [
  { key: "pathways",     label: "Pathways",      icon: "🧠", accentClass: "text-pathway" },
  { key: "cytokines",    label: "Cytokines",     icon: "🔥", accentClass: "text-cytokine" },
  { key: "cells",        label: "Immune Cells",  icon: "🔬", accentClass: "text-cell" },
  { key: "genes",        label: "Genetic Loci",  icon: "🧬", accentClass: "text-gene" },
  { key: "therapeutics", label: "Therapeutics",  icon: "💊", accentClass: "text-target" },
  { key: "mechanisms",   label: "Mechanisms",    icon: "⚙️", accentClass: "text-hypothesis" },
];

function TagList({ items, colorClass }: { items: string[]; colorClass: string }) {
  if (!items.length) return <p className="text-xs text-muted italic">None identified</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <span key={i} className={`rounded-lg border px-2.5 py-1 text-xs font-medium ${colorClass}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function OverlapTabContent({
  tab,
  o,
  nameA,
  nameB,
}: {
  tab: OverlapTab;
  o: CompareResponse["overlaps"];
  nameA: string;
  nameB: string;
}) {
  const configs = {
    pathways:     { shared: o.shared_pathways,     a: o.unique_pathways_a,     b: o.unique_pathways_b,     color: "border-pathway/25 bg-pathway/5 text-pathway" },
    cytokines:    { shared: o.shared_cytokines,    a: o.unique_cytokines_a,    b: o.unique_cytokines_b,    color: "border-cytokine/25 bg-cytokine/5 text-cytokine" },
    cells:        { shared: o.shared_cell_types,   a: o.unique_cell_types_a,   b: o.unique_cell_types_b,   color: "border-cell/25 bg-cell/5 text-cell" },
    genes:        { shared: o.shared_genes,        a: o.unique_genes_a,        b: o.unique_genes_b,        color: "border-gene/25 bg-gene/5 text-gene" },
    therapeutics: { shared: o.shared_therapeutics, a: o.unique_therapeutics_a, b: o.unique_therapeutics_b, color: "border-target/25 bg-target/5 text-target" },
    mechanisms:   { shared: o.shared_mechanisms,   a: o.unique_mechanisms_a,   b: o.unique_mechanisms_b,   color: "border-hypothesis/25 bg-hypothesis/5 text-hypothesis" },
  };
  const cfg = configs[tab];
  return (
    <div className="space-y-4 pt-4">
      {cfg.shared.length > 0 && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-2 flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-accent-400" />
            Shared ({cfg.shared.length})
          </p>
          <TagList items={cfg.shared} colorClass={cfg.color} />
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-2 flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-blue-400" />
            Only {nameA} ({cfg.a.length})
          </p>
          <TagList items={cfg.a} colorClass="border-blue-500/25 bg-blue-500/5 text-blue-400" />
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-purple-400 mb-2 flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-purple-400" />
            Only {nameB} ({cfg.b.length})
          </p>
          <TagList items={cfg.b} colorClass="border-purple-500/25 bg-purple-500/5 text-purple-400" />
        </div>
      </div>
    </div>
  );
}

export default function CompareCard({ data }: CompareCardProps) {
  const { disease_a: a, disease_b: b, overlaps: o, similarity_score, summary } = data;
  const pct = Math.round(similarity_score * 100);
  const [activeTab, setActiveTab] = useState<OverlapTab>("pathways");

  const nameA = a.disease_name.split(" ")[0];
  const nameB = b.disease_name.split(" ")[0];

  const diffRows = [
    { label: "Pathways",     shared: o.shared_pathways.length,     ua: o.unique_pathways_a.length,     ub: o.unique_pathways_b.length },
    { label: "Genes",        shared: o.shared_genes.length,        ua: o.unique_genes_a.length,        ub: o.unique_genes_b.length },
    { label: "Therapeutics", shared: o.shared_therapeutics.length, ua: o.unique_therapeutics_a.length, ub: o.unique_therapeutics_b.length },
    { label: "Cytokines",    shared: o.shared_cytokines.length,    ua: o.unique_cytokines_a.length,    ub: o.unique_cytokines_b.length },
    { label: "Cell Types",   shared: o.shared_cell_types.length,   ua: o.unique_cell_types_a.length,   ub: o.unique_cell_types_b.length },
    { label: "Mechanisms",   shared: o.shared_mechanisms.length,   ua: o.unique_mechanisms_a.length,   ub: o.unique_mechanisms_b.length },
  ];

  return (
    <div className="space-y-4">
      {/* Diff summary table */}
      <div className="rounded-xl border border-surface-3 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-surface-2 border-b border-surface-3">
              <th className="text-left px-4 py-2.5 text-muted font-semibold uppercase tracking-wider">Category</th>
              <th className="text-center px-3 py-2.5 text-accent-400 font-semibold">Shared</th>
              <th className="text-center px-3 py-2.5 text-blue-400 font-semibold">{nameA} only</th>
              <th className="text-center px-3 py-2.5 text-purple-400 font-semibold">{nameB} only</th>
            </tr>
          </thead>
          <tbody className="bg-surface-1 divide-y divide-surface-3">
            {diffRows.map((row) => (
              <tr key={row.label} className="hover:bg-surface-2/50 transition">
                <td className="px-4 py-2 text-gray-400 font-medium">{row.label}</td>
                <td className="px-3 py-2 text-center">
                  {row.shared > 0
                    ? <span className="inline-block rounded-full bg-accent-600/20 text-accent-400 px-2 py-0.5 text-[10px] font-bold">{row.shared}</span>
                    : <span className="text-muted">n/a</span>}
                </td>
                <td className="px-3 py-2 text-center">
                  {row.ua > 0
                    ? <span className="inline-block rounded-full bg-blue-500/15 text-blue-400 px-2 py-0.5 text-[10px] font-bold">{row.ua}</span>
                    : <span className="text-muted">n/a</span>}
                </td>
                <td className="px-3 py-2 text-center">
                  {row.ub > 0
                    ? <span className="inline-block rounded-full bg-purple-500/15 text-purple-400 px-2 py-0.5 text-[10px] font-bold">{row.ub}</span>
                    : <span className="text-muted">n/a</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Header: similarity score */}
      <div className="rounded-xl border border-accent-500/25 overflow-hidden">
        <div className="px-5 py-4 bg-surface-1">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-ink text-display-m">
              <span>{a.disease_name}</span>
              <span className="mx-3 text-muted font-mono text-sm">vs</span>
              <span>{b.disease_name}</span>
            </h3>
            <div className="text-right">
              <p className="font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.14em" }}>Similarity</p>
              <span className="font-display tabular-nums text-green" style={{ fontSize: 32 }}>{pct}%</span>
            </div>
          </div>
          {/* Similarity bar */}
          <div className="h-3 rounded-full bg-surface-3 overflow-hidden">
            <div
              className="h-full rounded-full bg-green transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="flex justify-between mt-1 text-[9px] text-muted">
            <span>0%: No overlap</span>
            <span>100%: Identical</span>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="rounded-xl border border-surface-3 bg-surface-1 px-5 py-4">
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-2">Comparison Summary</p>
        <p className="text-sm leading-relaxed text-gray-300 whitespace-pre-wrap">{summary}</p>
      </div>

      {/* Side-by-side disease profiles */}
      <div className="grid gap-3 md:grid-cols-2">
        {[a, b].map((disease, idx) => (
          <div
            key={disease.disease_name}
            className={`rounded-xl border p-4 ${idx === 0 ? "border-blue-500/20 bg-blue-500/3" : "border-purple-500/20 bg-purple-500/3"}`}
            style={{ backgroundColor: idx === 0 ? "rgba(59, 130, 246, 0.03)" : "rgba(168, 85, 247, 0.03)" }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className={`h-2.5 w-2.5 rounded-full ${idx === 0 ? "bg-blue-400" : "bg-purple-400"}`} />
              <h4 className={`text-sm font-bold ${idx === 0 ? "text-blue-400" : "text-purple-400"}`}>
                {disease.disease_name}
              </h4>
            </div>
            <p className="text-xs text-gray-400 mb-3 leading-relaxed">{disease.description.slice(0, 180)}…</p>
            {disease.prevalence && (
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] text-muted font-medium uppercase tracking-wider">Prevalence</span>
                <span className="text-xs text-gray-300">{disease.prevalence}</span>
              </div>
            )}
            <div className="space-y-1.5 border-t border-surface-3 pt-2.5 mt-2.5">
              {disease.key_cell_types.length > 0 && (
                <p className="text-xs text-gray-400 leading-relaxed">
                  <span className="text-cell font-semibold">Cells: </span>
                  {disease.key_cell_types.slice(0, 4).join(", ")}
                </p>
              )}
              {disease.cytokines.length > 0 && (
                <p className="text-xs text-gray-400 leading-relaxed">
                  <span className="text-cytokine font-semibold">Cytokines: </span>
                  {disease.cytokines.slice(0, 5).join(", ")}
                </p>
              )}
              {disease.associated_genes.length > 0 && (
                <p className="text-xs text-gray-400 leading-relaxed">
                  <span className="text-gene font-semibold">Genes: </span>
                  {disease.associated_genes.slice(0, 5).map((g) => g.gene).join(", ")}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Overlap Analysis: tabbed */}
      <div className="rounded-xl border border-surface-3 overflow-hidden">
        <div className="border-b border-surface-3 bg-surface-2 px-3 py-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light mb-2">Overlap Analysis</p>
          <div className="flex flex-wrap gap-0.5">
            {OVERLAP_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-all ${
                  activeTab === tab.key
                    ? "bg-surface-1 text-gray-200 shadow-sm"
                    : "text-muted hover:text-gray-300 hover:bg-surface-1/50"
                }`}
              >
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="px-4 pb-4 bg-surface-1/30">
          <OverlapTabContent
            tab={activeTab}
            o={o}
            nameA={nameA}
            nameB={nameB}
          />
        </div>
      </div>
    </div>
  );
}
