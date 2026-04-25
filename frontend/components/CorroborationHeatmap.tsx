"use client";
import { HeatmapCell } from "@/types";

const CATEGORIES = [
  "medical_access", "nutrition", "elderly_care", "water_sanitation",
  "shelter", "education", "mental_health", "livelihood", "other",
];
const CHANNELS = ["whatsapp", "app", "ocr", "csv", "debrief"];
const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp", app: "App", ocr: "OCR", csv: "CSV", debrief: "Debrief",
};
const CATEGORY_LABELS: Record<string, string> = {
  medical_access: "Medical", nutrition: "Nutrition", elderly_care: "Elderly",
  water_sanitation: "Water", shelter: "Shelter", education: "Education",
  mental_health: "Mental", livelihood: "Livelihood", other: "Other",
};

interface Props {
  cells: HeatmapCell[];
  loading?: boolean;
}

export function CorroborationHeatmap({ cells, loading }: Props) {
  // Build lookup: category → channel → count
  const lookup: Record<string, Record<string, number>> = {};
  for (const cell of cells) {
    if (!lookup[cell.need_category]) lookup[cell.need_category] = {};
    lookup[cell.need_category][cell.source_channel] = cell.count;
  }

  const maxVal = Math.max(1, ...cells.map((c) => c.count));

  function cellOpacity(cat: string, chan: string) {
    const v = lookup[cat]?.[chan] ?? 0;
    return v / maxVal;
  }

  if (loading) {
    return <div className="shimmer h-48 rounded-xl" />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="text-left text-slate-500 font-medium py-2 pr-3 w-24">Category</th>
            {CHANNELS.map((ch) => (
              <th key={ch} className="text-center text-slate-500 font-medium py-2 px-1">
                {CHANNEL_LABELS[ch]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {CATEGORIES.map((cat) => {
            const hasAny = CHANNELS.some((ch) => (lookup[cat]?.[ch] ?? 0) > 0);
            return (
              <tr key={cat} className={hasAny ? "" : "opacity-30"}>
                <td className="text-slate-400 py-1.5 pr-3 font-medium">{CATEGORY_LABELS[cat]}</td>
                {CHANNELS.map((ch) => {
                  const count = lookup[cat]?.[ch] ?? 0;
                  const alpha = cellOpacity(cat, ch);
                  return (
                    <td key={ch} className="text-center py-1.5 px-1">
                      <div
                        className="mx-auto w-8 h-6 rounded-md flex items-center justify-center text-xs font-mono transition-all"
                        style={{
                          background: `rgba(20,184,166,${alpha * 0.8 + 0.05})`,
                          border: `1px solid rgba(20,184,166,${alpha * 0.5 + 0.1})`,
                          color: alpha > 0.3 ? "#ccfbef" : "#475569",
                        }}
                        title={`${CATEGORY_LABELS[cat]} / ${CHANNEL_LABELS[ch]}: ${count}`}
                      >
                        {count || "·"}
                      </div>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
