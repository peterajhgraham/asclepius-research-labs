"use client";

import { useEffect, useRef, useCallback } from "react";

export interface GraphNode {
  id: string;
  label?: string;
  type?: string;
  degree?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type?: string;
  weight?: number;
}

interface LayoutNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  height?: number;
  highlightNode?: string;
  onNodeClick?: (nodeId: string) => void;
}

export const TYPE_COLORS: Record<string, string> = {
  cytokine:    "#87f085",
  gene:        "#f5c062",
  therapeutic: "#f08987",
  pathway:     "#6ab4f5",
  disease:     "#c78bff",
  cell_type:   "#f5b4e8",
  Unknown:     "#6b7280",
};

function nodeColor(type: string | undefined): string {
  return TYPE_COLORS[type ?? "Unknown"] ?? TYPE_COLORS.Unknown;
}

function nodeRadius(n: LayoutNode): number {
  const base = 7;
  if (!n.degree) return base;
  return base + Math.min(n.degree / 5, 7);
}

function hitTest(nodes: LayoutNode[], x: number, y: number): LayoutNode | null {
  let hit: LayoutNode | null = null;
  let minDist = Infinity;
  for (const n of nodes) {
    const dx = n.x - x;
    const dy = n.y - y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const r = nodeRadius(n) + 6;
    if (dist < r && dist < minDist) {
      minDist = dist;
      hit = n;
    }
  }
  return hit;
}

function runForce(
  nodes: LayoutNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
  iterations: number,
) {
  const idxMap = new Map(nodes.map((n, i) => [n.id, i]));
  const k = Math.sqrt((width * height) / Math.max(nodes.length, 1));
  const repulsion = k * k * 2.2;
  const spring = 0.04;
  const damping = 0.8;

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 1 - iter / iterations;

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx += fx;
        nodes[i].vy += fy;
        nodes[j].vx -= fx;
        nodes[j].vy -= fy;
      }
    }

    for (const edge of edges) {
      const si = idxMap.get(edge.source);
      const ti = idxMap.get(edge.target);
      if (si == null || ti == null) continue;
      const dx = nodes[ti].x - nodes[si].x;
      const dy = nodes[ti].y - nodes[si].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - k) * spring;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      nodes[si].vx += fx;
      nodes[si].vy += fy;
      nodes[ti].vx -= fx;
      nodes[ti].vy -= fy;
    }

    for (const n of nodes) {
      n.vx += (width / 2 - n.x) * 0.005;
      n.vy += (height / 2 - n.y) * 0.005;
    }

    for (const n of nodes) {
      n.vx *= damping;
      n.vy *= damping;
      const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
      const maxSpeed = k * temp * 3;
      if (speed > maxSpeed) {
        n.vx = (n.vx / speed) * maxSpeed;
        n.vy = (n.vy / speed) * maxSpeed;
      }
      n.x = Math.max(40, Math.min(width - 40, n.x + n.vx));
      n.y = Math.max(30, Math.min(height - 30, n.y + n.vy));
    }
  }
}

