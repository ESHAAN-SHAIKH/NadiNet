"use client";
import { useState, useMemo } from "react";
import { Need } from "@/types";

const HALF_LIVES: Record<string, number> = {
  medical_access: 96, nutrition: 144, elderly_care: 192, mental_health: 192,
  water_sanitation: 288, shelter: 336, education: 336, livelihood: 312, other: 240,
};

function simulateT(currentT: number, lambdaPerHour: number, additionalDays: number): number {
  const t = currentT * Math.exp(-lambdaPerHour * additionalDays * 24);
  return Math.max(0, Math.min(1, t));
}

function tColor(t: number) {
  if (t > 0.6) return { bar: "#10b981", text: "text-emerald-400" };
  if (t > 0.2)  return { bar: "#f59e0b", text: "text-amber-400" };
  return { bar: "#ef4444", text: "text-rose-400" };
}

interface Props { needs: Need[]; loading?: boolean; }

export function DecaySimulator({ needs, loading }: Props) {
  const [simDays, setSimDays] = useState(0);

  const results = useMemo(() =>
    needs.map((n) => {
      const lambda = n.lambda_per_hour ?? (Math.LN2 / (HALF_LIVES[n.need_category] ?? 240));
      const currentT = n.t_score ?? 1;
      const simT = simulateT(currentT, lambda, simDays);
      return { need: n, currentT, simT, lambda };
    }),
    [needs, simDays]
  );

  if (loading) return <div className="shimmer h-64 rounded-xl" />;

  return (
    <div>
      {/* Simulator slider */}
      <div className="mb-6 p-4 bg-slate-800/60 rounded-xl border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <label className="text-sm font-medium text-slate-300">
            Simulate days elapsed
          </label>
          <span className="font-mono text-teal-400 text-sm font-bold">+{simDays} days</span>
        </div>
        <input
          type="range" min={0} max={14} step={0.5}
          value={simDays}
          onChange={(e) => setSimDays(parseFloat(e.target.value))}
          className="w-full accent-teal-400"
        />
        <div className="flex justify-between text-xs text-slate-600 mt-1">
          <span>Now</span><span>7d</span><span>14d</span>
        </div>
      </div>

      {/* Need bars */}
      <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
        {results.map(({ need, currentT, simT }) => {
          const c = tColor(simT);
          const willReverify = simT < 0.2;
          return (
            <div key={need.id} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400 truncate max-w-[160px]">
                  <span className="text-slate-500">{need.zone_id} · </span>
                  {need.need_category.replace(/_/g, " ")}
                </span>
                <div className="flex items-center gap-2">
                  <span className={`font-mono font-bold ${c.text}`}>
                    {Math.round(simT * 100)}%
                  </span>
                  {willReverify && (
                    <span className="text-xs bg-rose-500/20 text-rose-400 border border-rose-500/30 px-1.5 py-0.5 rounded">
                      reverify
                    </span>
                  )}
                </div>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden flex">
                {/* Current T in dimmer shade */}
                <div
                  className="h-full rounded-full opacity-30 transition-all"
                  style={{ width: `${currentT * 100}%`, background: c.bar }}
                />
              </div>
              <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden relative -mt-2">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ width: `${simT * 100}%`, background: c.bar }}
                />
              </div>
            </div>
          );
        })}
        {!results.length && (
          <p className="text-slate-500 text-sm text-center py-8">No active needs to simulate.</p>
        )}
      </div>
    </div>
  );
}
