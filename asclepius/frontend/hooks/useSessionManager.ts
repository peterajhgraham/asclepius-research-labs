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
  } catch (e) {
    if (e instanceof Error && e.name === "QuotaExceededError") {
      console.warn("localStorage quota exceeded — session history could not be saved");
    }
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
    // Generate the ID outside the updater so the same value is used in both
    // setSessions and setActiveSessionId (React 18 may invoke the updater more
    // than once, which would produce a different ID on each call if genId() were
    // called inside it).
    const newId = activeSessionId ? null : genId();
    setSessions((prev) => {
      let updated: SavedSession[];
      if (activeSessionId) {
        updated = prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, entries: stripped, title: sessionTitle(stripped), mode, updatedAt: Date.now() }
            : s,
        );
      } else {
        updated = [
          {
            id: newId!,
            title: sessionTitle(stripped),
            mode,
            entries: stripped,
            createdAt: Date.now(),
            updatedAt: Date.now(),
          },
          ...prev,
        ];
      }
      persistSessions(updated);
      return updated;
    });
    if (newId) setActiveSessionId(newId);
  }, [entries, activeSessionId, mode]);

  useEffect(() => {
    if (entries.length > 0 && entries.every((e) => !e.loading)) {
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
