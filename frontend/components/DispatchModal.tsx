"use client";
import { useState } from "react";
import { Need, Candidate } from "@/types";
import { useCandidates, useDispatch } from "@/lib/api";

const SCORE_COMPONENTS = [
  { key: "f_score", label: "F", color: "#6366f1", desc: "Frequency" },
  { key: "u_score", label: "U", color: "#8b5cf6", desc: "Urgency" },
  { key: "g_score", label: "G", color: "#3b82f6", desc: "Gap" },
  { key: "v_score", label: "V", color: "#ec4899", desc: "Vulnerability" },
  { key: "c_score", label: "C", color: "#f59e0b", desc: "Corroboration" },
  { key: "t_score", label: "T", color: "#10b981", desc: "Trust decay" },
] as const;

interface Props {
  need: Need;
  onClose: () => void;
}

export function DispatchModal({ need, onClose }: Props) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [dispatched, setDispatched] = useState(false);

  const { data: result, isLoading } = useCandidates(need.id, [], 2);
  const dispatch = useDispatch();

  const totalFill = (need.f_score ?? 0) * (need.u_score ?? 0) * (need.g_score ?? 0.8) *
    (need.v_score ?? 1) * (need.c_score ?? 0.5) * (need.t_score ?? 1);

  function toggleCandidate(id: string) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function handleDispatch() {
    if (!selectedIds.length) return;
    await dispatch.mutateAsync({ need_id: need.id, volunteer_ids: selectedIds });
    setDispatched(true);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <h2 className="text-base font-bold text-white">Dispatch Volunteers</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Left: Need details + score breakdown */}
          <div className="w-52 shrink-0 border-r border-slate-800 p-5 overflow-y-auto">
            <div className="mb-4">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Need</span>
              <p className="text-sm font-bold text-white mt-1 capitalize">{need.need_category.replace(/_/g, " ")}</p>
              <p className="text-xs text-slate-400 mt-0.5">{need.zone_id}</p>
            </div>

            <div className="mb-1">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Priority Score</span>
              <p className="text-2xl font-mono font-bold text-teal-400 mt-1">{need.priority_score}</p>
            </div>

            {/* Score breakdown stacked bar */}
            <div className="mt-4 space-y-2">
              {SCORE_COMPONENTS.map(({ key, label, color, desc }) => {
                const val = (need as unknown as Record<string, number | null>)[key] ?? 0;
                const pct = Math.round((val as number) * 100);
                return (
                  <div key={key}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span style={{ color }} className="font-semibold">{label}</span>
                      <span className="text-slate-500">{desc}</span>
                      <span className="font-mono text-slate-300">{pct}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, background: color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Candidate list */}
          <div className="flex-1 overflow-y-auto p-5">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Matching Volunteers {result && `(${result.pool_size} in pool)`}
            </p>

            {isLoading && (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <div key={i} className="shimmer h-16 rounded-xl" />)}
              </div>
            )}

            {result?.candidates.map((c) => {
              const isRec = result.recommended_ids.includes(c.id);
              const isSelected = selectedIds.includes(c.id);
              return (
                <button
                  key={c.id}
                  onClick={() => toggleCandidate(c.id)}
                  className={`
                    w-full text-left p-3 rounded-xl mb-2 border transition-all
                    ${isSelected
                      ? "border-teal-500/60 bg-teal-500/5"
                      : "border-slate-700 bg-slate-800/40 hover:border-slate-600"
                    }
                    ${isRec ? "ring-1 ring-teal-500/30" : ""}
                  `}
                >
                  <div className="flex items-center gap-3">
                    {/* Avatar */}
                    <div className={`
                      w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold
                      ${c.is_available ? "bg-teal-500/20 text-teal-400" : "bg-slate-700 text-slate-500"}
                    `}>
                      {c.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white truncate">{c.name}</span>
                        {isRec && (
                          <span className="text-xs bg-teal-500/20 text-teal-400 border border-teal-500/30 px-1.5 rounded">
                            {result.kinship_bonus ? "paired 🤝" : "recommended"}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs text-slate-500">{c.zone_id || "—"}</span>
                        <span className="text-xs text-slate-600">·</span>
                        <span className="text-xs text-slate-500">{Math.round(c.completion_rate * 100)}% complete</span>
                        <span className="text-xs text-slate-600">·</span>
                        <span className="text-xs text-slate-500">trust {Math.round(c.trust_score * 100)}%</span>
                      </div>
                    </div>

                    <span className={`
                      font-mono text-xs border px-2 py-0.5 rounded shrink-0
                      ${isSelected ? "border-teal-500/50 text-teal-400" : "border-slate-700 text-slate-500"}
                    `}>
                      {c.pass2_score.toFixed(2)}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {selectedIds.length} volunteer{selectedIds.length !== 1 ? "s" : ""} selected
          </span>
          {dispatched ? (
            <div className="flex items-center gap-2 text-teal-400 text-sm font-semibold">
              <span>✓</span> WhatsApp sent!
            </div>
          ) : (
            <button
              onClick={handleDispatch}
              disabled={!selectedIds.length || dispatch.isPending}
              className="px-4 py-2 bg-teal-500 hover:bg-teal-400 disabled:opacity-40 text-white text-sm font-semibold rounded-xl transition-all"
            >
              {dispatch.isPending ? "Dispatching…" : "Dispatch via WhatsApp"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
