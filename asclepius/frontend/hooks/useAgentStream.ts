"use client";

import { useCallback, useRef, useState } from "react";

export interface AgentPlannerStep {
  iteration: number;
  thinking?: string;
  tool_calls?: string[];
}

export interface AgentToolCall {
  iteration: number;
  tool: string;
  args: Record<string, unknown>;
}

export interface AgentToolResult {
  iteration: number;
  tool: string;
  result_preview: string;
}

export interface AgentVerification {
  verdict: string;
  confidence: number;
  notes: string;
  revised_answer?: string;
  images_inspected: number;
  cost_usd?: number;
  model_used?: string;
}

export interface AgentDone {
  iterations: number;
  model: string;
  cost_usd: number;
}

export interface AgentState {
  steps: AgentPlannerStep[];
  toolCalls: AgentToolCall[];
  toolResults: AgentToolResult[];
  finalAnswer: string;
  imageHashes: string[];
  verification: AgentVerification | null;
  done: AgentDone | null;
  isStreaming: boolean;
  error: string | null;
}

const EMPTY: AgentState = {
  steps: [],
  toolCalls: [],
  toolResults: [],
  finalAnswer: "",
  imageHashes: [],
  verification: null,
  done: null,
  isStreaming: false,
  error: null,
};

export function useAgentStream() {
  const [state, setState] = useState<AgentState>(EMPTY);
  const abortRef = useRef<AbortController | null>(null);

  const stream = useCallback(async (question: string, verify: boolean = false) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ ...EMPTY, isStreaming: true });

    try {
      const url =
        `/api/query/agent?question=${encodeURIComponent(question)}` +
        `&verify=${verify ? "true" : "false"}`;
      const response = await fetch(url, { signal: controller.signal });

      if (!response.ok || !response.body) {
        setState((s) => ({ ...s, isStreaming: false, error: `Stream error: ${response.status}` }));
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
          try {
            const evt = JSON.parse(raw) as Record<string, unknown>;
            const t = evt.type as string;
            if (t === "planner_step") {
              setState((s) => ({
                ...s,
                steps: [
                  ...s.steps,
                  {
                    iteration: (evt.iteration as number) ?? 0,
                    thinking: evt.thinking as string | undefined,
                    tool_calls: (evt.tool_calls as string[]) ?? [],
                  },
                ],
              }));
            } else if (t === "tool_call") {
              setState((s) => ({
                ...s,
                toolCalls: [
                  ...s.toolCalls,
                  {
                    iteration: (evt.iteration as number) ?? 0,
                    tool: (evt.tool as string) ?? "",
                    args: (evt.args as Record<string, unknown>) ?? {},
                  },
                ],
              }));
            } else if (t === "tool_result") {
              setState((s) => ({
                ...s,
                toolResults: [
                  ...s.toolResults,
                  {
                    iteration: (evt.iteration as number) ?? 0,
                    tool: (evt.tool as string) ?? "",
                    result_preview: (evt.result_preview as string) ?? "",
                  },
                ],
              }));
            } else if (t === "final") {
              setState((s) => ({
                ...s,
                finalAnswer: (evt.answer as string) ?? "",
                imageHashes: (evt.image_hashes as string[]) ?? [],
              }));
            } else if (t === "verification") {
              const verdict = (evt.verdict as string) ?? "no_images";
              const confidence = (evt.confidence as number) ?? 0;
              const notes = (evt.notes as string) ?? "";
              const revised = evt.revised_answer as string | undefined;
              const imagesInspected = (evt.images_inspected as number) ?? 0;
              setState((s) => ({
                ...s,
                verification: {
                  verdict,
                  confidence,
                  notes,
                  revised_answer: revised,
                  images_inspected: imagesInspected,
                  cost_usd: evt.cost_usd as number | undefined,
                  model_used: evt.model_used as string | undefined,
                },
                // If verifier rewrote the answer with [unverified] / [uncertain]
                // markers, swap it into the visible final answer.
                finalAnswer:
                  revised && (verdict === "partially_supported" || verdict === "unsupported")
                    ? revised
                    : s.finalAnswer,
              }));
            } else if (t === "done") {
              setState((s) => ({
                ...s,
                isStreaming: false,
                done: {
                  iterations: (evt.iterations as number) ?? 0,
                  model: (evt.model as string) ?? "",
                  cost_usd: (evt.cost_usd as number) ?? 0,
                },
              }));
            } else if (t === "error") {
              setState((s) => ({
                ...s,
                isStreaming: false,
                error: (evt.message as string) ?? "Unknown agent error",
              }));
            }
          } catch {
            // ignore malformed events
          }
        }
      }
      setState((s) => ({ ...s, isStreaming: false }));
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
    setState(EMPTY);
  }, []);

  return { ...state, stream, cancel, reset };
}
