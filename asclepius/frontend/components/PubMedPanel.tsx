import type { PubMedArticle } from "@/lib/api";

interface PubMedPanelProps {
  articles: PubMedArticle[];
}

export default function PubMedPanel({ articles }: PubMedPanelProps) {
  if (!articles.length) return null;

  return (
    <div className="rounded-lg border border-surface-4 bg-surface-1 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-light mb-3">
        Live PubMed Results ({articles.length})
      </p>
      <div className="space-y-2">
        {articles.map((article) => (
          <div
            key={article.pmid}
            className="rounded-md border border-surface-3 bg-surface-2 px-3 py-2.5"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-accent-400 hover:text-accent-300 transition leading-snug"
                >
                  {article.title}
                </a>
                <p className="mt-1 text-xs text-muted">
                  {article.authors.slice(0, 3).join(", ")}
                  {article.authors.length > 3 && " et al."}
                  {article.year && ` (${article.year})`}
                  {article.journal && `. ${article.journal}`}
                </p>
                {article.abstract && (
                  <p className="mt-1.5 text-xs text-gray-400 leading-relaxed line-clamp-2">
                    {article.abstract}
                  </p>
                )}
              </div>
              <span className="shrink-0 rounded border border-surface-4 bg-surface-1 px-2 py-0.5 text-[10px] text-muted-light">
                PMID:{article.pmid}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
