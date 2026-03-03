import type { CompareResponse, Overlaps } from "@/lib/api";

interface CompareCardProps {
  data: CompareResponse;
}

function OverlapSection({
  label,
  shared,
  uniqueA,
  uniqueB,
  nameA,
  nameB,
  accentClass,
}: {
  label: string;
  shared: string[];
  uniqueA: string[];
  uniqueB: string[];
  nameA: string;
  nameB: string;
  accentClass: string;
}) {
  if (!shared.length && !uniqueA.length && !uniqueB.length) return null;
  return (
    <div className="rounded-lg border border-surface-4 bg-surface-2 p-4">
      <h4 className={`mb-3 text-xs font-semibold uppercase tracking-widest ${accentClass}`}>
        {label}
      </h4>
      {shared.length > 0 && (
        <div className="mb-2">
          <span className="text-xs text-muted-light font-medium">Shared: </span>
          <span className="text-sm text-gray-300">{shared.join(", ")}</span>
        </div>
      )}
      {uniqueA.length > 0 && (
        <div className="mb-1">
          <span className="text-xs text-blue-400 font-medium">Only {nameA}: </span>
          <span className="text-sm text-gray-400">{uniqueA.join(", ")}</span>
        </div>
      )}
      {uniqueB.length > 0 && (
        <div>
          <span className="text-xs text-purple-400 font-medium">Only {nameB}: </span>
          <span className="text-sm text-gray-400">{uniqueB.join(", ")}</span>
        </div>
      )}
    </div>
  );
}

export default function CompareCard({ data }: CompareCardProps) {
  const { disease_a: a, disease_b: b, overlaps: o, similarity_score, summary } = data;
  const pct = Math.round(similarity_score * 100);

  return (
    <div className="space-y-4">
      {/* Header with similarity score */}
      <div className="rounded-lg border border-accent-500/30 bg-accent-600/10 px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-gray-100">
            {a.disease_name} vs {b.disease_name}
          </h3>
          <span className="rounded-full bg-accent-600/20 px-3 py-1 text-xs font-bold text-accent-400">
            {pct}% similar
          </span>
        </div>
        {/* Similarity bar */}
        <div className="h-2 rounded-full bg-surface-3 overflow-hidden">
          <div
            className="h-full rounded-full bg-accent-500 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Summary */}
      <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-2">
          Comparison Summary
        </p>
        <p className="text-sm leading-relaxed text-gray-300 whitespace-pre-wrap">
          {summary}
        </p>
      </div>

      {/* Side-by-side disease profiles */}
      <div className="grid gap-4 md:grid-cols-2">
        {[a, b].map((disease, idx) => (
          <div
            key={disease.disease_name}
            className={`rounded-lg border ${idx === 0 ? "border-blue-500/20" : "border-purple-500/20"} bg-surface-1 p-4`}
          >
            <h4 className={`text-sm font-semibold mb-2 ${idx === 0 ? "text-blue-400" : "text-purple-400"}`}>
              {disease.disease_name}
            </h4>
            <p className="text-xs text-gray-400 mb-3">{disease.description.slice(0, 200)}...</p>
            {disease.prevalence && (
              <p className="text-xs text-muted-light mb-2">Prevalence: {disease.prevalence}</p>
            )}
            <div className="space-y-1.5">
              {disease.key_cell_types.length > 0 && (
                <p className="text-xs text-gray-400">
                  <span className="text-cell font-medium">Cells:</span> {disease.key_cell_types.slice(0, 4).join(", ")}
                </p>
              )}
              {disease.cytokines.length > 0 && (
                <p className="text-xs text-gray-400">
                  <span className="text-cytokine font-medium">Cytokines:</span> {disease.cytokines.slice(0, 5).join(", ")}
                </p>
              )}
              {disease.associated_genes.length > 0 && (
                <p className="text-xs text-gray-400">
                  <span className="text-gene font-medium">Top genes:</span>{" "}
                  {disease.associated_genes.slice(0, 4).map((g) => g.gene).join(", ")}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Overlap analysis */}
      <div className="grid gap-3 sm:grid-cols-2">
        <OverlapSection
          label="Pathways"
          shared={o.shared_pathways}
          uniqueA={o.unique_pathways_a}
          uniqueB={o.unique_pathways_b}
          nameA={a.disease_name}
          nameB={b.disease_name}
          accentClass="text-pathway"
        />
        <OverlapSection
          label="Cytokines"
          shared={o.shared_cytokines}
          uniqueA={o.unique_cytokines_a}
          uniqueB={o.unique_cytokines_b}
          nameA={a.disease_name}
          nameB={b.disease_name}
          accentClass="text-cytokine"
        />
        <OverlapSection
          label="Immune Cells"
          shared={o.shared_cell_types}
          uniqueA={o.unique_cell_types_a}
          uniqueB={o.unique_cell_types_b}
          nameA={a.disease_name}
          nameB={b.disease_name}
          accentClass="text-cell"
        />
        <OverlapSection
          label="Genetic Risk Loci"
          shared={o.shared_genes}
          uniqueA={o.unique_genes_a}
          uniqueB={o.unique_genes_b}
          nameA={a.disease_name}
          nameB={b.disease_name}
          accentClass="text-gene"
        />
        <OverlapSection
          label="Therapeutics"
          shared={o.shared_therapeutics}
          uniqueA={o.unique_therapeutics_a}
          uniqueB={o.unique_therapeutics_b}
          nameA={a.disease_name}
          nameB={b.disease_name}
          accentClass="text-target"
        />
        <OverlapSection
          label="Mechanisms"
          shared={o.shared_mechanisms}
          uniqueA={o.unique_mechanisms_a}
          uniqueB={o.unique_mechanisms_b}
          nameA={a.disease_name}
          nameB={b.disease_name}
          accentClass="text-hypothesis"
        />
      </div>
    </div>
  );
}
