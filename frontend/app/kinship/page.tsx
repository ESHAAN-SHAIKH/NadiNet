"use client";
import { useState } from "react";
import { VolunteerGraph } from "@/components/VolunteerGraph";
import { useKinshipGraph } from "@/lib/api";
import { KinshipNode } from "@/types";

export default function KinshipPage() {
  const { data: graph, isLoading } = useKinshipGraph();
  const [selectedNode, setSelectedNode] = useState<KinshipNode | null>(null);

  const safeGraph = graph ?? { nodes: [], edges: [] };

  function getKinshipPartners(nodeId: string) {
    if (!graph) return [];
    const partners: string[] = [];
    for (const e of graph.edges) {
      if (e.source === nodeId) partners.push(e.target);
      if (e.target === nodeId) partners.push(e.source);
    }
    return graph.nodes.filter((n) => partners.includes(n.id));
  }

  const partners = selectedNode ? getKinshipPartners(selectedNode.id) : [];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Kinship Graph</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Force-directed co-deployment network · {safeGraph.nodes.length} volunteers, {safeGraph.edges.length} edges
        </p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-teal-500" />Available
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-slate-600" />Offline
        </div>
        <div className="flex items-center gap-2">
          <span className="w-8 h-0.5 bg-teal-500" />Quality ≥0.7
        </div>
        <div className="flex items-center gap-2">
          <span className="w-8 h-0.5 border-t-2 border-dashed border-slate-500" />Quality &lt;0.7
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Node size ∝ trust score</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Graph canvas */}
        <div className="xl:col-span-3 card p-3">
          <VolunteerGraph
            graph={safeGraph}
            loading={isLoading}
            onSelectNode={setSelectedNode}
            selectedNodeId={selectedNode?.id}
          />
        </div>

        {/* Detail panel */}
        <div className="space-y-4">
          {selectedNode ? (
            <div className="card animate-fade-in">
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold
                  ${selectedNode.is_available ? "bg-teal-500/20 text-teal-400 border border-teal-500/30" : "bg-slate-700 text-slate-400 border border-slate-600"}`}>
                  {selectedNode.initials}
                </div>
                <div>
                  <p className="text-base font-bold text-white">{selectedNode.name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {selectedNode.is_available ? "🟢 Available" : "⚫ Offline"}
                  </p>
                </div>
              </div>

              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Zone</span>
                  <span className="text-slate-300">{selectedNode.zone_id || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Trust score</span>
                  <span className="font-mono text-teal-400">{Math.round(selectedNode.trust_score * 100)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Completion</span>
                  <span className="font-mono text-slate-300">{Math.round(selectedNode.completion_rate * 100)}%</span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-1">Skills</span>
                  <div className="flex flex-wrap gap-1">
                    {selectedNode.skills.map((s) => (
                      <span key={s} className="text-xs bg-slate-800 border border-slate-700 text-slate-400 px-2 py-0.5 rounded-md">
                        {s.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>

                {partners.length > 0 && (
                  <div>
                    <span className="text-slate-500 block mb-1">Kinship partners ({partners.length})</span>
                    {partners.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => setSelectedNode(p)}
                        className="flex items-center gap-2 w-full text-left py-1.5 text-xs text-slate-300 hover:text-white transition-colors"
                      >
                        <span className="w-6 h-6 rounded-full bg-teal-500/15 border border-teal-500/30 text-teal-400 flex items-center justify-center text-xs font-bold shrink-0">
                          {p.initials}
                        </span>
                        {p.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card text-center py-8 text-slate-600">
              <p className="text-3xl mb-2">🕸</p>
              <p className="text-sm">Click a node to see volunteer details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