function drawGraph(
  ctx: CanvasRenderingContext2D,
  nodes: LayoutNode[],
  edges: GraphEdge[],
  idxMap: Map<string, number>,
  highlightId: string | undefined,
) {
  const { width, height } = ctx.canvas;
  ctx.clearRect(0, 0, width, height);

  // Edges — highlight edges connected to the selected hub
  for (const edge of edges) {
    const si = idxMap.get(edge.source);
    const ti = idxMap.get(edge.target);
    if (si == null || ti == null) continue;
    const s = nodes[si];
    const t = nodes[ti];
    const isConnected = highlightId && (edge.source === highlightId || edge.target === highlightId);
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = isConnected ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.07)";
    ctx.lineWidth = isConnected ? 1.5 : 1;
    ctx.stroke();
  }

  // Nodes — draw in two passes so highlighted node renders on top
  const normalNodes = nodes.filter((n) => n.id !== highlightId);
  const highlightedNode = nodes.find((n) => n.id === highlightId);
  const drawOrder = highlightedNode ? [...normalNodes, highlightedNode] : normalNodes;

  const showLabels = nodes.length <= 45;

  for (const n of drawOrder) {
    const isHighlight = n.id === highlightId;
    const r = nodeRadius(n);
    const color = nodeColor(n.type);

    // Outer glow for highlighted node
    if (isHighlight) {
      const grad = ctx.createRadialGradient(n.x, n.y, r, n.x, n.y, r + 14);
      grad.addColorStop(0, color + "40");
      grad.addColorStop(1, color + "00");
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 14, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(n.x, n.y, isHighlight ? r * 1.5 : r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.globalAlpha = isHighlight ? 1 : 0.82;
    ctx.fill();
    ctx.globalAlpha = 1;

    // Stroke ring on highlight
    if (isHighlight) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r * 1.5 + 2.5, 0, Math.PI * 2);
      ctx.strokeStyle = color + "80";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Labels
    const shouldLabel = isHighlight || showLabels;
    if (shouldLabel) {
      const label = (n.label ?? n.id).slice(0, 22);
      const finalR = isHighlight ? r * 1.5 : r;
      ctx.font = `10px 'Geist Mono', ui-monospace, monospace`;
      ctx.textAlign = "center";
      const metrics = ctx.measureText(label);
      const lx = n.x;
      const ly = n.y + finalR + 14;

      // Label background for readability
      ctx.fillStyle = "rgba(12, 16, 20, 0.80)";
      ctx.fillRect(lx - metrics.width / 2 - 3, ly - 11, metrics.width + 6, 14);

      ctx.fillStyle = isHighlight ? color : "#9aa5b4";
      ctx.fillText(label, lx, ly);
    }
  }
}

export default function KnowledgeGraph({
  nodes,
  edges,
  height = 420,
  highlightNode,
  onNodeClick,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const layoutRef = useRef<LayoutNode[]>([]);
  const highlightRef = useRef<string | undefined>(highlightNode);
  highlightRef.current = highlightNode;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const idxMap = new Map(layoutRef.current.map((n, i) => [n.id, i]));
    drawGraph(ctx, layoutRef.current, edges, idxMap, highlightRef.current);
  }, [edges]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.offsetWidth;
    const h = height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    if (!nodes.length) return;

    layoutRef.current = nodes.map((n) => ({
      ...n,
      x: Math.random() * w * 0.8 + w * 0.1,
      y: Math.random() * h * 0.8 + h * 0.1,
      vx: 0,
      vy: 0,
    }));

    runForce(layoutRef.current, edges, w, h, 220);
    draw();
  }, [nodes, edges, height, draw]);

  useEffect(() => {
    draw();
  }, [highlightNode, draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = canvas.offsetWidth * dpr;
      canvas.height = canvas.offsetHeight * dpr;
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.scale(dpr, dpr);
      draw();
    });
    ro.observe(canvas.parentElement ?? canvas);
    return () => ro.disconnect();
  }, [draw]);

  // Click handler: find the nearest node and fire onNodeClick
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !onNodeClick) return;
    const handler = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.offsetWidth / rect.width;
      const scaleY = canvas.offsetHeight / rect.height;
      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;
      const hit = hitTest(layoutRef.current, x, y);
      if (hit) onNodeClick(hit.id);
    };
    canvas.addEventListener("click", handler);
    return () => canvas.removeEventListener("click", handler);
  }, [onNodeClick]);

  // Hover cursor: pointer when over a node
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const handler = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.offsetWidth / rect.width;
      const scaleY = canvas.offsetHeight / rect.height;
      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;
      canvas.style.cursor = hitTest(layoutRef.current, x, y) ? "pointer" : "default";
    };
    canvas.addEventListener("mousemove", handler);
    return () => canvas.removeEventListener("mousemove", handler);
  }, []);

  if (!nodes.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-line bg-bg-2 text-xs text-faint"
        style={{ height }}
      >
        No graph data
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className="w-full rounded-lg border border-line bg-bg-2"
      style={{ height, display: "block" }}
    />
  );
}
