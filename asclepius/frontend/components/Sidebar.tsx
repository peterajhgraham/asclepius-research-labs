"use client";

import { useState, useEffect, useCallback, type FormEvent } from "react";
import { MODE_CONFIG } from "@/components/ModeSwitcher";
import { BrandLockup } from "@/components/Logo";
import type { SavedSession } from "@/lib/types";
import { listDossiers, createDossier, type DossierSummary } from "@/lib/api";

interface Props {
  sessions: SavedSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onOpenDossier?: (id: string) => void;
  onOpenGraph?: () => void;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  sidebarOpen,
  onToggleSidebar,
  onOpenDossier,
  onOpenGraph,
}: Props) {
  const [dossiers, setDossiers] = useState<DossierSummary[]>([]);
  const [dossiersLoading, setDossiersLoading] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    setDossiersLoading(true);
    listDossiers()
      .then((data) => setDossiers(data.dossiers ?? []))
      .catch(() => setDossiers([]))
      .finally(() => setDossiersLoading(false));
  }, []);

  const handleCreate = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const name = newName.trim();
      if (!name) return;
      try {
        const d = await createDossier(name);
        setDossiers((prev) => [d, ...prev]);
        setNewName("");
        setShowNewForm(false);
      } catch {
        // non-fatal
      }
    },
    [newName],
  );

  return (
    <>
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onToggleSidebar} />
      )}
      <aside
        className={`fixed top-0 left-0 z-40 h-full w-[220px] border-r border-line bg-bg-2 flex flex-col transition-transform duration-200 lg:relative lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand lockup */}
        <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
          <button onClick={onNewSession} aria-label="New session" className="group">
            <BrandLockup />
          </button>
          <button
            onClick={onNewSession}
            aria-label="New session"
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-bg-3 hover:text-ink transition"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">

          {/* Recent sessions */}
          <div className="px-3 pt-4 pb-2">
            <p className="px-1 mb-2 font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.18em" }}>
              Recent
            </p>
            {sessions.length === 0 && (
              <p className="px-1 py-4 text-xs text-faint leading-relaxed">
                No sessions yet. Start a query to begin.
              </p>
            )}
            <div className="space-y-0.5">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`Select session: ${session.title}`}
                  className={`group flex items-center gap-2 rounded-md px-2.5 py-2 cursor-pointer transition ${
                    activeSessionId === session.id
                      ? "bg-bg-3 text-ink-2"
                      : "text-muted hover:bg-bg-3/60 hover:text-ink-2"
                  }`}
                  onClick={() => onSelectSession(session.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      if (e.key === " ") e.preventDefault(); // prevent page scroll
                      onSelectSession(session.id);
                    }
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate leading-snug">{session.title}</p>
                    <p className="mt-0.5 font-mono text-faint" style={{ fontSize: 10 }}>
                      {MODE_CONFIG[session.mode]?.label} · {session.entries.length}q
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                    aria-label="Delete session"
                    className="shrink-0 flex h-5 w-5 items-center justify-center rounded opacity-0 group-hover:opacity-100 hover:bg-risk/15 hover:text-risk transition"
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Dossiers */}
          <div className="border-t border-line px-3 pt-3 pb-2">
            <div className="flex items-center justify-between mb-2 px-1">
              <p className="font-mono uppercase text-faint" style={{ fontSize: 10, letterSpacing: "0.18em" }}>
                Dossiers
              </p>
              <button
                onClick={() => setShowNewForm((v) => !v)}
                aria-label="New dossier"
                className="flex h-5 w-5 items-center justify-center rounded text-muted hover:text-green transition"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
            </div>

            {showNewForm && (
              <form onSubmit={handleCreate} className="mb-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Dossier name…"
                  autoFocus
                  className="w-full rounded-md border border-line bg-bg-3 px-2.5 py-1.5 text-xs text-ink placeholder-faint outline-none focus:border-green/50 font-mono"
                />
              </form>
            )}

            {dossiersLoading ? (
              <p className="px-1 text-[10px] text-faint">Loading…</p>
            ) : dossiers.length === 0 ? (
              <p className="px-1 py-2 text-xs text-faint">No dossiers yet.</p>
            ) : (
              <div className="space-y-0.5">
                {dossiers.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => onOpenDossier?.(d.id)}
                    className="group w-full flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-muted hover:bg-bg-3/60 hover:text-ink-2 transition"
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-green/60">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate leading-snug">{d.name}</p>
                      <p className="font-mono text-faint" style={{ fontSize: 10 }}>
                        {d.entry_count} {d.entry_count === 1 ? "entry" : "entries"}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Knowledge Graph entry — prominent card above footer */}
        {onOpenGraph && (
          <div className="border-t border-line px-3 py-3">
            <button
              onClick={onOpenGraph}
              className="group w-full rounded-lg border border-line bg-bg-2 px-3 py-2.5 text-left transition hover:border-green/25 hover:bg-bg-3"
            >
              <div className="flex items-center gap-2.5">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0 text-green/70 group-hover:text-green transition">
                  <circle cx="12" cy="5" r="2" />
                  <circle cx="5" cy="19" r="2" />
                  <circle cx="19" cy="19" r="2" />
                  <line x1="12" y1="7" x2="5" y2="17" />
                  <line x1="12" y1="7" x2="19" y2="17" />
                </svg>
                <span className="flex-1 text-xs font-mono text-ink-2">Knowledge Graph</span>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="shrink-0 text-faint group-hover:text-muted transition">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
              <p className="mt-1 font-mono text-faint" style={{ fontSize: 9, letterSpacing: "0.12em" }}>
                CAUSAL ENTITY NETWORK · CLICK TO EXPLORE
              </p>
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-line px-4 py-3">
          <div className="flex items-center justify-between">
            <span className="font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.16em" }}>
              Sessions stored locally
            </span>
            <span className="font-mono tabular-nums text-muted" style={{ fontSize: 10 }}>
              {sessions.length}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
