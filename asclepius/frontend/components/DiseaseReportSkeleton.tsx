"use client";

/** Shimmer skeleton for Disease Report and Target Risk loading states. */

function Shimmer({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-bg-3 ${className ?? ""}`}
      aria-hidden="true"
    />
  );
}

function Section({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Shimmer key={i} className={`h-3 ${i === rows - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

function TagRow({ count }: { count: number }) {
  const widths = ["w-16", "w-20", "w-14", "w-24", "w-18", "w-12"];
  return (
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <Shimmer key={i} className={`h-5 rounded-full ${widths[i % widths.length]}`} />
      ))}
    </div>
  );
}

interface Props {
  mode?: "disease-report" | "target-risk";
}

export default function DiseaseReportSkeleton({ mode = "disease-report" }: Props) {
  return (
    <div className="rounded-xl border border-line bg-bg-2 overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
        <Shimmer className="h-4 w-4 rounded" />
        <Shimmer className="h-4 w-40" />
        <div className="ml-auto">
          <Shimmer className="h-3 w-20" />
        </div>
      </div>

      <div className="p-5 space-y-6">
        {/* Summary block */}
        <Section rows={4} />

        {/* Score row (target-risk only) */}
        {mode === "target-risk" && (
          <div className="flex gap-3">
            <Shimmer className="h-16 flex-1 rounded-lg" />
            <Shimmer className="h-16 flex-1 rounded-lg" />
            <Shimmer className="h-16 flex-1 rounded-lg" />
          </div>
        )}

        {/* Tag clusters */}
        <div className="space-y-4">
          <div>
            <Shimmer className="mb-2 h-3 w-24" />
            <TagRow count={6} />
          </div>
          <div>
            <Shimmer className="mb-2 h-3 w-20" />
            <TagRow count={5} />
          </div>
          <div>
            <Shimmer className="mb-2 h-3 w-28" />
            <TagRow count={4} />
          </div>
        </div>

        {/* Pathway cards */}
        <div className="space-y-3">
          <Shimmer className="mb-2 h-3 w-24" />
          {[1, 2].map((n) => (
            <div key={n} className="rounded-lg border border-line p-3 space-y-2">
              <Shimmer className="h-3 w-1/2" />
              <Section rows={2} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
