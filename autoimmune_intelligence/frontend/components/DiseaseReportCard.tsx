import type { DiseaseReportResponse } from "@/lib/dmi-api";

function PmidLink({ pmid }: { pmid: string }) {
  const clean = pmid.replace(/^PMID:?\s*/i, "").trim();
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${clean}/`}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-block rounded border border-surface-4 bg-surface-2 px-1.5 py-0.5 text-[10px] font-mono text-accent-400 transition hover:border-accent-500/40 hover:text-accent-300"
    >
      PMID:{clean}
    </a>
  );
}

function PmidList({ pmids }: { pmids: string[] }) {
  if (!pmids.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {pmids.map((p, i) => (
        <PmidLink key={i} pmid={p} />
      ))}
    </div>
  );
}

function Section({
  icon,
  label,
  children,
  accentClass,
  borderClass,
}: {
  icon: string;
  label: string;
  children: React.ReactNode;
  accentClass: string;
  borderClass: string;
}) {
  return (
    <div className={`rounded-lg border ${borderClass} bg-surface-2 p-4`}>
      <h3
        className={`mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest ${accentClass}`}
      >
        <span className="text-base">{icon}</span>
        {label}
      </h3>
      {children}
    </div>
  );
}

export default function DiseaseReportCard({
  data,
}: {
  data: DiseaseReportResponse;
}) {
  return (
    <div className="space-y-3">
      {/* Disease Summary */}
      {data.disease_summary && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-1.5">
            Disease Summary
          </p>
          <p className="text-sm leading-relaxed text-gray-300">
            {data.disease_summary}
          </p>
        </div>
      )}

      {/* Core Pathways */}
      {data.core_pathways.length > 0 && (
        <Section
          icon={"\uD83E\uDDE0"}
          label="Core Pathways"
          accentClass="text-pathway"
          borderClass="border-pathway/20"
        >
          <div className="space-y-3">
            {data.core_pathways.map((pw, i) => (
              <div key={i}>
                <p className="text-sm font-medium text-gray-200">{pw.name}</p>
                <p className="text-sm text-gray-400 mt-0.5">{pw.description}</p>
                <PmidList pmids={pw.evidence_pmids} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Grid: Genes + Cell Types */}
      <div className="grid gap-3 sm:grid-cols-2">
        {data.causal_genes.length > 0 && (
          <Section
            icon={"\uD83D\uDCA0"}
            label="Causal Genes"
            accentClass="text-gene"
            borderClass="border-gene/20"
          >
            <div className="flex flex-wrap gap-1.5">
              {data.causal_genes.map((g, i) => (
                <span
                  key={i}
                  className="rounded-md border border-gene/20 bg-gene/5 px-2 py-1 text-xs font-mono text-gene"
                >
                  {g}
                </span>
              ))}
            </div>
          </Section>
        )}

        {data.key_cell_types.length > 0 && (
          <Section
            icon={"\uD83E\uDDEC"}
            label="Key Cell Types"
            accentClass="text-cell"
            borderClass="border-cell/20"
          >
            <ul className="space-y-1">
              {data.key_cell_types.map((c, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-gray-300"
                >
                  <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-cell opacity-70" />
                  {c}
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>

      {/* Validated Targets */}
      {data.validated_targets.length > 0 && (
        <Section
          icon={"\uD83C\uDFAF"}
          label="Validated Targets"
          accentClass="text-target"
          borderClass="border-target/20"
        >
          <div className="space-y-3">
            {data.validated_targets.map((vt, i) => (
              <div key={i}>
                <p className="text-sm font-medium text-gray-200">
                  {vt.target}
                </p>
                <p className="text-sm text-gray-400 mt-0.5">{vt.mechanism}</p>
                <PmidList pmids={vt.evidence_pmids} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Failed Targets */}
      {data.failed_targets.length > 0 && (
        <Section
          icon={"\u26A0\uFE0F"}
          label="Failed Targets"
          accentClass="text-red-400"
          borderClass="border-red-500/20"
        >
          <div className="space-y-3">
            {data.failed_targets.map((ft, i) => (
              <div key={i}>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-gray-200">
                    {ft.target}
                  </p>
                  <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-400 uppercase">
                    {ft.stage_failed}
                  </span>
                </div>
                <p className="text-sm text-gray-400 mt-0.5">
                  {ft.mechanistic_reason}
                </p>
                <PmidList pmids={ft.evidence_pmids} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Mechanistic Contradictions */}
      {data.mechanistic_contradictions.length > 0 && (
        <Section
          icon={"\u2753"}
          label="Mechanistic Contradictions"
          accentClass="text-hypothesis"
          borderClass="border-hypothesis/20"
        >
          <div className="space-y-3">
            {data.mechanistic_contradictions.map((mc, i) => (
              <div key={i}>
                <p className="text-sm text-gray-300">{mc.description}</p>
                <PmidList pmids={mc.evidence_pmids} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Grid: Biomarkers + Unresolved Questions */}
      <div className="grid gap-3 sm:grid-cols-2">
        {data.biomarkers.length > 0 && (
          <Section
            icon={"\uD83E\uDE78"}
            label="Biomarkers"
            accentClass="text-cytokine"
            borderClass="border-cytokine/20"
          >
            <div className="flex flex-wrap gap-1.5">
              {data.biomarkers.map((b, i) => (
                <span
                  key={i}
                  className="rounded-md border border-cytokine/20 bg-cytokine/5 px-2 py-1 text-xs text-cytokine"
                >
                  {b}
                </span>
              ))}
            </div>
          </Section>
        )}

        {data.unresolved_questions.length > 0 && (
          <Section
            icon={"\uD83D\uDD2C"}
            label="Unresolved Questions"
            accentClass="text-hypothesis"
            borderClass="border-hypothesis/20"
          >
            <ul className="space-y-1.5">
              {data.unresolved_questions.map((q, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-gray-300"
                >
                  <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-hypothesis opacity-70" />
                  {q}
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>

      {/* All Citations */}
      {data.all_citations.length > 0 && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-2">
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
