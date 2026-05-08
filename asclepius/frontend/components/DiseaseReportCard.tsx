"use client";

import { useState } from "react";
import type { DiseaseReportResponse } from "@/lib/dmi-api";

function PmidLink({ pmid }: { pmid: string }) {
  const clean = pmid.replace(/^PMID:?\s*/i, "").trim();
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${clean}/`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded border border-surface-4 bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono text-accent-400 transition hover:border-accent-500/40 hover:bg-accent-500/10 hover:text-accent-300"
    >
      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-60">
        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
      </svg>
      PMID:{clean}
    </a>
  );
}

function PmidList({ pmids }: { pmids: string[] }) {
  if (!pmids.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {pmids.map((p, i) => (
        <PmidLink key={i} pmid={p} />
      ))}
    </div>
  );
}

function CollapsibleSection({
  icon,
  label,
  subtitle,
  accentClass,
  borderClass,
  badgeCount,
  children,
  defaultOpen = true,
}: {
  icon: string;
  label: string;
  subtitle?: string;
  accentClass: string;
  borderClass: string;
  badgeCount?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`rounded-xl border ${borderClass} overflow-hidden`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-surface-2 hover:bg-surface-2/80 transition text-left"
      >
        <span className="text-lg leading-none">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-bold uppercase tracking-widest ${accentClass}`}>{label}</span>
            {badgeCount !== undefined && (
              <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${accentClass} bg-current/10`} style={{backgroundColor: "rgba(currentColor,0.1)"}}>
                <span className={`${accentClass}`}>{badgeCount}</span>
              </span>
            )}
          </div>
          {subtitle && <p className="text-[10px] text-muted mt-0.5 leading-snug">{subtitle}</p>}
        </div>
        <svg
          className={`h-4 w-4 shrink-0 text-muted transition-transform ${open ? "" : "-rotate-90"}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="px-4 py-4 bg-surface-1/50 border-t border-surface-3">
          {children}
        </div>
      )}
    </div>
  );
}

