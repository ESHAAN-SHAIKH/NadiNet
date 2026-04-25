"use client";
import { useState } from "react";
import { DecaySimulator } from "@/components/DecaySimulator";
import { useNeeds, useReporters, useUpdateReporterTrust } from "@/lib/api";
import { Reporter } from "@/types";

function trustColor(t: number) {
  if (t >= 0.85) return "text-teal-400 bg-teal-500/10 border-teal-500/30";
  if (t >= 0.65) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-rose-400 bg-rose-500/10 border-rose-500/30";
}

function decayLabel(t: number) {
  if (t >= 0.85) return { label: "slow", color: "text-teal-400" };
  if (t >= 0.65) return { label: "normal", color: "text-amber-400" };
  return { label: "fast", color: "text-rose-400" };
}

export default function DecayPage() {
  const { data: needs = [], isLoading: needsLoading } = useNeeds("active");
  const { data: reporters = [], isLoading: repLoading } = useReporters();
  const updateTrust = useUpdateReporterTrust();
  const [editId, setEditId] = useState<string | null>(null);
  const [editScore, setEditScore] = useState(0);
  const [editJust, setEditJust] = useState("");

  function startEdit(r: Reporter) {
    setEditId(r.id);
    setEditScore(r.trust_score);
    setEditJust("");
  }
  async function saveEdit(r: Reporter) {
    if (!editJust.trim()) return alert("Justification required");
    await updateTrust.mutateAsync({ id: r.id, trust_score: editScore, justification: editJust });
    setEditId(null);
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Trust Decay</h1>
        <p className="text-sm text-slate-500 mt-0.5">Simulate temporal decay and manage reporter trust scores</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Left: Decay Simulator */}
        <div className="card">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Decay Simulator</h2>
          <DecaySimulator needs={needs} loading={needsLoading} />
        </div>

        {/* Right: Reporter calibration */}
        <div className="card">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Reporter Calibration</h2>
          {repLoading ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="shimmer h-16 rounded-xl" />)}</div>
          ) : (
            <div className="space-y-3">
              {reporters.map((r) => {
                const dl = decayLabel(r.trust_score);
                const tc = trustColor(r.trust_score);
                const verifyPct = r.reports_filed > 0
                  ? Math.round((r.reports_verified / r.reports_filed) * 100)
                  : 0;

                return (
                  <div key={r.id} className="p-3.5 rounded-xl border border-slate-700/60 bg-slate-800/30 space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-white">{r.name || r.phone}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-slate-500">{r.reports_filed} filed</span>
                          <span className="text-xs text-slate-600">·</span>
                          <span className="text-xs text-slate-500">{verifyPct}% verified</span>
                          <span className="text-xs text-slate-600">·</span>
                          <span className={`text-xs font-medium ${dl.color}`}>{dl.label} decay</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`score-badge ${tc}`}>
                          {Math.round(r.trust_score * 100)}%
                        </span>
                        <button
                          onClick={() => editId === r.id ? setEditId(null) : startEdit(r)}
                          className="text-xs text-slate-500 hover:text-slate-300 border border-slate-700 hover:border-slate-500 px-2 py-1 rounded-lg transition-all"
                        >
                          Edit
                        </button>
                      </div>
                    </div>

                    {editId === r.id && (
                      <div className="pt-2 border-t border-slate-700 space-y-2">
                        <div>
                          <label className="text-xs text-slate-500 mb-1 block">Trust score: {Math.round(editScore * 100)}%</label>
                          <input
                            type="range" min={0} max={1} step={0.01}
                            value={editScore}
                            onChange={(e) => setEditScore(parseFloat(e.target.value))}
                            className="w-full accent-teal-400"
                          />
                        </div>
                        <input
                          placeholder="Justification (required)"
                          value={editJust}
                          onChange={(e) => setEditJust(e.target.value)}
                          className="w-full text-xs bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-300 placeholder-slate-600 outline-none focus:border-teal-500"
                        />
                        <button
                          onClick={() => saveEdit(r)}
                          disabled={updateTrust.isPending}
                          className="text-xs px-3 py-1.5 bg-teal-500/20 text-teal-400 border border-teal-500/30 rounded-lg hover:bg-teal-500/30 transition-all"
                        >
                          Save
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
