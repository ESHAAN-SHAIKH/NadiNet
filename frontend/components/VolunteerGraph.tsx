"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { KinshipGraph, KinshipNode, KinshipEdge } from "@/types";

interface NodePos extends KinshipNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface Props {
  graph: KinshipGraph;
  loading?: boolean;
  onSelectNode?: (node: KinshipNode | null) => void;
  selectedNodeId?: string | null;
}

export function VolunteerGraph({ graph, loading, onSelectNode, selectedNodeId }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<NodePos[]>([]);
  const frameRef = useRef<number>(0);
  const [hover, setHover] = useState<string | null>(null);
  const [dims, setDims] = useState({ w: 800, h: 500 });

  // Initialize node positions
  useEffect(() => {
    if (!graph.nodes.length) return;
    const w = canvasRef.current?.clientWidth || 800;
    const h = canvasRef.current?.clientHeight || 500;
    setDims({ w, h });

    nodesRef.current = graph.nodes.map((n, i) => ({
      ...n,
      x: (Math.cos((i / graph.nodes.length) * Math.PI * 2) * 0.35 + 0.5) * w,
      y: (Math.sin((i / graph.nodes.length) * Math.PI * 2) * 0.35 + 0.5) * h,
      vx: 0,
      vy: 0,
    }));
  }, [graph.nodes]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { w, h } = dims;
    ctx.clearRect(0, 0, w, h);

    const nodes = nodesRef.current;
    const edges = graph.edges;

    // Build adjacency for highlighting
    const connectedTo = new Set<string>();
    if (selectedNodeId) {
      for (const e of edges) {
        if (e.source === selectedNodeId) connectedTo.add(e.target);
        if (e.target === selectedNodeId) connectedTo.add(e.source);
      }
    }

    const isHighlighted = (id: string) =>
      !selectedNodeId || id === selectedNodeId || connectedTo.has(id);

    // Draw edges
    for (const edge of edges) {
      const a = nodes.find((n) => n.id === edge.source);
      const b = nodes.find((n) => n.id === edge.target);
      if (!a || !b) continue;

      const edgeHighlighted = !selectedNodeId ||
        (isHighlighted(edge.source) && isHighlighted(edge.target));

      ctx.save();
      ctx.globalAlpha = edgeHighlighted ? 0.8 : 0.1;
      ctx.strokeStyle = edge.quality_score >= 0.7 ? "#14b8a6" : "#64748b";
      ctx.lineWidth = Math.min(4, 1 + edge.co_deployments * 0.5);
      if (edge.quality_score < 0.7) {
        ctx.setLineDash([4, 4]);
      }
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      ctx.restore();
    }

    // Draw nodes
    for (const node of nodes) {
      const highlighted = isHighlighted(node.id);
      const isHover = hover === node.id;
      const isSelected = node.id === selectedNodeId;

      const radius = 10 + node.trust_score * 12;
      const color = node.is_available ? "#14b8a6" : "#64748b";

      ctx.save();
      ctx.globalAlpha = highlighted ? 1 : 0.25;

      // Glow for selected
      if (isSelected || isHover) {
        ctx.shadowColor = color;
        ctx.shadowBlur = 20;
      }

      // Circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? color : `${color}33`;
      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.fill();
      ctx.stroke();

      // Initials
      ctx.fillStyle = isSelected ? "#fff" : color;
      ctx.font = `bold ${Math.round(radius * 0.6)}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(node.initials, node.x, node.y);

      ctx.restore();
    }

    // Apply simple force-directed physics
    const REPULSION = 3000;
    const ATTRACTION = 0.01;
    const DAMPING = 0.8;

    for (let i = 0; i < nodes.length; i++) {
      nodes[i].vx = 0;
      nodes[i].vy = 0;
      // Center gravity
      nodes[i].vx += (w / 2 - nodes[i].x) * 0.002;
      nodes[i].vy += (h / 2 - nodes[i].y) * 0.002;
      // Node repulsion
      for (let j = 0; j < nodes.length; j++) {
        if (i === j) continue;
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = REPULSION / (dist * dist);
        nodes[i].vx += (dx / dist) * force * 0.1;
        nodes[i].vy += (dy / dist) * force * 0.1;
      }
    }
    // Edge attraction
    for (const edge of edges) {
      const a = nodes.find((n) => n.id === edge.source);
      const b = nodes.find((n) => n.id === edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      a.vx += dx * ATTRACTION;
      a.vy += dy * ATTRACTION;
      b.vx -= dx * ATTRACTION;
      b.vy -= dy * ATTRACTION;
    }
    for (const n of nodes) {
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x = Math.max(30, Math.min(w - 30, n.x + n.vx));
      n.y = Math.max(30, Math.min(h - 30, n.y + n.vy));
    }

    frameRef.current = requestAnimationFrame(draw);
  }, [graph, dims, selectedNodeId, hover]);

  useEffect(() => {
    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [draw]);

  function getNodeAt(x: number, y: number): NodePos | null {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const cx = x - rect.left;
    const cy = y - rect.top;
    for (const n of nodesRef.current) {
      const r = 10 + n.trust_score * 12;
      const dx = n.x - cx;
      const dy = n.y - cy;
      if (dx * dx + dy * dy <= r * r) return n;
    }
    return null;
  }

  if (loading) return <div className="shimmer rounded-xl" style={{ height: 500 }} />;

  return (
    <canvas
      ref={canvasRef}
      width={dims.w}
      height={dims.h}
      className="w-full rounded-xl cursor-pointer"
      style={{ height: 500, background: "#0b1120" }}
      onMouseMove={(e) => {
        const n = getNodeAt(e.clientX, e.clientY);
        setHover(n?.id ?? null);
      }}
      onMouseLeave={() => setHover(null)}
      onClick={(e) => {
        const n = getNodeAt(e.clientX, e.clientY);
        onSelectNode?.(n ? { ...n } : null);
      }}
    />
  );
}
