"use client";

import { useEffect, useRef, useCallback } from "react";

export interface GraphNode {
  id: string;
  label?: string;
  type?: string;
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
}

const TYPE_COLORS: Record<string, string> = {
  cytokine:    "#87f085",
  gene:        "#f5c062",
  therapeutic: "#f08987",
  pathway:     "#6ab4f5",
  disease:     "#c78bff",
  cell_type:   "#f5b4e8",
  Unknown:     "#6b7280",
};

const EDGE_COLOR = "rgba(255,255,255,0.12)";
const LABEL_COLOR = "#b0bec5";

function nodeColor(type: string | undefined): string {
  return TYPE_COLORS[type ?? "Unknown"] ?? TYPE_COLORS.Unknown;
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
  const repulsion = k * k * 2;
  const spring = 0.04;
  const damping = 0.8;

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 1 - iter / iterations;

    // Repulsion: all pairs
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

    // Spring attraction: edges
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

    // Center gravity
    for (const n of nodes) {
      n.vx += (width / 2 - n.x) * 0.005;
      n.vy += (height / 2 - n.y) * 0.005;
    }

    // Integrate + damp + clamp
    for (const n of nodes) {
      n.vx *= damping;
      n.vy *= damping;
      const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
      const maxSpeed = k * temp * 3;
      if (speed > maxSpeed) {
        n.vx = (n.vx / speed) * maxSpeed;
        n.vy = (n.vy / speed) * maxSpeed;
      }
      n.x = Math.max(32, Math.min(width - 32, n.x + n.vx));
      n.y = Math.max(24, Math.min(height - 24, n.y + n.vy));
    }
  }
}

function drawGraph(
  ctx: CanvasRenderingContext2D,
  nodes: LayoutNode[],
  edges: GraphEdge[],
  idxMap: Map<string, number>,
  highlightId: string | undefined,
  dpr: number,
) {
  const { width, height } = ctx.canvas;
  ctx.clearRect(0, 0, width, height);

  // Edges
  for (const edge of edges) {
    const si = idxMap.get(edge.source);
    const ti = idxMap.get(edge.target);
    if (si == null || ti == null) continue;
    const s = nodes[si];
    const t = nodes[ti];
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = EDGE_COLOR;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Nodes
  const R = 7;
  for (const n of nodes) {
    const isHighlight = n.id === highlightId;
    ctx.beginPath();
    ctx.arc(n.x, n.y, isHighlight ? R * 1.6 : R, 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n.type);
    ctx.globalAlpha = isHighlight ? 1 : 0.8;
    ctx.fill();
    ctx.globalAlpha = 1;

    if (isHighlight || nodes.length <= 40) {
      const label = (n.label ?? n.id).slice(0, 18);
      ctx.font = "10px monospace";
      ctx.fillStyle = LABEL_COLOR;
      ctx.textAlign = "center";
      ctx.fillText(label, n.x, n.y + R + 12);
    }
  }
}

export default function KnowledgeGraph({
  nodes,
  edges,
  height = 380,
  highlightNode,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const layoutRef = useRef<LayoutNode[]>([]);
  // Sync highlightNode into a ref so draw() can read it without being a dep
  const highlightRef = useRef<string | undefined>(highlightNode);
  highlightRef.current = highlightNode;

  // Stable draw function: reads positions from layoutRef, highlight from highlightRef
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const idxMap = new Map(layoutRef.current.map((n, i) => [n.id, i]));
    drawGraph(ctx, layoutRef.current, edges, idxMap, highlightRef.current, dpr);
  }, [edges]);

  // Layout effect: randomizes positions and runs force sim — only reruns when
  // nodes or edges change, NOT when highlightNode changes
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

    // Initialize layout positions
    layoutRef.current = nodes.map((n) => ({
      ...n,
      x: Math.random() * w * 0.8 + w * 0.1,
      y: Math.random() * h * 0.8 + h * 0.1,
      vx: 0,
      vy: 0,
    }));

    runForce(layoutRef.current, edges, w, h, 200);
    draw();
  }, [nodes, edges, height, draw]);

  // Draw-only effect: repaints with updated highlight without re-laying out
  useEffect(() => {
    draw();
  }, [highlightNode, draw]);

  // ResizeObserver: resize canvas and redraw without re-laying out
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
