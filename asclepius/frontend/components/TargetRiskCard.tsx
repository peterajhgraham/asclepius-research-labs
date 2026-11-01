"use client";

import type { TargetRiskResponse } from "@/lib/dmi-api";
import { PmidList, Section } from "@/components/report-ui";

type Level = "low" | "moderate" | "high";

function levelOf(score: number): Level {
  return score >= 60 ? "high" : score >= 30 ? "moderate" : "low";
}

const LEVEL_TEXT: Record<Level, string> = { low: "text-green", moderate: "text-amber", high: "text-risk" };
const LEVEL_BAR: Record<Level, string> = { low: "bg-green", moderate: "bg-amber", high: "bg-risk" };

// One score as a row: label, a thin bar, the number. Colour carries only the level.
function ScoreRow({ label, hint, score }: { label: string; hint: string; score: number }) {
  const level = levelOf(score);
  return (
    <div title={hint} className="grid grid-cols-[9.5rem_1fr_2.5rem] items-center gap-4 py-1.5">
      <span className="text-sm text-ink-2">{label}</span>
      <div className="h-1 overflow-hidden rounded-full bg-bg-3">
        <div
          className={`h-full rounded-full transition-all duration-700 ${LEVEL_BAR[level]}`}
          style={{ width: `${Math.max(2, Math.min(100, score))}%` }}
        />
      </div>
      <span className="text-right text-sm tabular-nums text-ink">{score}</span>
    </div>
  );
}

// A labelled attribute whose value is tinted by what it implies for risk.
function Attribute({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone: "good" | "watch" | "bad";
  hint: string;
}) {
  const dot = tone === "good" ? "bg-green" : tone === "bad" ? "bg-risk" : "bg-amber";
  return (
    <div title={hint}>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 flex items-center gap-2 text-sm capitalize text-ink">
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
        {value}
      </p>
    </div>
  );
}

export default function TargetRiskCard({ data }: { data: TargetRiskResponse }) {
  const position =
    data.pathway_position === "upstream" ? "good" : data.pathway_position === "downstream" ? "bad" : "watch";
  const redundancy =
    data.redundancy_level === "low" ? "good" : data.redundancy_level === "high" ? "bad" : "watch";
  const biomarkers =
    data.biomarker_alignment === "strong" ? "good" : data.biomarker_alignment === "weak" ? "bad" : "watch";
  const overall = levelOf(data.overall_risk_score);

  return (
    <div>
      <div className="flex items-start justify-between gap-6 pb-6">
        <div className="min-w-0">
          <h3 className="text-xl font-medium tracking-tight text-ink">{data.target}</h3>
          <p className="mt-1 text-sm text-muted">
            Risk assessment in <span className="text-ink-2">{data.disease}</span>
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-3xl font-medium leading-none tabular-nums text-ink">
            {data.overall_risk_score}
            <span className="ml-1 text-sm font-normal text-faint">/100</span>
          </p>
          <p className={`mt-1.5 text-xs ${LEVEL_TEXT[overall]}`}>
            {overall === "moderate" ? "Moderate risk" : overall === "high" ? "High risk" : "Low risk"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 border-t border-line py-5">
        <Attribute
          label="Pathway position"
          value={data.pathway_position}
          tone={position}
          hint="Upstream targets (closer to the root cause) are generally more druggable but may have broader effects."
        />
        <Attribute
          label="Redundancy"
          value={data.redundancy_level}
          tone={redundancy}
          hint="High redundancy means parallel pathways can compensate, reducing therapeutic impact."
        />
        <Attribute
          label="Biomarker alignment"
          value={data.biomarker_alignment}
          tone={biomarkers}
          hint="Strong alignment means measurable endpoints exist to track target engagement and response."
        />
      </div>

      <div className="border-t border-line py-5">
        <ScoreRow label="Mechanistic risk" hint="Causal link to disease pathobiology" score={data.mechanistic_risk_score} />
        <ScoreRow label="Translational risk" hint="Likelihood of clinical success" score={data.translational_risk_score} />
        <ScoreRow label="Overall risk" hint="Combined composite score" score={data.overall_risk_score} />
      </div>

      {data.risk_explanation && (
        <Section label="Rationale">
          <p className="text-sm leading-relaxed text-ink-2">{data.risk_explanation}</p>
        </Section>
      )}

      {(data.historical_failures ?? []).length > 0 && (
        <Section label="Historical failures" count={data.historical_failures.length}>
          <div className="space-y-5">
            {data.historical_failures.map((hf, i) => (
              <div key={i}>
                <p className="text-sm font-medium text-ink">
                  {hf.program}
                  <span className="ml-2 text-xs font-normal text-muted">{hf.failure_stage}</span>
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{hf.reason}</p>
                <PmidList pmids={hf.evidence_pmids} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {(data.citations ?? []).length > 0 && (
        <Section label="Citations" count={data.citations.length} defaultOpen={false}>
          <PmidList pmids={data.citations} />
        </Section>
      )}
    </div>
  );
}
