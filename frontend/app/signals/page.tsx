"use client";
import { useState } from "react";
import { NeedQueue } from "@/components/NeedQueue";
import { CorroborationHeatmap } from "@/components/CorroborationHeatmap";
import { DispatchModal } from "@/components/DispatchModal";
import { useNeeds, useHeatmap, usePromoteNeed } from "@/lib/api";
import { Need } from "@/types";

const CHANNEL_COLORS: Record<string, string> = {
  whatsapp: "bg-green-500/20 text-green-400 border-green-500/30",
  app:      "bg-blue-500/20 text-blue-400 border-blue-500/30",
  ocr:      "bg-purple-500/20 text-purple-400 border-purple-500/30",
  csv:      "bg-amber-500/20 text-amber-400 border-amber-500/30",
  debrief:  "bg-teal-500/20 text-teal-400 border-teal-500/30",
};

export default function SignalsPage() {
  const [selectedNeed, setSelectedNeed] = useState<Need | null>(null);
  const { data: active = [], isLoading: activeLoading } = useNeeds("active");
  const { data: watch = [], isLoading: watchLoading } = useNeeds("watch");
  const { data: heatmap = [], isLoading: hmLoading } = useHeatmap();
  const promote = usePromoteNeed();

  // Channel counts summary
  const channelCounts: Record<string, number> = {};
  for (const c of heatmap) {
    channelCounts[c.source_channel] = (channelCounts[c.source_channel] || 0) + c.count;
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Need Signals</h1>
        <p className="text-sm text-slate-500 mt-0.5">All active needs and unverified watch signals</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Main area */}
        <div className="xl:col-span-3 space-y-6">
          {/* Active Needs */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Active Needs</h2>
              <span className="text-xs text-teal-400 bg-teal-500/10 border border-teal-500/20 px-2 py-1 rounded-lg">
                {active.length} corroborated
              </span>
            </div>
            <NeedQueue needs={active} loading={activeLoading} onSelect={setSelectedNeed} selected={selectedNeed?.id} />
          </div>

          {/* Heatmap */}
          <div className="card">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Corroboration Heatmap</h2>
            <CorroborationHeatmap cells={heatmap} loading={hmLoading} />
          </div>

          {/* Watch signals */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Unverified Signals</h2>
              <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded-lg">
                {watch.length} watch
              </span>
            </div>
            {watchLoading ? (
              <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="shimmer h-12 rounded-xl" />)}</div>
            ) : watch.length === 0 ? (
              <p className="text-slate-500 text-sm py-4 text-center">No unverified signals pending</p>
            ) : (
              <div className="space-y-2">
                {watch.map((n) => (
                  <div key={n.id} className="flex items-center gap-3 p-3 rounded-xl border border-slate-700/60 bg-slate-800/30">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-300 font-medium capitalize">
                        {n.need_category.replace(/_/g, " ")} · {n.zone_id}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {new Date(n.first_reported).toLocaleString()}
                      </p>
                    </div>
                    <button
                      onClick={() => promote.mutate({ needId: n.id })}
                      disabled={promote.isPending}
                      className="text-xs px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg transition-colors font-medium"
                    >
                      Promote
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar: channel breakdown */}
        <div className="space-y-4">
          <div className="card">
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Source Channels Today</h2>
            <div className="space-y-2">
              {Object.entries(channelCounts).map(([ch, count]) => (
                <div key={ch} className="flex items-center justify-between">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded border ${CHANNEL_COLORS[ch] || "bg-slate-700 text-slate-400 border-slate-600"}`}>
                    {ch}
                  </span>
                  <span className="text-sm font-mono font-bold text-slate-300">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {selectedNeed && <DispatchModal need={selectedNeed} onClose={() => setSelectedNeed(null)} />}
    </div>
  );
}
