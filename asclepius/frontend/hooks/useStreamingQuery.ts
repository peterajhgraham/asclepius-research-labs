"use client";

import { useCallback, useRef, useState } from "react";

export interface Citation {
  text: string;
  score: number;
  rerank_score: number;
  type: string;
  pmid: string;
  source: string;
}

export interface StreamDonePayload {
  model: string;
  cost: number;
  sources: string[];
}

export interface StreamState {
  text: string;
  citations: Citation[];
  done: DoneState | null;
  isStreaming: boolean;
  error: string | null;
}

interface DoneState {
  model: string;
  cost: number;
  sources: string[];
}

export function useStreamingQuery() {
  const [state, setState] = useState<StreamState>({
    text: "",
    citations: [],
    done: null,
    isStreaming: false,
    error: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const stream = useCallback(async (question: string) => {
    // Abort any in-flight stream
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ text: "", citations: [], done: null, isStreaming: true, error: null });

    try {
      const url = `/api/query/stream?question=${encodeURIComponent(question)}`;
      const response = await fetch(url, { signal: controller.signal });

      if (!response.ok || !response.body) {
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: `Stream error: ${response.status}`,
        }));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          const raw = part.slice(6);
          if (raw === "[DONE]") {
            setState((s) => ({ ...s, isStreaming: false }));
            return;
          }
          try {
            const event = JSON.parse(raw) as {
              type: string;
              text?: string;
              data?: Citation[];
              model?: string;
              cost?: number;
              sources?: string[];
              message?: string;
            };
            if (event.type === "token" && event.text) {
              setState((s) => ({ ...s, text: s.text + event.text }));
            } else if (event.type === "citations" && event.data) {
              setState((s) => ({ ...s, citations: event.data! }));
            } else if (event.type === "done") {
              setState((s) => ({
                ...s,
                isStreaming: false,
                done: {
                  model: event.model ?? "",
                  cost: event.cost ?? 0,
                  sources: event.sources ?? [],
                },
              }));
            } else if (event.type === "error") {
              setState((s) => ({
                ...s,
                isStreaming: false,
                error: event.message ?? "Unknown streaming error",
              }));
            }
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: "Connection lost. Please try again.",
        }));
      }
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({ ...s, isStreaming: false }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ text: "", citations: [], done: null, isStreaming: false, error: null });
  }, []);

  return { ...state, stream, cancel, reset };
}
