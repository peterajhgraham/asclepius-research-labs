"use client";

import { useState, useEffect, useRef } from "react";
import { getDossier, getDossierInsights, type Dossier, type DossierInsights } from "@/lib/api";

interface Props {
  dossierId: string | null;
  onClose: () => void;
}

export default function DossierPanel({ dossierId, onClose }: Props) {
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [insights, setInsights] = useState<DossierInsights | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState(false);
  const [tab, setTab] = useState<"entries" | "insights">("entries");

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    if (!dossierId) {
      setDossier(null);
      setInsights(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setFetchError(false);
    setTab("entries");
    Promise.allSettled([getDossier(dossierId), getDossierInsights(dossierId)])
      .then(([dossierResult, insightsResult]) => {
        if (cancelled) return;
        if (dossierResult.status === "rejected") {
          setFetchError(true);
          return;
        }
        setDossier(dossierResult.value);
        if (insightsResult.status === "fulfilled") {
          setInsights(insightsResult.value);
        }
        // insights failure is non-fatal — dossier still displays
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [dossierId]);

  if (!dossierId) return null;

  return (
    <>
      {/* Backdrop (mobile) */}
      <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />

      {/* Panel — overlay on mobile, persistent split column at ≥1024px */}
      <aside
        className="fixed right-0 top-0 z-40 h-full w-[340px] border-l border-line bg-bg-2 shadow-card animate-slide-in flex flex-col
                   lg:relative lg:right-auto lg:top-auto lg:z-auto lg:shadow-none lg:flex-shrink-0"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-ink text-display-m leading-none truncate">
              {loading ? "Loading…" : (dossier?.name ?? "Dossier")}
            </h3>
            {dossier?.description && (
              <p className="mt-1 text-xs text-muted truncate">{dossier.description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dossier"
            className="ml-3 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-bg-3 hover:text-ink transition"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-line">
          {(["entries", "insights"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 font-mono uppercase transition text-[9px] ${
                tab === t
                  ? "text-green border-b-2 border-green"
                  : "text-faint hover:text-ink-2"
              }`}
              style={{ letterSpacing: "0.14em" }}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto py-3 px-3 space-y-2">
          {loading && (
            <p className="text-xs text-faint text-center py-8">Loading dossier…</p>
          )}

          {!loading && fetchError && (
            <p className="text-xs text-red text-center py-8">
              Failed to load dossier. Check your connection and try again.
            </p>
          )}

          {!loading && !fetchError && tab === "entries" && (
            <>
              {(!dossier?.entries || dossier.entries.length === 0) ? (
                <p className="text-xs text-faint text-center py-8">
                  No entries yet. Add queries to this dossier from the main interface.
                </p>
              ) : (
                dossier.entries.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-line bg-bg-2 p-3 transition hover:bg-bg-3"
                  >
                    <p className="text-xs font-medium text-ink leading-snug">{entry.query}</p>
                    <p className="mt-1 font-mono text-faint" style={{ fontSize: 9, letterSpacing: "0.1em" }}>
                      {new Date(entry.created_at).toLocaleDateString()}
                    </p>
                    {entry.notes && (
                      <p className="mt-2 text-xs italic text-muted leading-relaxed border-t border-line pt-2">
                        {entry.notes}
                      </p>
                    )}
                  </div>
                ))
              )}
            </>
          )}

          {!loading && !fetchError && tab === "insights" && insights && (
            <div className="space-y-4">
              <StatRow label="Queries" value={insights.total_queries} />
              <ChipSection label="Key Entities" items={insights.key_entities} accent="text-green" />
              <ChipSection label="Mechanisms" items={insights.key_mechanisms} />
              <ChipSection label="Pathways" items={insights.pathways} />
              <ChipSection label="Therapeutic Targets" items={insights.therapeutic_targets} accent="text-amber" />
              <ChipSection label="Genes" items={insights.genes} />
              {insights.notes.length > 0 && (
                <div>
                  <SectionLabel label="Notes" />
                  <div className="space-y-1.5">
                    {insights.notes.map((n) => (
                      <div key={n.entry_id} className="rounded border border-line bg-bg-3 px-2.5 py-2">
                        <p className="text-[10px] text-muted font-mono truncate">{n.query}</p>
                        <p className="mt-1 text-xs text-ink-2 italic">{n.notes}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-line px-4 py-2.5 flex items-center justify-between">
          <p className="font-mono text-faint" style={{ fontSize: 9, letterSpacing: "0.1em" }}>
            {dossier ? `${dossier.entry_count} entries · ${dossier.id}` : ""}
          </p>
        </div>
      </aside>
    </>
  );
}

function StatRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between px-1">
      <span className="font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
        {label}
      </span>
      <span className="font-mono tabular-nums text-ink-2 text-xs">{value}</span>
    </div>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="mb-1.5 px-1 font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
      {label}
    </p>
  );
}

function ChipSection({
  label,
  items,
  accent = "text-ink-2",
}: {
  label: string;
  items: string[];
  accent?: string;
}) {
  if (!items.length) return null;
  return (
    <div>
      <SectionLabel label={label} />
      <div className="flex flex-wrap gap-1">
        {items.slice(0, 12).map((item) => (
          <span
            key={item}
            className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono border border-line bg-bg-3 ${accent}`}
          >
            {item}
          </span>
        ))}
        {items.length > 12 && (
          <span className="text-[10px] font-mono text-faint">+{items.length - 12} more</span>
        )}
      </div>
    </div>
  );
}
