"use client";
import { useState } from "react";
import { Need } from "@/types";

const CATEGORY_META: Record<string, { color: string; dot: string; label: string }> = {
  medical_access:   { color: "bg-rose-500",   dot: "bg-rose-400",   label: "Medical" },
  nutrition:        { color: "bg-orange-500",  dot: "bg-orange-400", label: "Nutrition" },
  elderly_care:     { color: "bg-purple-500",  dot: "bg-purple-400", label: "Elderly" },
  water_sanitation: { color: "bg-blue-500",    dot: "bg-blue-400",   label: "Water" },
  shelter:          { color: "bg-amber-500",   dot: "bg-amber-400",  label: "Shelter" },
  education:        { color: "bg-indigo-500",  dot: "bg-indigo-400", label: "Education" },
  mental_health:    { color: "bg-pink-500",    dot: "bg-pink-400",   label: "Mental" },
  livelihood:       { color: "bg-green-500",   dot: "bg-green-400",  label: "Livelihood" },
  other:            { color: "bg-slate-500",   dot: "bg-slate-400",  label: "Other" },
};

function scoreColor(score: number) {
  if (score >= 70) return "text-rose-400 border-rose-500/40 bg-rose-500/10";
  if (score >= 40) return "text-amber-400 border-amber-500/40 bg-amber-500/10";
  return "text-teal-400 border-teal-500/40 bg-teal-500/10";
}

function tBar(t: number | null) {
  const val = t ?? 1;
  let color = "bg-teal-500";
  if (val < 0.2) color = "bg-rose-500";
  else if (val < 0.6) color = "bg-amber-500";
  return (
    <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${Math.round(val * 100)}%` }} />
    </div>
  );
}

function freshnessLabel(lastCorroborated: string) {
  const diff = Date.now() - new Date(lastCorroborated).getTime();
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return "< 1h ago";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

interface NeedQueueProps {
  needs: Need[];
  loading?: boolean;
  onSelect?: (need: Need) => void;
  selected?: string | null;
  compact?: boolean;
}

export function NeedQueue({ needs, loading, onSelect, selected, compact = false }: NeedQueueProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="shimmer h-16 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!needs.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-slate-600">
        <span className="text-4xl mb-3">✨</span>
        <p className="text-sm">No active needs — community is doing well!</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {needs.map((need) => {
        const meta = CATEGORY_META[need.need_category] ?? CATEGORY_META.other;
        const isSelected = selected === need.id;

        return (
          <button
            key={need.id}
            onClick={() => onSelect?.(need)}
            className={`
              w-full text-left px-4 py-3 rounded-xl border transition-all duration-200
              ${isSelected
                ? "border-teal-500/50 bg-teal-500/5 shadow-teal-500/10 shadow-md"
                : "border-slate-700/60 bg-slate-800/40 hover:border-slate-600 hover:bg-slate-800/70"
              }
            `}
          >
            <div className="flex items-center gap-3">
              {/* Urgency dot */}
              <span className={`priority-dot ${meta.dot} shrink-0`} />

              {/* Need info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100 truncate">
                    {meta.label}
                  </span>
                  <span className="text-xs text-slate-500 truncate">· {need.zone_id}</span>
                </div>
                {!compact && (
                  <div className="flex items-center gap-3 mt-1">
                    {tBar(need.t_score)}
                    <span className="text-xs text-slate-500">{freshnessLabel(need.last_corroborated)}</span>
                  </div>
                )}
              </div>

              {/* Right side */}
              <div className="flex items-center gap-2 shrink-0">
                <span className={`score-badge ${scoreColor(need.priority_score)}`}>
                  {need.priority_score}
                </span>
                <span className="text-xs text-slate-600 bg-slate-800 border border-slate-700 px-1.5 py-0.5 rounded-md">
                  {need.source_count}src
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
