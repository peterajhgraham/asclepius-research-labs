"use client";

import { useState, useEffect, useRef } from "react";
import KnowledgeGraph, { type GraphNode, type GraphEdge } from "@/components/KnowledgeGraph";

interface HubNode {
  node_id: string;
  node_type: string;
  degree: number;
  betweenness?: number;
}

interface SubgraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}

async function fetchHubs(signal?: AbortSignal): Promise<{ hubs: HubNode[] }> {
  const res = await fetch("/api/graph/hubs", { signal });
  if (!res.ok) throw new Error("Failed to fetch hubs");
  return res.json();
}

async function fetchSubgraph(seedNode: string, hops = 2, signal?: AbortSignal): Promise<SubgraphData> {
  const res = await fetch("/api/graph/subgraph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ seed_nodes: [seedNode], hops }),
    signal,
  });
  if (!res.ok) throw new Error("Failed to fetch subgraph");
  return res.json();
}

const TYPE_PILL: Record<string, string> = {
  cytokine:    "border-green/30 text-green",
  gene:        "border-amber/30 text-amber",
  therapeutic: "border-risk/30 text-risk",
  pathway:     "border-blue-400/30 text-blue-400",
  disease:     "border-purple-400/30 text-purple-400",
};

export default function GraphExplorer() {
  const [hubs, setHubs] = useState<HubNode[]>([]);
  const [hubsLoading, setHubsLoading] = useState(true);
  const [hubsError, setHubsError] = useState<string | null>(null);
  const [selectedHub, setSelectedHub] = useState<string | null>(null);
  const [subgraph, setSubgraph] = useState<SubgraphData | null>(null);
  const [subgraphLoading, setSubgraphLoading] = useState(false);
  const [subgraphError, setSubgraphError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchHubs(controller.signal)
      .then((data) => setHubs(data.hubs ?? []))
      .catch((err) => {
        if ((err as Error).name !== "AbortError") {
          setHubsError("Graph service unavailable — check that the backend is running.");
        }
      })
      .finally(() => setHubsLoading(false));
    return () => controller.abort();
  }, []);

  async function handleSelectHub(nodeId: string) {
    if (nodeId === selectedHub) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSelectedHub(nodeId);
    setSubgraphLoading(true);
    setSubgraph(null);
    setSubgraphError(null);
    try {
      const data = await fetchSubgraph(nodeId, 2, controller.signal);
      setSubgraph(data);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setSubgraphError("Failed to load subgraph. Try again.");
      }
    } finally {
      setSubgraphLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div>
          <h3 className="font-display text-ink text-display-m leading-none">
            Knowledge Graph
          </h3>
          <p className="mt-1 font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
            Causal immune signaling network · select a hub to explore
          </p>
        </div>
        {subgraph && (
          <div className="ml-auto flex items-center gap-2 font-mono text-[10px] text-faint">
            <span>{subgraph.node_count} nodes</span>
            <span className="text-line">·</span>
            <span>{subgraph.edge_count} edges</span>
          </div>
        )}
      </div>

      {/* Graph canvas */}
      {subgraphLoading && (
        <div className="flex items-center justify-center rounded-lg border border-line bg-bg-2 text-xs text-faint" style={{ height: 380 }}>
          <span className="hx-spin mr-2" />
          Loading subgraph…
        </div>
      )}
      {!subgraphLoading && subgraph && (
        <KnowledgeGraph
          nodes={subgraph.nodes}
          edges={subgraph.edges}
          height={380}
          highlightNode={selectedHub ?? undefined}
        />
      )}
      {!subgraphLoading && !subgraph && !hubsLoading && (
        <div
          className="flex items-center justify-center rounded-lg border border-line bg-bg-2 text-xs text-faint"
          style={{ height: 380 }}
        >
          {subgraphError ?? hubsError ?? "Select a hub node below to visualize its subgraph"}
        </div>
      )}

      {/* Legend */}
      {subgraph && (
        <div className="flex flex-wrap gap-2 text-[10px] font-mono">
          {Object.entries({ cytokine: "#87f085", gene: "#f5c062", therapeutic: "#f08987", pathway: "#6ab4f5", disease: "#c78bff" }).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1 text-faint">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
              {type}
            </span>
          ))}
        </div>
      )}

      {/* Hub list */}
      <div>
        <p className="mb-2 font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Top Hub Nodes
        </p>
        {hubsLoading && (
          <p className="text-xs text-faint">Loading hub analysis…</p>
        )}
        {hubsError && (
          <p className="text-xs text-risk">{hubsError}</p>
        )}
        {!hubsLoading && !hubsError && (
          <div className="space-y-1">
            {hubs.slice(0, 15).map((hub) => (
              <button
                key={hub.node_id}
                onClick={() => handleSelectHub(hub.node_id)}
                className={`group w-full flex items-center gap-3 rounded-md px-3 py-2 text-left transition ${
                  selectedHub === hub.node_id
                    ? "bg-bg-3 border border-green/20"
                    : "border border-transparent hover:bg-bg-3/60"
                }`}
              >
                <span
                  className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-mono uppercase ${
                    TYPE_PILL[hub.node_type] ?? "border-line text-faint"
                  }`}
                >
                  {hub.node_type}
                </span>
                <span className="flex-1 min-w-0 text-xs font-mono text-ink-2 truncate">
                  {hub.node_id}
                </span>
                <span className="shrink-0 font-mono tabular-nums text-[10px] text-muted">
                  deg {hub.degree}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
