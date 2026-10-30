"use client";

import type { DiseaseReportResponse } from "@/lib/dmi-api";
import { PmidList, Section, Tag, PmidLink } from "@/components/report-ui";

// A named item with a description and supporting citations (pathways, targets).
function EvidenceItem({
  tag,
  title,
  body,
  pmids,
}: {
  tag?: string;
  title: string;
  body: string;
  pmids: string[];
}) {
  return (
    <div>
      <p className="text-sm font-medium text-ink">
        {title}
        {tag && <span className="ml-2 text-xs font-normal text-muted">{tag}</span>}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
      <PmidList pmids={pmids} />
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="text-sm leading-relaxed text-ink-2">
          {item}
        </li>
      ))}
    </ul>
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
    <div>
      {data.disease_summary && (
        <p className="pb-6 text-[15px] leading-relaxed text-ink">{data.disease_summary}</p>
      )}

      {data.core_pathways.length > 0 && (
        <Section label="Core pathways" count={data.core_pathways.length}>
          <div className="space-y-5">
            {data.core_pathways.map((pw, i) => (
              <EvidenceItem key={i} title={pw.name} body={pw.description} pmids={pw.evidence_pmids} />
            ))}
          </div>
        </Section>
      )}

      {data.validated_targets.length > 0 && (
        <Section label="Validated targets" count={data.validated_targets.length}>
          <div className="space-y-5">
            {data.validated_targets.map((vt, i) => (
              <EvidenceItem key={i} title={vt.target} body={vt.mechanism} pmids={vt.evidence_pmids} />
            ))}
          </div>
        </Section>
      )}

      {data.failed_targets.length > 0 && (
        <Section label="Failed targets" count={data.failed_targets.length} defaultOpen={false}>
          <div className="space-y-5">
            {data.failed_targets.map((ft, i) => (
              <EvidenceItem
                key={i}
                title={ft.target}
                tag={ft.stage_failed}
                body={ft.mechanistic_reason}
                pmids={ft.evidence_pmids}
              />
            ))}
          </div>
        </Section>
      )}

      {data.mechanistic_contradictions.length > 0 && (
        <Section label="Mechanistic contradictions" count={data.mechanistic_contradictions.length} defaultOpen={false}>
          <div className="space-y-5">
            {data.mechanistic_contradictions.map((mc, i) => (
              <div key={i}>
                <p className="text-sm leading-relaxed text-ink-2">{mc.description}</p>
                <PmidList pmids={mc.evidence_pmids} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.causal_genes.length > 0 && (
        <Section label="Causal genes" count={data.causal_genes.length}>
          <div className="flex flex-wrap gap-1.5">
            {data.causal_genes.map((g, i) => (
              <Tag key={i}>{g}</Tag>
            ))}
          </div>
        </Section>
      )}

      {data.key_cell_types.length > 0 && (
        <Section label="Key cell types" count={data.key_cell_types.length}>
          <BulletList items={data.key_cell_types} />
        </Section>
      )}

      {data.biomarkers.length > 0 && (
        <Section label="Biomarkers" count={data.biomarkers.length}>
          <div className="flex flex-wrap gap-1.5">
            {data.biomarkers.map((b, i) => (
              <Tag key={i}>{b}</Tag>
            ))}
          </div>
        </Section>
      )}

      {data.unresolved_questions.length > 0 && (
        <Section label="Open questions" count={data.unresolved_questions.length}>
          <BulletList items={data.unresolved_questions} />
        </Section>
      )}

      {data.all_citations.length > 0 && (
        <Section label="Citations" count={data.all_citations.length} defaultOpen={false}>
          <div className="flex flex-wrap gap-1.5">
            {data.all_citations.map((pmid, i) => (
              <PmidLink key={i} pmid={pmid} />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
