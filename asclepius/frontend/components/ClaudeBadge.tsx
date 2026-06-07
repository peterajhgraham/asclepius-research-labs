"use client";

import { Logo } from "@/components/Logo";
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
    <div className="flex items-center gap-2 text-[11px] text-muted">
      <div className="flex items-center gap-1.5 rounded-md border border-line bg-bg-2 px-2 py-1 font-medium">
        <Logo size={13} />
        <span className="font-sans tracking-tight text-ink-2">
          {isStreaming ? "Asclepius" : (tier ?? "Asclepius Engine")}
        </span>
        {!isStreaming && cost != null && cost > 0 && (
          <span className="text-faint font-mono tabular-nums ml-0.5">${cost.toFixed(5)}</span>
        )}
      </div>
      {isStreaming ? (
        <span className="hx-spin" aria-label="Working" />
      ) : sourceCount > 0 ? (
        <span className="text-muted">
          {sourceCount} source{sourceCount !== 1 ? "s" : ""} retrieved
        </span>
      ) : null}
    </div>
  );
}
