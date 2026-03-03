import { useState } from "react";
import type { HypothesisResponse, Hypothesis } from "@/lib/api";

interface HypothesisCardProps {
  data: HypothesisResponse;
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const colors: Record<string, string> = {
    High: "bg-green-500/20 text-green-400 border-green-500/30",
    "Medium-High": "bg-blue-500/20 text-blue-400 border-blue-500/30",
    Medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    Low: "bg-red-500/20 text-red-400 border-red-500/30",
  };
  const cls = colors[confidence] || colors["Medium"];
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${cls}`}>
      {confidence}
    </span>
  );
}

function CategoryBadge({ category }: { category: string }) {
  const colors: Record<string, string> = {
    "Target Discovery": "bg-accent-600/20 text-accent-400",
    "Drug Repurposing": "bg-purple-500/20 text-purple-400",
    "Network Mechanism": "bg-cyan-500/20 text-cyan-400",
    "Genetic Mechanism": "bg-gene/20 text-gene",
    "Combination Therapy": "bg-target/20 text-target",
  };
  const cls = colors[category] || "bg-surface-3 text-muted-light";
  return (
    <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${cls}`}>
      {category}
    </span>
  );
}

function SingleHypothesis({ h, index }: { h: Hypothesis; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-surface-4 bg-surface-1 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 text-left hover:bg-surface-2 transition"
      >
        <div className="flex items-start gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent-600/20 text-xs font-bold text-accent-400 mt-0.5">
            {index + 1}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-100 leading-relaxed">
              {h.hypothesis}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <CategoryBadge category={h.category} />
              <ConfidenceBadge confidence={h.confidence} />
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
        <div className="border-t border-surface-3 px-4 py-4 space-y-4">
          {/* Rationale */}
          <div>
            <h5 className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-1">
              Rationale
            </h5>
            <p className="text-sm text-gray-300 leading-relaxed">{h.rationale}</p>
          </div>

          {/* Experimental Design */}
          <div className="rounded-lg border border-surface-3 bg-surface-2 p-3 space-y-2">
            <h5 className="text-xs font-semibold uppercase tracking-widest text-accent-400">
              Experimental Design
            </h5>
            <div className="grid gap-2 sm:grid-cols-2 text-sm">
              <div>
                <span className="text-xs text-muted-light font-medium">Model: </span>
                <span className="text-gray-300">{h.experimental_design.model}</span>
              </div>
              <div>
                <span className="text-xs text-muted-light font-medium">Timeline: </span>
                <span className="text-gray-300">{h.experimental_design.timeline}</span>
              </div>
            </div>
            <div>
              <span className="text-xs text-muted-light font-medium">Intervention: </span>
              <span className="text-sm text-gray-300">{h.experimental_design.intervention}</span>
            </div>
            {h.experimental_design.readouts.length > 0 && (
              <div>
                <span className="text-xs text-muted-light font-medium">Readouts:</span>
                <ul className="mt-1 space-y-0.5">
                  {h.experimental_design.readouts.map((r, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-400">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-accent-400/60" />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {h.experimental_design.controls.length > 0 && (
              <div>
                <span className="text-xs text-muted-light font-medium">Controls:</span>
                <ul className="mt-1 space-y-0.5">
                  {h.experimental_design.controls.map((c, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-400">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-gray-500" />
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
              <div className="rounded-lg border border-surface-3 bg-surface-2 p-3">
                <h5 className="text-xs font-semibold uppercase tracking-widest text-cell mb-1.5">
                  Biomarkers
                </h5>
                <ul className="space-y-0.5">
                  {h.biomarkers.map((b, i) => (
                    <li key={i} className="text-xs text-gray-400 flex items-start gap-1.5">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-cell/60" />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {h.confounders.length > 0 && (
              <div className="rounded-lg border border-surface-3 bg-surface-2 p-3">
                <h5 className="text-xs font-semibold uppercase tracking-widest text-yellow-400 mb-1.5">
                  Confounders
                </h5>
                <ul className="space-y-0.5">
                  {h.confounders.map((c, i) => (
                    <li key={i} className="text-xs text-gray-400 flex items-start gap-1.5">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-yellow-400/60" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function HypothesisCard({ data }: HypothesisCardProps) {
  return (
    <div className="space-y-3">
      {/* Context banner */}
      <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-2">
          Evidence Context
        </p>
        <div className="flex flex-wrap gap-3 text-xs text-gray-400">
          {data.context.diseases_matched.length > 0 && (
            <span>Diseases: <span className="text-gray-300">{data.context.diseases_matched.join(", ")}</span></span>
          )}
          {data.context.pathways_matched.length > 0 && (
            <span>Pathways: <span className="text-gray-300">{data.context.pathways_matched.join(", ")}</span></span>
          )}
          {data.context.therapeutics_matched.length > 0 && (
            <span>Therapeutics: <span className="text-gray-300">{data.context.therapeutics_matched.join(", ")}</span></span>
          )}
        </div>
      </div>

      {/* Hypotheses */}
      <div className="space-y-2">
        {data.hypotheses.map((h, i) => (
          <SingleHypothesis key={i} h={h} index={i} />
        ))}
      </div>

      {data.total_generated === 0 && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-6 text-center">
          <p className="text-sm text-muted">
            No hypotheses could be generated for this topic. Try a more specific
            query involving a disease, pathway, or therapeutic target.
          </p>
        </div>
      )}
    </div>
  );
}
