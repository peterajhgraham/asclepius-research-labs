"use client";

import { modelDisplayName } from "@/lib/utils";

interface Props {
  model?: string;
  cost?: number;
  isStreaming?: boolean;
  sourceCount?: number;
}

export default function ClaudeBadge({ model, cost, isStreaming = false, sourceCount = 0 }: Props) {
  const tier = model ? modelDisplayName(model) : null;
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-light">
      <div className="flex items-center gap-1.5 rounded-md border border-surface-3 bg-surface-1 px-2 py-1 font-medium">
        <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
        <span className="font-mono tracking-tight">
          {isStreaming ? "Asclepius" : (tier ?? "Asclepius Engine")}
        </span>
        {!isStreaming && cost != null && cost > 0 && (
          <span className="text-muted font-mono opacity-70 ml-0.5">${cost.toFixed(5)}</span>
        )}
      </div>
      {isStreaming ? (
        <span className="flex items-center gap-1 text-muted">
          <span className="flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1 w-1 rounded-full bg-accent-500 animate-pulse-dot"
                style={{ animationDelay: `${i * 0.16}s` }}
              />
            ))}
          </span>
          Generating…
        </span>
      ) : sourceCount > 0 ? (
        <span className="text-muted">
          {sourceCount} source{sourceCount !== 1 ? "s" : ""} retrieved
        </span>
      ) : null}
    </div>
  );
}
