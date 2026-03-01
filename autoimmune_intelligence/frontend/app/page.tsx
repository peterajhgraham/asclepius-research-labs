"use client";

import { useState, useRef, useEffect, type FormEvent } from "react";
import { submitQuery } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

const EXAMPLE_PROMPTS = [
  "Rheumatoid arthritis cytokine pathways",
  "Lupus interferon signaling",
  "T cell exhaustion in autoimmunity",
];

export default function HomePage() {
  const [question, setQuestion] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e?: FormEvent<HTMLFormElement>) {
    if (e) e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);
    setError(null);

    try {
      const result = await submitQuery({ question: trimmed });
      const aiMessage: ChatMessage = {
        role: "assistant",
        content: result.answer,
        sources: result.sources,
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (err: unknown) {
      let detail = "Unable to reach the analysis service.";
      if (err && typeof err === "object" && "response" in err) {
        const res = (err as { response?: { data?: { error?: string } } }).response;
        if (res?.data?.error) detail = res.data.error;
      }
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  function handleExampleClick(example: string) {
    setQuestion(example);
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

  return (
    <main className="flex min-h-screen flex-col items-center justify-start bg-white px-4 pt-24 pb-16">
      {/* Header */}
      <div className="mb-8 text-center">
        <span className="inline-block rounded-full bg-brand-100 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-brand-700">
          Research Platform
        </span>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Autoimmune Intelligence
        </h1>
        <p className="mt-4 max-w-xl text-base text-gray-500">
          Submit a clinical or mechanistic question. Our AI synthesises
          immunological evidence and surfaces structured insights with
          literature references.
        </p>
      </div>

      {/* Example Prompts */}
      {messages.length === 0 && (
        <div className="mb-6 flex flex-wrap justify-center gap-2">
          {EXAMPLE_PROMPTS.map((example) => (
            <button
              key={example}
              onClick={() => handleExampleClick(example)}
              className="rounded-full bg-gray-100 px-4 py-1.5 text-sm text-gray-700 transition hover:bg-gray-200"
            >
              {example}
            </button>
          ))}
        </div>
      )}

      {/* Chat Messages */}
      <div className="w-full max-w-2xl flex-1 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`rounded-xl p-4 ${
              msg.role === "user"
                ? "ml-auto max-w-[80%] bg-brand-100 text-right text-gray-900"
                : "mr-auto max-w-[90%] border border-gray-200 bg-white shadow-sm"
            }`}
          >
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {msg.content}
            </p>

            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-3 border-t border-gray-100 pt-2">
                <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-brand-600">
                  Sources
                </p>
                <ul className="space-y-0.5">
                  {msg.sources.map((src, i) => {
                    const { text, href } = formatPubMedLink(src);
                    return (
                      <li key={i} className="text-xs text-gray-500">
                        {href ? (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline hover:text-brand-700"
                          >
                            {text}
                          </a>
                        ) : (
                          text
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        ))}

        {/* Loading Animation */}
        {loading && (
          <div className="mr-auto flex max-w-[90%] items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
            <span className="animate-pulse text-sm text-brand-600">
              Analyzing...
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error message */}
      {error && (
        <div className="mt-4 w-full max-w-2xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Query form */}
      <form
        onSubmit={handleSubmit}
        className="mt-6 w-full max-w-2xl"
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What drives JAK-STAT dysregulation in lupus?"
            disabled={loading}
            className="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 placeholder-gray-400 shadow-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="rounded-xl bg-brand-700 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <span className="animate-pulse">Analysing...</span>
            ) : (
              "Query"
            )}
          </button>
        </div>
      </form>
    </main>
  );
}
