"use client";

import { useState, useRef, useEffect, type FormEvent } from "react";
import { submitQuery, type QueryResponse } from "@/lib/api";
import ResponseCard from "@/components/ResponseCard";

interface ConversationEntry {
  question: string;
  response: QueryResponse | null;
  loading: boolean;
  error: string | null;
}

const EXAMPLE_PROMPTS = [
  "Rheumatoid arthritis cytokine pathways",
  "JAK-STAT dysregulation in lupus",
  "T cell exhaustion in autoimmunity",
  "IL-23/IL-17 axis in psoriasis",
  "TNF signaling and therapeutic targets",
  "Multiple sclerosis pathogenesis",
];

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  async function handleSubmit(e?: FormEvent<HTMLFormElement>) {
    if (e) e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    const idx = entries.length;
    const entry: ConversationEntry = {
      question: trimmed,
      response: null,
      loading: true,
      error: null,
    };

    setEntries((prev) => [...prev, entry]);
    setQuestion("");
    setLoading(true);

    try {
      const result = await submitQuery({ question: trimmed });
      setEntries((prev) =>
        prev.map((e, i) =>
          i === idx ? { ...e, response: result, loading: false } : e
        )
      );
    } catch (err: unknown) {
      let detail = "Unable to reach the analysis service.";
      if (err && typeof err === "object" && "response" in err) {
        const res = (err as { response?: { data?: { error?: string } } }).response;
        if (res?.data?.error) detail = res.data.error;
      }
      setEntries((prev) =>
        prev.map((e, i) =>
          i === idx ? { ...e, error: detail, loading: false } : e
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const isEmpty = entries.length === 0;

  return (
    <main className="flex min-h-screen flex-col bg-surface-0">
      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-surface-3 bg-surface-0/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-600/20 text-accent-400">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-100 tracking-tight">
                Autoimmune Intelligence
              </h1>
              <p className="text-xs text-muted">
                Immune reasoning copilot
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden sm:inline-block rounded-full border border-surface-4 px-3 py-1 text-xs text-muted">
              {entries.length} {entries.length === 1 ? "query" : "queries"}
            </span>
          </div>
        </div>
      </header>

      {/* Content area */}
      <div className="flex-1">
        {/* Empty state */}
        {isEmpty && (
          <div className="mx-auto flex max-w-3xl flex-col items-center px-6 pt-24 pb-8">
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-600/10 text-accent-400">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-gray-100 sm:text-3xl">
              Autoimmune Intelligence
            </h2>
            <p className="mt-2 text-center text-sm text-muted max-w-md">
              Structured immune reasoning for hypothesis generation.
              Ask about disease mechanisms, cytokine networks, pathways, or therapeutics.
            </p>

            <div className="mt-10 w-full max-w-lg">
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-dim">
                Try a query
              </p>
              <div className="grid grid-cols-2 gap-2">
                {EXAMPLE_PROMPTS.map((example) => (
                  <button
                    key={example}
                    onClick={() => setQuestion(example)}
                    className="rounded-lg border border-surface-3 bg-surface-1 px-3 py-2.5 text-left text-sm text-gray-300 transition hover:border-surface-4 hover:bg-surface-2 hover:text-gray-100"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {!isEmpty && (
          <div className="mx-auto max-w-5xl px-6 py-8 space-y-8">
            {entries.map((entry, idx) => (
              <div key={idx}>
                {/* User query */}
                <div className="mb-4 flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent-600/20 text-xs font-semibold text-accent-400">
                    Q
                  </div>
                  <p className="pt-0.5 text-sm font-medium text-gray-100">
                    {entry.question}
                  </p>
                </div>

                {/* Loading state */}
                {entry.loading && (
                  <div className="ml-10 flex items-center gap-3 rounded-lg border border-surface-3 bg-surface-1 px-4 py-3">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
                    <span className="animate-pulse text-sm text-muted-light">
                      Reasoning across datasets...
                    </span>
                  </div>
                )}

                {/* Error state */}
                {entry.error && (
                  <div className="ml-10 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                    {entry.error}
                  </div>
                )}

                {/* Response */}
                {entry.response && (
                  <div className="ml-10">
                    <ResponseCard data={entry.response} />
                  </div>
                )}
              </div>
            ))}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area — sticky bottom */}
      <div className="sticky bottom-0 border-t border-surface-3 bg-surface-0/90 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="mx-auto max-w-5xl px-6 py-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about a disease mechanism, pathway, or therapeutic target..."
              disabled={loading}
              className="flex-1 rounded-lg border border-surface-3 bg-surface-1 px-4 py-3 text-sm text-gray-100 placeholder-muted outline-none transition focus:border-accent-500/50 focus:ring-1 focus:ring-accent-500/30 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="rounded-lg bg-accent-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-accent-700 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-2 focus:ring-offset-surface-0 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Reasoning
                </span>
              ) : (
                "Analyze"
              )}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
