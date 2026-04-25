"use client";
import { useState, useMemo } from "react";
import { useSignalLog } from "@/lib/api";
import { SignalLogEntry } from "@/types";

const EVENT_STYLES: Record<string, { dot: string; label: string }> = {
  SIGNAL_INGESTED:      { dot: "bg-slate-500",   label: "Signal" },
  NEED_CORROBORATED:    { dot: "bg-teal-500",     label: "Corroborated" },
  NEED_PROMOTED:        { dot: "bg-amber-500",    label: "Promoted" },
  TASK_DISPATCHED:      { dot: "bg-blue-500",     label: "Dispatched" },
  TASK_ACCEPTED:        { dot: "bg-emerald-500",  label: "Accepted" },
  TASK_DECLINED:        { dot: "bg-red-500",      label: "Declined" },
  DECAY_WARNING:        { dot: "bg-amber-500",    label: "Decay" },
  REVERIFICATION_SENT:  { dot: "bg-purple-500",   label: "Reverify" },
  DEBRIEF_RECEIVED:     { dot: "bg-emerald-500",  label: "Debrief" },
  NEED_ARCHIVED:        { dot: "bg-slate-600",    label: "Archived" },
};

const ALL_TYPES = Object.keys(EVENT_STYLES);

function formatTime(ts: string) {
  return new Intl.DateTimeFormat("en-IN", {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }).format(new Date(ts));
}

export default function LogPage() {
  const { data: log = [], isLoading } = useSignalLog(200);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(ALL_TYPES));
  const [search, setSearch] = useState("");

  function toggleType(t: string) {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });
  }

  const filtered = useMemo(() =>
    log.filter((e) =>
      selectedTypes.has(e.event_type) &&
      (!search || e.description.toLowerCase().includes(search.toLowerCase()))
    ),
    [log, selectedTypes, search]
  );

  async function exportCsv() {
    const rows = [
      ["timestamp", "event_type", "description"],
      ...filtered.map((e) => [e.timestamp, e.event_type, e.description]),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "nadinet-log.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Signal Log</h1>
          <p className="text-sm text-slate-500 mt-0.5">Chronological audit trail of all system events</p>
        </div>
        <button
          onClick={exportCsv}
          className="text-xs px-3 py-2 bg-slate-800 border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500 rounded-xl transition-all font-medium"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Filter bar */}
      <div className="card space-y-3">
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search events…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 text-sm bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-300 placeholder-slate-600 outline-none focus:border-teal-500 transition-colors"
          />
          <button
            onClick={() => setSelectedTypes(new Set(ALL_TYPES))}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2"
          >
            All
          </button>
          <button
            onClick={() => setSelectedTypes(new Set())}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2"
          >
            None
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {ALL_TYPES.map((t) => {
            const style = EVENT_STYLES[t];
            const active = selectedTypes.has(t);
            return (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border transition-all
                  ${active
                    ? "border-slate-600 bg-slate-800 text-slate-300"
                    : "border-slate-800 bg-transparent text-slate-600"
                  }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${active ? style.dot : "bg-slate-700"}`} />
                {style.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Log entries */}
      <div className="space-y-1">
        {isLoading ? (
          [...Array(8)].map((_, i) => <div key={i} className="shimmer h-14 rounded-xl" />)
        ) : filtered.length === 0 ? (
          <div className="card text-center py-16 text-slate-600">
            <p className="text-3xl mb-2">📋</p>
            <p className="text-sm">No events match the current filters</p>
          </div>
        ) : (
          filtered.map((entry) => {
            const style = EVENT_STYLES[entry.event_type] ?? EVENT_STYLES.SIGNAL_INGESTED;
            const isArchived = entry.event_type === "NEED_ARCHIVED";
            return (
              <div
                key={entry.id + entry.timestamp}
                className={`flex items-start gap-4 px-4 py-3 rounded-xl border border-transparent hover:border-slate-700/60 hover:bg-slate-800/30 transition-all ${isArchived ? "opacity-50" : ""}`}
              >
                {/* Timeline dot */}
                <div className="flex flex-col items-center shrink-0 pt-1">
                  <span className={`w-2.5 h-2.5 rounded-full ${style.dot}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${isArchived ? "italic text-slate-500" : "text-slate-200"}`}>
                    {entry.description}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-slate-600 font-mono">{formatTime(entry.timestamp)}</span>
                    <span className="text-xs text-slate-700">·</span>
                    <span className="text-xs text-slate-600">{style.label}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <p className="text-xs text-slate-700 text-center">{filtered.length} events shown</p>
    </div>
  );
}
