"use client";

import type { Mode } from "@/lib/types";

export const MODE_CONFIG: Record<Mode, { label: string; description: string; group: "dmi" | "legacy" }> = {
  "disease-report": { label: "Mechanism Report", description: "Map disease biology from literature",        group: "dmi" },
  "target-risk":    { label: "Target Risk",       description: "Score therapeutic target tractability",     group: "dmi" },
  standard:         { label: "Analyze",           description: "Real-time scientific reasoning",            group: "legacy" },
  research:         { label: "Research Agent",    description: "Multi-hop agent: retriever + PubMed + graph as tools (slower)", group: "legacy" },
  compare:          { label: "Compare",           description: "Side-by-side biological comparison",        group: "legacy" },
  hypothesis:       { label: "Hypothesize",       description: "Generate testable experimental hypotheses", group: "legacy" },
};

export const ALL_MODES: Mode[] = ["disease-report", "target-risk", "standard", "research", "compare", "hypothesis"];

interface Props {
  mode: Mode;
  onModeChange: (m: Mode) => void;
}

export default function ModeSwitcher({ mode, onModeChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-0.5 rounded-lg border border-surface-3 bg-surface-1 p-0.5">
      {ALL_MODES.map((m) => {
        const active = mode === m;
        return (
          <div key={m} className="relative group shrink-0">
            <button
              type="button"
              onClick={() => onModeChange(m)}
              aria-label={MODE_CONFIG[m].description}
              className={`
                relative rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-all
                ${active
                  ? "bg-surface-3 text-gray-100 shadow-sm"
                  : "text-muted hover:text-gray-300"
                }
              `}
            >
              {MODE_CONFIG[m].label}
            </button>
            <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
              <div className="rounded-md border border-surface-3 bg-surface-0 px-2.5 py-1.5 text-[11px] text-gray-400 whitespace-nowrap shadow-xl">
                {MODE_CONFIG[m].description}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
