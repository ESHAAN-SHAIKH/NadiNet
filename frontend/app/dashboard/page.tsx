"use client";
import { useState } from "react";
import { MetricCards } from "@/components/MetricCards";
import { NeedQueue } from "@/components/NeedQueue";
import { CorroborationHeatmap } from "@/components/CorroborationHeatmap";
import { DispatchModal } from "@/components/DispatchModal";
import { useDashboardStats, useNeeds, useHeatmap, useVolunteers, useUpdateAvailability } from "@/lib/api";
import { Need } from "@/types";

export default function DashboardPage() {
  const [selectedNeed, setSelectedNeed] = useState<Need | null>(null);

  const { data: stats, isLoading: statsLoading } = useDashboardStats();
  const { data: needs = [], isLoading: needsLoading } = useNeeds("active");
  const { data: heatmap = [], isLoading: heatmapLoading } = useHeatmap();
  const { data: volunteers = [] } = useVolunteers();
  const updateAvail = useUpdateAvailability();

  const availableCount = volunteers.filter((v) => v.is_available).length;

  return (
    <div className="p-6 space-y-6 min-h-screen">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Live coordination overview · {new Date().toLocaleDateString("en-IN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
        </p>
      </div>

      {/* Metric Cards */}
      <MetricCards stats={stats} loading={statsLoading} />

      {/* Two-column layout */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Left: Need Queue */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Active Needs</h2>
            <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded-lg border border-slate-700">
              {needs.length} total
            </span>
          </div>
          <NeedQueue
            needs={needs}
            loading={needsLoading}
            onSelect={setSelectedNeed}
            selected={selectedNeed?.id}
          />
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Corroboration Heatmap */}
          <div className="card">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4">
              Corroboration Heatmap
            </h2>
            <CorroborationHeatmap cells={heatmap} loading={heatmapLoading} />
          </div>

          {/* Volunteer quick panel */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Volunteers</h2>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-teal-400" />
                <span className="text-xs text-slate-400">{availableCount} available</span>
              </div>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {volunteers.slice(0, 8).map((v) => (
                <div key={v.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-800/60 transition-colors">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0
                    ${v.is_available ? "bg-teal-500/20 text-teal-400" : "bg-slate-700 text-slate-500"}`}>
                    {v.name.split(" ").map(w => w[0]).join("").slice(0,2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-200 truncate">{v.name}</p>
                    <p className="text-xs text-slate-500 truncate">{v.zone_id || "—"}</p>
                  </div>
                  <button
                    onClick={() => updateAvail.mutate({ id: v.id, is_available: !v.is_available })}
                    className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-all shrink-0
                      ${v.is_available
                        ? "border-teal-500/40 text-teal-400 bg-teal-500/5 hover:bg-teal-500/10"
                        : "border-slate-700 text-slate-500 hover:border-slate-600"
                      }`}
                  >
                    {v.is_available ? "Available" : "Offline"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Dispatch Modal */}
      {selectedNeed && (
        <DispatchModal need={selectedNeed} onClose={() => setSelectedNeed(null)} />
      )}
    </div>
  );
}
