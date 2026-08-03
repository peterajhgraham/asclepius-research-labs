"use client";

import { useState } from "react";
import type { DiseaseReportResponse } from "@/lib/dmi-api";

// Quiet, neutral citation chip — hover reveals the green link affordance.
// Reserving bright green for hover keeps a report full of citations calm.
function PmidLink({ pmid }: { pmid: string }) {
  const clean = pmid.replace(/^PMID:?\s*/i, "").trim();
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${clean}/`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded-md border border-line-2 bg-bg-3 px-1.5 py-0.5 text-[10px] font-mono text-muted transition hover:border-green/40 hover:text-green"
    >
      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-50">
        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
      </svg>
      {clean}
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

// A neutral content chip (genes, cell types, biomarkers).
function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md border border-line-2 bg-bg-3 px-2.5 py-1 text-xs font-mono text-ink-2">
      {children}
    </span>
  );
}

function CollapsibleSection({
  label,
  subtitle,
  accent = "var(--muted)",
  count,
  children,
  defaultOpen = true,
}: {
  label: string;
  subtitle?: string;
  accent?: string;
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-line bg-bg-2 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-bg-3"
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: accent }} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-2">{label}</span>
            {count !== undefined && (
              <span className="rounded-full bg-bg-4 px-1.5 py-0.5 text-[10px] font-mono tabular-nums text-muted">
                {count}
              </span>
            )}
          </div>
          {subtitle && <p className="mt-0.5 text-[11px] leading-snug text-muted">{subtitle}</p>}
        </div>
        <svg
          className={`h-4 w-4 shrink-0 text-muted transition-transform ${open ? "" : "-rotate-90"}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && <div className="border-t border-line px-4 py-4">{children}</div>}
    </div>
  );
}

// A named item with a description + supporting citations (pathways, targets).
function EvidenceItem({
  badge,
  badgeColor,
  title,
  body,
  pmids,
  first,
}: {
  badge?: string;
  badgeColor?: string;
  title: string;
  body: string;
  pmids: string[];
  first: boolean;
}) {
  return (
    <div className={first ? "" : "border-t border-line pt-4"}>
      <div className="flex items-start gap-2.5">
        {badge ? (
          <span
            className="mt-0.5 shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{
              color: badgeColor,
              background: `color-mix(in srgb, ${badgeColor ?? "var(--muted)"} 14%, transparent)`,
            }}
          >
            {badge}
          </span>
        ) : (
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink">{title}</p>
          <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
          <PmidList pmids={pmids} />
        </div>
      </div>
    </div>
  );
}

export default function DiseaseReportCard({ data: raw }: { data: DiseaseReportResponse }) {
  const data = {
    ...raw,
    core_pathways: raw.core_pathways ?? [],
    causal_genes: raw.causal_genes ?? [],
    key_cell_types: raw.key_cell_types ?? [],
    validated_targets: raw.validated_targets ?? [],
    failed_targets: raw.failed_targets ?? [],
    mechanistic_contradictions: raw.mechanistic_contradictions ?? [],
    biomarkers: raw.biomarkers ?? [],
    unresolved_questions: raw.unresolved_questions ?? [],
    all_citations: raw.all_citations ?? [],
  };
  return (
    <div className="space-y-3">
      {/* Disease Overview */}
      {data.disease_summary && (
        <div className="rounded-xl border border-line bg-bg-2 px-5 py-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-green" />
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Disease Overview</p>
          </div>
          <p className="text-sm leading-relaxed text-ink-2">{data.disease_summary}</p>
        </div>
      )}

      {/* Core Pathways */}
      {data.core_pathways.length > 0 && (
        <CollapsibleSection
          label="Core Pathways"
          subtitle="Primary molecular mechanisms driving disease pathogenesis"
          count={data.core_pathways.length}
        >
          <div className="space-y-4">
            {data.core_pathways.map((pw, i) => (
              <EvidenceItem
                key={i}
                first={i === 0}
                title={pw.name}
                body={pw.description}
                pmids={pw.evidence_pmids}
              />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Grid: Causal Genes + Cell Types */}
      <div className="grid gap-3 sm:grid-cols-2">
        {data.causal_genes.length > 0 && (
          <CollapsibleSection
            label="Causal Genes"
            subtitle="Key genetic risk loci and effectors"
            accent="var(--green)"
            count={data.causal_genes.length}
          >
            <div className="flex flex-wrap gap-1.5">
              {data.causal_genes.map((g, i) => (
                <Tag key={i}>{g}</Tag>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {data.key_cell_types.length > 0 && (
          <CollapsibleSection
            label="Key Cell Types"
            subtitle="Cells central to disease pathology"
            count={data.key_cell_types.length}
          >
            <ul className="space-y-1.5">
              {data.key_cell_types.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-ink-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted" />
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
          label="Validated Therapeutic Targets"
          subtitle="Targets with clinical or preclinical evidence of efficacy"
          accent="var(--green)"
          count={data.validated_targets.length}
        >
          <div className="space-y-4">
            {data.validated_targets.map((vt, i) => (
              <EvidenceItem
                key={i}
                first={i === 0}
                badge="Target"
                badgeColor="var(--green)"
                title={vt.target}
                body={vt.mechanism}
                pmids={vt.evidence_pmids}
              />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Failed Targets */}
      {data.failed_targets.length > 0 && (
        <CollapsibleSection
          label="Failed Targets"
          subtitle="Targets that did not translate clinically, useful for de-risking"
          accent="var(--red)"
          count={data.failed_targets.length}
          defaultOpen={false}
        >
          <div className="space-y-4">
            {data.failed_targets.map((ft, i) => (
              <EvidenceItem
                key={i}
                first={i === 0}
                badge={ft.stage_failed}
                badgeColor="var(--red)"
                title={ft.target}
                body={ft.mechanistic_reason}
                pmids={ft.evidence_pmids}
              />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Mechanistic Contradictions */}
      {data.mechanistic_contradictions.length > 0 && (
        <CollapsibleSection
          label="Mechanistic Contradictions"
          subtitle="Conflicting findings in the literature worth investigating"
          accent="var(--amber)"
          count={data.mechanistic_contradictions.length}
          defaultOpen={false}
        >
          <div className="space-y-3">
            {data.mechanistic_contradictions.map((mc, i) => (
              <div key={i} className={i === 0 ? "" : "border-t border-line pt-3"}>
                <p className="text-sm leading-relaxed text-ink-2">{mc.description}</p>
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
            label="Biomarkers"
            subtitle="Measurable indicators of disease activity"
            count={data.biomarkers.length}
          >
            <div className="flex flex-wrap gap-1.5">
              {data.biomarkers.map((b, i) => (
                <Tag key={i}>{b}</Tag>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {data.unresolved_questions.length > 0 && (
          <CollapsibleSection
            label="Open Questions"
            subtitle="Unanswered mechanistic gaps in current research"
            accent="var(--amber)"
            count={data.unresolved_questions.length}
          >
            <ul className="space-y-2">
              {data.unresolved_questions.map((q, i) => (
                <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-ink-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted" />
                  {q}
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}
      </div>

      {/* All Citations */}
      {data.all_citations.length > 0 && (
        <div className="rounded-xl border border-line bg-bg-2 px-4 py-3">
          <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
            All Citations ({data.all_citations.length})
          </p>
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
