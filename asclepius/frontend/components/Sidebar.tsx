"use client";

import { MODE_CONFIG } from "@/components/ModeSwitcher";
import { BrandLockup } from "@/components/Logo";
import type { SavedSession } from "@/lib/types";

interface Props {
  sessions: SavedSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  sidebarOpen,
  onToggleSidebar,
}: Props) {
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

        {/* Recent sessions */}
        <div className="flex-1 overflow-y-auto px-3 pt-4 pb-1">
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
                onKeyDown={(e) => e.key === "Enter" && onSelectSession(session.id)}
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
