"use client";

import { useState } from "react";
import type { TargetRiskResponse } from "@/lib/dmi-api";

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

function RiskGauge({
  label,
  subtitle,
  score,
  barColor,
}: {
  label: string;
  subtitle: string;
  score: number;
  barColor: string;
}) {
  const riskLevel = score >= 60 ? "HIGH" : score >= 30 ? "MODERATE" : "LOW";
  const riskColor = score >= 60 ? "text-red-400" : score >= 30 ? "text-yellow-400" : "text-green-400";
  const riskBg = score >= 60 ? "bg-red-500/10" : score >= 30 ? "bg-yellow-500/10" : "bg-green-500/10";
  const riskBorder = score >= 60 ? "border-red-500/20" : score >= 30 ? "border-yellow-500/20" : "border-green-500/20";

  return (
    <div className={`rounded-xl border ${riskBorder} ${riskBg} p-4`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-light">{label}</p>
          <p className="text-[10px] text-muted mt-0.5 leading-snug">{subtitle}</p>
        </div>
        <div className="text-right">
          <span className={`font-display tabular-nums ${riskColor}`} style={{ fontSize: 32 }}>{score}</span>
          <span className="text-muted text-xs">/100</span>
        </div>
      </div>
      <div className="h-2.5 rounded-full bg-surface-3/80 overflow-hidden mb-2">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-bold uppercase tracking-wider ${riskColor}`}>
          {riskLevel} RISK
        </span>
        <div className="flex gap-1 text-[9px] text-muted">
          <span>0</span>
          <span className="mx-1 text-muted-dim">·</span>
          <span>30</span>
          <span className="mx-1 text-muted-dim">·</span>
          <span>60</span>
          <span className="mx-1 text-muted-dim">·</span>
          <span>100</span>
        </div>
      </div>
    </div>
  );
}

function AttributeBadge({
  label,
  value,
  colorClass,
  tooltip,
}: {
  label: string;
  value: string;
  colorClass: string;
  tooltip: string;
}) {
  const [showTip, setShowTip] = useState(false);
  return (
    <div className="relative">
      <button
        className="flex flex-col items-center gap-1 rounded-lg border border-surface-3 bg-surface-2 px-3 py-2.5 text-center hover:border-surface-4 transition min-w-[90px]"
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
        type="button"
      >
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase ${colorClass}`}>
          {value}
        </span>
        <span className="text-[10px] text-muted">{label}</span>
      </button>
      {showTip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-10 w-48 rounded-lg border border-surface-4 bg-surface-0 px-3 py-2 text-[11px] text-gray-300 shadow-lg leading-relaxed">
          {tooltip}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-surface-0" />
        </div>
      )}
    </div>
  );
}

export default function TargetRiskCard({ data }: { data: TargetRiskResponse }) {
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

  const overallRiskColor =
    data.overall_risk_score >= 60
      ? "bg-red-500"
      : data.overall_risk_score >= 30
        ? "bg-yellow-500"
        : "bg-green-500";

  return (
    <div className="space-y-4">
      {/* Target header */}
      <div className="rounded-xl border border-accent-500/25 bg-accent-600/8 px-5 py-4" style={{ backgroundColor: "rgba(37, 99, 235, 0.05)" }}>
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent-600/15 text-2xl">
            🎯
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-display text-ink text-display-m">{data.target}</h3>
            <p className="text-sm text-muted mt-0.5">
              Therapeutic target risk assessment in <span className="text-ink-2 font-medium">{data.disease}</span>
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono uppercase text-faint mb-1" style={{ fontSize: 10, letterSpacing: "0.14em" }}>Overall Risk</p>
            <span className={`font-display tabular-nums ${data.overall_risk_score >= 60 ? "text-risk" : data.overall_risk_score >= 30 ? "text-amber" : "text-green"}`} style={{ fontSize: 52, lineHeight: 1 }}>
              {data.overall_risk_score}
            </span>
            <span className="text-muted text-sm">/100</span>
          </div>
        </div>

        {/* Attribute badges */}
        <div className="flex flex-wrap gap-2 mt-4">
          <AttributeBadge
            label="Pathway Position"
            value={data.pathway_position}
            colorClass={positionColor}
            tooltip="Upstream targets (closer to disease root cause) are generally more druggable but may have broader effects."
          />
          <AttributeBadge
            label="Redundancy"
            value={data.redundancy_level}
            colorClass={redundancyColor}
            tooltip="High redundancy means parallel pathways can compensate, reducing therapeutic impact. Low redundancy targets are harder to escape."
          />
          <AttributeBadge
            label="Biomarker Alignment"
            value={data.biomarker_alignment}
            colorClass={biomarkerColor}
            tooltip="Strong biomarker alignment means measurable endpoints exist to track target engagement and therapeutic response."
          />
        </div>
      </div>

      {/* Risk Score Gauges */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-2.5 px-0.5">Risk Score Breakdown</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <RiskGauge
            label="Mechanistic Risk"
            subtitle="Causal link to disease pathobiology"
            score={data.mechanistic_risk_score}
            barColor="bg-pathway"
          />
          <RiskGauge
            label="Translational Risk"
            subtitle="Likelihood of clinical success"
            score={data.translational_risk_score}
            barColor="bg-cytokine"
          />
          <RiskGauge
            label="Overall Risk"
            subtitle="Combined composite score"
            score={data.overall_risk_score}
            barColor={overallRiskColor}
          />
        </div>
      </div>

      {/* Risk Explanation */}
      {data.risk_explanation && (
        <div className="rounded-xl border border-surface-3 bg-surface-1 px-5 py-4">
          <div className="flex items-center gap-2 mb-2">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-400">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light">Risk Rationale</p>
          </div>
          <p className="text-sm leading-relaxed text-gray-300">{data.risk_explanation}</p>
        </div>
      )}

      {/* Historical Failures */}
      {data.historical_failures.length > 0 && (
        <div className="rounded-xl border border-red-500/20 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/8 border-b border-red-500/15" style={{ backgroundColor: "rgba(239, 68, 68, 0.05)" }}>
            <span className="text-base">⚠️</span>
            <p className="text-xs font-bold uppercase tracking-widest text-red-400">
              Historical Failures ({data.historical_failures.length})
            </p>
            <p className="text-[10px] text-muted ml-2">Clinical or preclinical programs that did not succeed</p>
          </div>
          <div className="px-4 py-4 bg-surface-1/50 space-y-4">
            {data.historical_failures.map((hf, i) => (
              <div key={i} className={`${i > 0 ? "pt-4 border-t border-surface-3" : ""}`}>
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 shrink-0 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-400 uppercase whitespace-nowrap">
                    {hf.failure_stage}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-100">{hf.program}</p>
                    <p className="text-sm text-gray-400 mt-1 leading-relaxed">{hf.reason}</p>
                    {hf.evidence_pmids.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {hf.evidence_pmids.map((p, j) => (
                          <PmidLink key={j} pmid={p} />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Citations */}
      {data.citations.length > 0 && (
        <div className="rounded-xl border border-surface-3 bg-surface-1 px-4 py-3">
          <div className="flex items-center gap-2 mb-2.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted-light">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14,2 14,8 20,8" />
            </svg>
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-light">
              Supporting Literature ({data.citations.length})
            </p>
          </div>
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
