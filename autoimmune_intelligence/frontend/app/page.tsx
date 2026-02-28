"use client";

import { useState, type FormEvent } from "react";
import ResponseCard from "@/components/ResponseCard";
import { submitQuery, type QueryResponse } from "@/lib/api";

export default function HomePage() {
  const [question, setQuestion] = useState<string>("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const result = await submitQuery({ question: trimmed });
      setResponse(result);
    } catch {
      setError("Unable to reach the analysis service. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-start bg-white px-4 pt-24 pb-16">
      {/* Header */}
      <div className="mb-12 text-center">
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

      {/* Query form */}
      <form onSubmit={handleSubmit} className="w-full max-w-2xl">
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
            {loading ? "Analysing…" : "Analyse"}
          </button>
        </div>
      </form>

      {/* Loading indicator */}
      {loading && (
        <div className="mt-10 flex items-center gap-2 text-sm text-brand-600">
          <svg
            className="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v8H4z"
            />
          </svg>
          Processing query…
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="mt-8 w-full max-w-2xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Response */}
      {response && <ResponseCard data={response} />}
    </main>
  );
}
