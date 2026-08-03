"use client";

import { useState, useEffect, useRef } from "react";
import KnowledgeGraph, { TYPE_COLORS, type GraphNode, type GraphEdge } from "@/components/KnowledgeGraph";

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

// Type display order and labels
const TYPE_ORDER = ["gene", "cytokine", "pathway", "therapeutic", "disease", "cell_type"];
const TYPE_LABEL: Record<string, string> = {
  gene: "Gene",
  cytokine: "Cytokine",
  pathway: "Pathway",
  therapeutic: "Therapeutic",
  disease: "Disease",
  cell_type: "Cell Type",
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
      // Compute in-subgraph degree from edges so nodes size correctly
      const degreeMap = new Map<string, number>();
      for (const e of data.edges) {
        degreeMap.set(e.source, (degreeMap.get(e.source) ?? 0) + 1);
        degreeMap.set(e.target, (degreeMap.get(e.target) ?? 0) + 1);
      }
      const nodes = data.nodes.map((n) => ({ ...n, degree: degreeMap.get(n.id) ?? 1 }));
      setSubgraph({ ...data, nodes });
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setSubgraphError("Failed to load subgraph. Try again.");
      }
    } finally {
      setSubgraphLoading(false);
    }
  }

  // Group hubs by type in display order
  const grouped: Record<string, HubNode[]> = {};
  for (const hub of hubs) {
    const t = hub.node_type ?? "Unknown";
    (grouped[t] ??= []).push(hub);
  }
  const groupEntries = [
    ...TYPE_ORDER.filter((t) => grouped[t]?.length),
    ...Object.keys(grouped).filter((t) => !TYPE_ORDER.includes(t) && grouped[t]?.length),
  ].map((t) => [t, grouped[t]] as [string, HubNode[]]);

  // Detect which types are present in the current subgraph for legend
  const activeTypes = subgraph
    ? [...new Set(subgraph.nodes.map((n) => n.type ?? "Unknown"))]
    : [];

  return (
    <div className="space-y-4">
      {/* Header + description */}
      <div>
        <h3 className="font-display text-ink text-display-m leading-none">
          Knowledge Graph
        </h3>
        <p className="mt-1 font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Causal immune signaling network
        </p>
        <p className="mt-2.5 text-xs text-muted leading-relaxed">
          A live map of relationships extracted from PubMed — genes, cytokines, pathways, therapeutics, and diseases linked by experimental evidence. Each hub is a highly connected entity in the network. Select a hub to explore its 2-hop neighborhood, or click any node in the graph to pivot to it.
        </p>
      </div>

      {/* Legend — always visible */}
      <div className="flex flex-wrap gap-x-3 gap-y-1.5">
        {TYPE_ORDER.map((type) => (
          <span key={type} className="flex items-center gap-1.5 font-mono text-[10px] text-muted">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ background: TYPE_COLORS[type] ?? TYPE_COLORS.Unknown }}
            />
            {TYPE_LABEL[type] ?? type}
          </span>
        ))}
      </div>

      {/* Graph canvas */}
      {subgraphLoading && (
        <div className="flex items-center justify-center rounded-lg border border-line bg-bg-2 text-xs text-faint" style={{ height: 420 }}>
          <span className="hx-spin mr-2" />
          Loading subgraph…
        </div>
      )}
      {!subgraphLoading && subgraph && (
        <>
          <div className="flex items-center gap-2 font-mono text-[10px] text-faint">
            <span className="text-ink-2 font-mono">{selectedHub}</span>
            <span className="text-line-2">·</span>
            <span>{subgraph.node_count} nodes</span>
            <span className="text-line-2">·</span>
            <span>{subgraph.edge_count} edges</span>
          </div>
          <KnowledgeGraph
            nodes={subgraph.nodes}
            edges={subgraph.edges}
            height={420}
            highlightNode={selectedHub ?? undefined}
            onNodeClick={handleSelectHub}
          />
          {/* Active type breakdown for current subgraph */}
          {activeTypes.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 pt-0.5">
              {activeTypes
                .filter((t) => TYPE_COLORS[t])
                .map((t) => (
                  <span key={t} className="flex items-center gap-1.5 font-mono text-[10px] text-faint">
                    <span
                      className="inline-block h-2 w-2 rounded-full flex-shrink-0"
                      style={{ background: TYPE_COLORS[t] }}
                    />
                    {TYPE_LABEL[t] ?? t}
                  </span>
                ))}
            </div>
          )}
        </>
      )}
      {!subgraphLoading && !subgraph && !hubsLoading && (
        <div
          className="flex flex-col items-center justify-center gap-2 rounded-lg border border-line bg-bg-2 text-center"
          style={{ height: 420 }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-faint">
            <circle cx="12" cy="5" r="2" />
            <circle cx="5" cy="19" r="2" />
            <circle cx="19" cy="19" r="2" />
            <line x1="12" y1="7" x2="5" y2="17" />
            <line x1="12" y1="7" x2="19" y2="17" />
          </svg>
          <p className="text-xs text-faint max-w-[240px] leading-relaxed">
            {subgraphError ?? hubsError ?? "Select a hub node below to visualize its 2-hop neighborhood"}
          </p>
        </div>
      )}

      {/* Hub list — grouped by type */}
      <div>
        <p className="mb-3 font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
          Top Hub Nodes
        </p>
        {hubsLoading && (
          <p className="text-xs text-faint">Analyzing network topology…</p>
        )}
        {hubsError && (
          <p className="text-xs text-risk">{hubsError}</p>
        )}
        {!hubsLoading && !hubsError && (
          <div className="space-y-4">
            {groupEntries.map(([type, nodes]) => (
              <div key={type}>
                {/* Type header */}
                <div className="mb-1.5 flex items-center gap-2">
                  <span
                    className="inline-block h-2 w-2 rounded-full flex-shrink-0"
                    style={{ background: TYPE_COLORS[type] ?? TYPE_COLORS.Unknown }}
                  />
                  <span className="font-mono uppercase text-faint" style={{ fontSize: 9, letterSpacing: "0.14em" }}>
                    {TYPE_LABEL[type] ?? type} · {nodes.length}
                  </span>
                </div>
                <div className="space-y-0.5">
                  {nodes.map((hub) => (
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
                        className="shrink-0 h-2 w-2 rounded-full"
                        style={{ background: TYPE_COLORS[hub.node_type] ?? TYPE_COLORS.Unknown }}
                      />
                      <span className="flex-1 min-w-0 text-xs font-mono text-ink-2 truncate">
                        {hub.node_id}
                      </span>
                      <span className="shrink-0 font-mono tabular-nums text-[10px] text-muted">
                        deg {hub.degree}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
