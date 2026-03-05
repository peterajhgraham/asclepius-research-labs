import type { TargetRiskResponse } from "@/lib/dmi-api";

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

function RiskGauge({
  label,
  score,
  color,
}: {
  label: string;
  score: number;
  color: string;
}) {
  const riskLevel =
    score >= 60 ? "HIGH" : score >= 30 ? "MODERATE" : "LOW";
  const riskColor =
    score >= 60
      ? "text-red-400"
      : score >= 30
        ? "text-yellow-400"
        : "text-green-400";

  return (
    <div className="rounded-lg border border-surface-4 bg-surface-2 p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-light">
          {label}
        </p>
        <span className={`text-lg font-bold font-mono ${riskColor}`}>
          {score}
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-surface-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <p className={`mt-1.5 text-[10px] font-semibold uppercase ${riskColor}`}>
        {riskLevel} RISK
      </p>
    </div>
  );
}

function Badge({
  label,
  value,
  colorClass,
}: {
  label: string;
  value: string;
  colorClass: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-light">{label}:</span>
      <span
        className={`rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase ${colorClass}`}
      >
        {value}
      </span>
    </div>
  );
}

export default function TargetRiskCard({
  data,
}: {
  data: TargetRiskResponse;
}) {
  const positionColor =
    data.pathway_position === "upstream"
      ? "bg-green-500/15 text-green-400"
      : data.pathway_position === "downstream"
        ? "bg-red-500/15 text-red-400"
        : "bg-yellow-500/15 text-yellow-400";

  const redundancyColor =
    data.redundancy_level === "low"
      ? "bg-green-500/15 text-green-400"
      : data.redundancy_level === "high"
        ? "bg-red-500/15 text-red-400"
        : "bg-yellow-500/15 text-yellow-400";

  const biomarkerColor =
    data.biomarker_alignment === "strong"
      ? "bg-green-500/15 text-green-400"
      : data.biomarker_alignment === "weak"
        ? "bg-red-500/15 text-red-400"
        : "bg-yellow-500/15 text-yellow-400";

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="rounded-lg border border-accent-500/20 bg-surface-1 px-4 py-3">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-lg">{"\uD83C\uDFAF"}</span>
          <div>
            <h3 className="text-base font-semibold text-gray-100">
              {data.target}
            </h3>
            <p className="text-xs text-muted-light">
              Target risk assessment for {data.disease}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3 mt-3">
          <Badge
            label="Pathway"
            value={data.pathway_position}
            colorClass={positionColor}
          />
          <Badge
            label="Redundancy"
            value={data.redundancy_level}
            colorClass={redundancyColor}
          />
          <Badge
            label="Biomarker"
            value={data.biomarker_alignment}
            colorClass={biomarkerColor}
          />
        </div>
      </div>

      {/* Risk Scores */}
      <div className="grid gap-3 sm:grid-cols-3">
        <RiskGauge
          label="Mechanistic Risk"
          score={data.mechanistic_risk_score}
          color="bg-pathway"
        />
        <RiskGauge
          label="Translational Risk"
          score={data.translational_risk_score}
          color="bg-cytokine"
        />
        <RiskGauge
          label="Overall Risk"
          score={data.overall_risk_score}
          color={
            data.overall_risk_score >= 60
              ? "bg-red-500"
              : data.overall_risk_score >= 30
                ? "bg-yellow-500"
                : "bg-green-500"
          }
        />
      </div>

      {/* Risk Explanation */}
      {data.risk_explanation && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-1.5">
            Risk Explanation
          </p>
          <p className="text-sm leading-relaxed text-gray-300">
            {data.risk_explanation}
          </p>
        </div>
      )}

      {/* Historical Failures */}
      {data.historical_failures.length > 0 && (
        <div className="rounded-lg border border-red-500/20 bg-surface-2 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-red-400">
            <span className="text-base">{"\u26A0\uFE0F"}</span>
            Historical Failures ({data.historical_failures.length})
          </h3>
          <div className="space-y-3">
            {data.historical_failures.map((hf, i) => (
              <div key={i}>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-gray-200">
                    {hf.program}
                  </p>
                  <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-400 uppercase">
                    {hf.failure_stage}
                  </span>
                </div>
                <p className="text-sm text-gray-400 mt-0.5">{hf.reason}</p>
                {hf.evidence_pmids.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {hf.evidence_pmids.map((p, j) => (
                      <PmidLink key={j} pmid={p} />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Citations */}
      {data.citations.length > 0 && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-2">
            Citations ({data.citations.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.citations.map((pmid, i) => (
              <PmidLink key={i} pmid={pmid} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