export default function DiseaseReportCard({ data }: { data: DiseaseReportResponse }) {
  return (
    <div className="space-y-3">
      {/* Disease Summary */}
      {data.disease_summary && (
        <div className="rounded-xl border border-accent-500/20 bg-accent-600/5 px-5 py-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-1.5 w-1.5 rounded-full bg-accent-400" />
            <p className="text-[10px] font-bold uppercase tracking-widest text-accent-400">Disease Overview</p>
          </div>
          <p className="text-sm leading-relaxed text-gray-200">{data.disease_summary}</p>
        </div>
      )}

      {/* Core Pathways */}
      {data.core_pathways.length > 0 && (
        <CollapsibleSection
          icon="🧠"
          label="Core Pathways"
          subtitle="Primary molecular mechanisms driving disease pathogenesis"
          accentClass="text-pathway"
          borderClass="border-pathway/20"
          badgeCount={data.core_pathways.length}
        >
          <div className="space-y-4">
            {data.core_pathways.map((pw, i) => (
              <div key={i} className={`${i > 0 ? "pt-4 border-t border-surface-3" : ""}`}>
                <div className="flex items-start gap-2">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-pathway opacity-70" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-100">{pw.name}</p>
                    <p className="text-sm text-gray-400 mt-1 leading-relaxed">{pw.description}</p>
                    <PmidList pmids={pw.evidence_pmids} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Grid: Causal Genes + Cell Types */}
      <div className="grid gap-3 sm:grid-cols-2">
        {data.causal_genes.length > 0 && (
          <CollapsibleSection
            icon="🧬"
            label="Causal Genes"
            subtitle="Key genetic risk loci and effectors"
            accentClass="text-gene"
            borderClass="border-gene/20"
            badgeCount={data.causal_genes.length}
          >
            <div className="flex flex-wrap gap-1.5">
              {data.causal_genes.map((g, i) => (
                <span
                  key={i}
                  className="rounded-lg border border-gene/25 bg-gene/8 px-2.5 py-1 text-xs font-mono font-semibold text-gene"
                  style={{ backgroundColor: "rgba(244, 114, 182, 0.06)" }}
                >
                  {g}
                </span>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {data.key_cell_types.length > 0 && (
          <CollapsibleSection
            icon="🔬"
            label="Key Cell Types"
            subtitle="Immune cells central to disease pathology"
            accentClass="text-cell"
            borderClass="border-cell/20"
            badgeCount={data.key_cell_types.length}
          >
            <ul className="space-y-1.5">
              {data.key_cell_types.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cell opacity-70" />
                  {c}
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}
      </div>

      {/* Validated Targets */}
      {data.validated_targets.length > 0 && (
        <CollapsibleSection
          icon="🎯"
          label="Validated Therapeutic Targets"
          subtitle="Targets with clinical or preclinical evidence of efficacy"
          accentClass="text-target"
          borderClass="border-target/20"
          badgeCount={data.validated_targets.length}
        >
          <div className="space-y-4">
            {data.validated_targets.map((vt, i) => (
              <div key={i} className={`${i > 0 ? "pt-4 border-t border-surface-3" : ""}`}>
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 rounded-full bg-target/15 px-2 py-0.5 text-[10px] font-bold text-target">TARGET</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-100">{vt.target}</p>
                    <p className="text-sm text-gray-400 mt-1 leading-relaxed">{vt.mechanism}</p>
                    <PmidList pmids={vt.evidence_pmids} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Failed Targets */}
      {data.failed_targets.length > 0 && (
        <CollapsibleSection
          icon="⚠️"
          label="Failed Targets"
          subtitle="Targets that did not translate clinically — important for de-risking"
          accentClass="text-red-400"
          borderClass="border-red-500/20"
          badgeCount={data.failed_targets.length}
          defaultOpen={false}
        >
          <div className="space-y-4">
            {data.failed_targets.map((ft, i) => (
              <div key={i} className={`${i > 0 ? "pt-4 border-t border-surface-3" : ""}`}>
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-400 uppercase whitespace-nowrap">
                    {ft.stage_failed}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-100">{ft.target}</p>
                    <p className="text-sm text-gray-400 mt-1 leading-relaxed">{ft.mechanistic_reason}</p>
                    <PmidList pmids={ft.evidence_pmids} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Mechanistic Contradictions */}
      {data.mechanistic_contradictions.length > 0 && (
        <CollapsibleSection
          icon="❓"
          label="Mechanistic Contradictions"
          subtitle="Conflicting findings in the literature worth investigating"
          accentClass="text-hypothesis"
          borderClass="border-hypothesis/20"
          badgeCount={data.mechanistic_contradictions.length}
          defaultOpen={false}
        >
          <div className="space-y-3">
            {data.mechanistic_contradictions.map((mc, i) => (
              <div key={i} className={`${i > 0 ? "pt-3 border-t border-surface-3" : ""}`}>
                <p className="text-sm text-gray-300 leading-relaxed">{mc.description}</p>
                <PmidList pmids={mc.evidence_pmids} />
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Grid: Biomarkers + Unresolved Questions */}
      <div className="grid gap-3 sm:grid-cols-2">
        {data.biomarkers.length > 0 && (
          <CollapsibleSection
            icon="🩸"
            label="Biomarkers"
            subtitle="Measurable indicators of disease activity"
            accentClass="text-cytokine"
            borderClass="border-cytokine/20"
            badgeCount={data.biomarkers.length}
          >
            <div className="flex flex-wrap gap-1.5">
              {data.biomarkers.map((b, i) => (
                <span
                  key={i}
                  className="rounded-lg border border-cytokine/25 px-2.5 py-1 text-xs font-medium text-cytokine"
                  style={{ backgroundColor: "rgba(249, 115, 22, 0.06)" }}
                >
                  {b}
                </span>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {data.unresolved_questions.length > 0 && (
          <CollapsibleSection
            icon="🔭"
            label="Open Questions"
            subtitle="Unanswered mechanistic gaps in current research"
            accentClass="text-hypothesis"
            borderClass="border-hypothesis/20"
            badgeCount={data.unresolved_questions.length}
          >
            <ul className="space-y-2">
              {data.unresolved_questions.map((q, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-300 leading-relaxed">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-hypothesis opacity-70" />
                  {q}
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}
      </div>

      {/* All Citations */}
      {data.all_citations.length > 0 && (
        <div className="rounded-xl border border-surface-3 bg-surface-1 px-4 py-3">
          <div className="flex items-center gap-2 mb-2.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted-light">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14,2 14,8 20,8" />
            </svg>
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light">
              All Citations ({data.all_citations.length})
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.all_citations.map((pmid, i) => (
              <PmidLink key={i} pmid={pmid} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
