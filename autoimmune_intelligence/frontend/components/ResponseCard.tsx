import type { QueryResponse, StructuredReasoning } from "@/lib/api";
import PubMedPanel from "./PubMedPanel";

interface ResponseCardProps {
  data: QueryResponse;
}

function formatPubMedLink(source: string): { text: string; href: string | null } {
  const pmidMatch = source.match(/PMID:\s*(\d+)/i);
  if (pmidMatch) {
    return {
      text: source,
      href: `https://pubmed.ncbi.nlm.nih.gov/${pmidMatch[1]}/`,
    };
  }
  return { text: source, href: null };
}

/* ------------------------------------------------------------------ */
/* Individual reasoning section                                       */
/* ------------------------------------------------------------------ */
function ReasoningSection({
  icon,
  label,
  items,
  accentClass,
  borderClass,
}: {
  icon: string;
  label: string;
  items: string[];
  accentClass: string;
  borderClass: string;
}) {
  if (!items.length) return null;
  return (
    <div className={`rounded-lg border ${borderClass} bg-surface-2 p-4`}>
      <h3 className={`mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest ${accentClass}`}>
        <span className="text-base">{icon}</span>
        {label}
      </h3>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-gray-300">
            <span className={`mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${accentClass.replace("text-", "bg-")} opacity-70`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Causal network section                                              */
/* ------------------------------------------------------------------ */
function CausalNetworkSection({ graphContext }: { graphContext: QueryResponse["graph_context"] }) {
  if (!graphContext?.causal_downstream?.length) return null;
  return (
    <div className="rounded-lg border border-accent-500/20 bg-surface-2 p-4">
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-accent-400">
        <span className="text-base">{"\u26A1"}</span>
        Causal Network Impact
      </h3>
      <div className="space-y-1.5">
        {graphContext.causal_downstream.slice(0, 8).map((item, i) => {
          const barWidth = Math.min(Math.abs(item.score) * 100, 100);
          return (
            <div key={i} className="flex items-center gap-3">
              <span className="w-24 text-xs text-gray-300 font-mono truncate">{item.node}</span>
              <div className="flex-1 h-2 rounded-full bg-surface-3 overflow-hidden">
                <div
                  className={`h-full rounded-full ${item.score >= 0 ? "bg-accent-500" : "bg-red-500"}`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
              <span className="text-[10px] text-muted font-mono w-12 text-right">
                {item.score.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>
      {graphContext.node_count > 0 && (
        <p className="mt-2 text-[10px] text-muted">
          Graph: {graphContext.node_count} nodes, {graphContext.edge_count} edges
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main response card                                                 */
/* ------------------------------------------------------------------ */
export default function ResponseCard({ data }: ResponseCardProps) {
  const r: StructuredReasoning | undefined = data.reasoning;
  const hasReasoning =
    r &&
    (r.key_cells.length > 0 ||
      r.key_cytokines.length > 0 ||
      r.pathways.length > 0 ||
      r.therapeutic_targets.length > 0 ||
      r.open_questions.length > 0 ||
      r.genes.length > 0);

  return (
    <div className="space-y-3">
      {/* Disease context banner */}
      {r?.disease_context && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-1.5">
            Disease Context
          </p>
          <p className="text-sm leading-relaxed text-gray-300">
            {r.disease_context}
          </p>
        </div>
      )}

      {/* Summary narrative */}
      {r?.summary && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-1.5">
            Mechanistic Summary
          </p>
          <p className="text-sm leading-relaxed text-gray-300 whitespace-pre-wrap">
            {r.summary}
          </p>
        </div>
      )}

      {/* Structured reasoning grid */}
      {hasReasoning && (
        <div className="grid gap-3 sm:grid-cols-2">
          <ReasoningSection
            icon={"\uD83E\uDDEC"}
            label="Key Immune Cells"
            items={r.key_cells}
            accentClass="text-cell"
            borderClass="border-cell/20"
          />
          <ReasoningSection
            icon={"\uD83D\uDD25"}
            label="Cytokines"
            items={r.key_cytokines}
            accentClass="text-cytokine"
            borderClass="border-cytokine/20"
          />
          <ReasoningSection
            icon={"\uD83E\uDDE0"}
            label="Dysregulated Pathways"
            items={r.pathways}
            accentClass="text-pathway"
            borderClass="border-pathway/20"
          />
          <ReasoningSection
            icon={"\uD83D\uDCA0"}
            label="Genetic Risk Loci"
            items={r.genes}
            accentClass="text-gene"
            borderClass="border-gene/20"
          />
          <ReasoningSection
            icon={"\uD83D\uDC8A"}
            label="Therapeutic Targets"
            items={r.therapeutic_targets}
            accentClass="text-target"
            borderClass="border-target/20"
          />
          <ReasoningSection
            icon={"\u2753"}
            label="Open Hypotheses"
            items={r.open_questions}
            accentClass="text-hypothesis"
            borderClass="border-hypothesis/20"
          />
        </div>
      )}

      {/* Causal network context */}
      <CausalNetworkSection graphContext={data.graph_context} />

      {/* PubMed articles */}
      {data.pubmed_articles && data.pubmed_articles.length > 0 && (
        <PubMedPanel articles={data.pubmed_articles} />
      )}

      {/* Sources */}
      {data.sources.length > 0 && (
        <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-2">
            Literature References
          </p>
          <div className="flex flex-wrap gap-2">
            {data.sources.map((src, i) => {
              const { text, href } = formatPubMedLink(src);
              return href ? (
                <a
                  key={i}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block rounded-md border border-surface-4 bg-surface-2 px-2.5 py-1 text-xs text-accent-400 transition hover:border-accent-500/40 hover:text-accent-300"
                >
                  {text}
                </a>
              ) : (
                <span
                  key={i}
                  className="inline-block rounded-md border border-surface-4 bg-surface-2 px-2.5 py-1 text-xs text-muted-light"
                >
                  {text}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
