"use client";

import { MODE_CONFIG } from "@/components/ModeSwitcher";
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
        className={`fixed top-0 left-0 z-40 h-full w-60 border-r border-surface-3 bg-surface-1 flex flex-col transition-transform duration-200 lg:relative lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-3 px-4 py-3.5">
          <button onClick={onNewSession} className="flex items-center gap-2 group">
            <span className="text-sm font-semibold tracking-tight text-gray-100 group-hover:text-accent-400 transition">
              Asclepius
            </span>
            <span className="rounded-md bg-accent-600/15 px-1.5 py-0.5 text-[10px] font-medium text-accent-400 tracking-wide">
              Research
            </span>
          </button>
          <button
            onClick={onNewSession}
            aria-label="New session"
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-gray-300 transition"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto py-1.5">
          {sessions.length === 0 && (
            <p className="px-4 py-8 text-center text-xs text-muted leading-relaxed">
              No sessions yet.<br />Start a query to begin.
            </p>
          )}
          {sessions.map((session) => (
            <div
              key={session.id}
              role="button"
              tabIndex={0}
              aria-label={`Select session: ${session.title}`}
              className={`group mx-2 mb-0.5 flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer transition ${
                activeSessionId === session.id
                  ? "bg-surface-2 text-gray-200"
                  : "text-muted hover:bg-surface-2/60 hover:text-gray-300"
              }`}
              onClick={() => onSelectSession(session.id)}
              onKeyDown={(e) => e.key === "Enter" && onSelectSession(session.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate leading-snug">{session.title}</p>
                <p className="text-[10px] text-muted mt-0.5 font-mono">
                  {MODE_CONFIG[session.mode]?.label} · {session.entries.length}q
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                aria-label="Delete session"
                className="shrink-0 flex h-5 w-5 items-center justify-center rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/15 hover:text-red-400 transition"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        <div className="border-t border-surface-3 px-4 py-2.5">
          <p className="text-[10px] text-muted font-mono">sessions · local storage</p>
        </div>
      </aside>
    </>
  );
}
