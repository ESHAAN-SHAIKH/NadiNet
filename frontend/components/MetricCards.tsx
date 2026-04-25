"use client";
import { DashboardStats } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  medical_access:  "text-rose-400",
  nutrition:       "text-orange-400",
  elderly_care:    "text-purple-400",
  water_sanitation:"text-blue-400",
  shelter:         "text-amber-400",
  education:       "text-indigo-400",
  mental_health:   "text-pink-400",
  livelihood:      "text-green-400",
  other:           "text-slate-400",
};

interface Card {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  icon: string;
  glow?: string;
}

interface MetricCardsProps {
  stats: DashboardStats | undefined;
  loading?: boolean;
}

export function MetricCards({ stats, loading }: MetricCardsProps) {
  const cards: Card[] = [
    {
      label: "Active Needs",
      value: loading ? "—" : stats?.total_active_needs ?? 0,
      sub: `${stats?.total_watch_signals ?? 0} watch signals`,
      color: "from-teal-500 to-cyan-600",
      icon: "🎯",
      glow: "shadow-teal-500/20",
    },
    {
      label: "Corroborated",
      value: loading ? "—" : stats?.total_active_needs ?? 0,
      sub: `${stats?.needs_needing_reverification ?? 0} need reverification`,
      color: "from-violet-500 to-purple-600",
      icon: "🔗",
      glow: "shadow-violet-500/20",
    },
    {
      label: "Kinship Matches",
      value: loading ? "—" : stats?.kinship_matches_today ?? 0,
      sub: "today",
      color: "from-amber-500 to-orange-600",
      icon: "🤝",
      glow: "shadow-amber-500/20",
    },
    {
      label: "Avg Decay Age",
      value: loading ? "—" : `${stats?.avg_decay_age_days ?? 0}d`,
      sub: `${stats?.available_volunteers ?? 0} volunteers ready`,
      color: "from-rose-500 to-pink-600",
      icon: "⏳",
      glow: "shadow-rose-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map((card, i) => (
        <div
          key={i}
          className={`card relative overflow-hidden shadow-lg ${card.glow}`}
        >
          {/* Gradient bar */}
          <div className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r ${card.color}`} />

          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{card.label}</p>
              <p className="text-3xl font-bold text-white mt-1 font-mono">{card.value}</p>
              {card.sub && <p className="text-xs text-slate-500 mt-1">{card.sub}</p>}
            </div>
            <span className="text-2xl">{card.icon}</span>
          </div>

          {loading && (
            <div className="absolute inset-0 shimmer opacity-40" />
          )}
        </div>
      ))}
    </div>
  );
}
