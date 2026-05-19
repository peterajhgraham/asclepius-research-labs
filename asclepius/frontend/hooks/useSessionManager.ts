"use client";

import { useCallback, useEffect, useState } from "react";
import { genId, LS_KEY, sessionTitle } from "@/lib/utils";
import type { ConversationEntry, Mode, SavedSession } from "@/lib/types";

function loadSessions(): SavedSession[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || "[]");
  } catch {
    return [];
  }
}

function persistSessions(sessions: SavedSession[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(sessions));
  } catch {
    // QuotaExceededError — storage full, skip silently
  }
}

export function useSessionManager(entries: ConversationEntry[], mode: Mode) {
  const [sessions, setSessions] = useState<SavedSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  const saveCurrentSession = useCallback(() => {
    if (!entries.length) return;
    // Strip imagePreviewUrl (base64 data URLs) before persisting to avoid quota exhaustion
    const stripped = entries.map(({ imagePreviewUrl: _omit, ...rest }) => rest);
    setSessions((prev) => {
      let updated: SavedSession[];
      if (activeSessionId) {
        updated = prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, entries: stripped, title: sessionTitle(stripped), mode, updatedAt: Date.now() }
            : s,
        );
      } else {
        const newId = genId();
        updated = [
          {
            id: newId,
            title: sessionTitle(stripped),
            mode,
            entries: stripped,
            createdAt: Date.now(),
            updatedAt: Date.now(),
          },
          ...prev,
        ];
        setActiveSessionId(newId);
      }
      persistSessions(updated);
      return updated;
    });
  }, [entries, activeSessionId, mode]);

  useEffect(() => {
    if (entries.length > 0 && entries.some((e) => !e.loading)) {
      saveCurrentSession();
    }
  }, [entries, saveCurrentSession]);

  const selectSession = useCallback(
    (sessionId: string): SavedSession | null => {
      const session = sessions.find((s) => s.id === sessionId) ?? null;
      if (session) setActiveSessionId(sessionId);
      return session;
    },
    [sessions],
  );

  const deleteSession = useCallback(
    (sessionId: string) => {
      setSessions((prev) => {
        const updated = prev.filter((s) => s.id !== sessionId);
        persistSessions(updated);
        return updated;
      });
      if (activeSessionId === sessionId) setActiveSessionId(null);
    },
    [activeSessionId],
  );

  const newSession = useCallback(() => {
    setActiveSessionId(null);
  }, []);

  return { sessions, activeSessionId, selectSession, deleteSession, newSession };
}
