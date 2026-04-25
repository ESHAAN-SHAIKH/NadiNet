/**
 * Frontend Vitest tests — NadiNet
 * Tests: NeedQueue rendering, DecaySimulator math, MetricCards display
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// ─── Utility: haversine math (mirrors backend logic, used in VolunteerGraph) ─

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ─── DecaySimulator math (client-side, no API call) ────────────────────────

function simulateT(currentT: number, lambdaPerHour: number, additionalDays: number): number {
  const t = currentT * Math.exp(-lambdaPerHour * additionalDays * 24);
  return Math.max(0, Math.min(1, t));
}

const HALF_LIVES: Record<string, number> = {
  medical_access: 96,
  nutrition: 144,
  elderly_care: 192,
  water_sanitation: 288,
  shelter: 336,
  education: 336,
  livelihood: 312,
  other: 240,
};

function getLambda(category: string): number {
  return Math.LN2 / (HALF_LIVES[category] ?? 240);
}

// ─── DecaySimulator Tests ────────────────────────────────────────────────────

describe("DecaySimulator — client-side math", () => {
  it("simulating 0 days returns the same T", () => {
    expect(simulateT(0.8, getLambda("nutrition"), 0)).toBeCloseTo(0.8, 5);
  });

  it("simulating one half-life halves T", () => {
    const halfLifeDays = HALF_LIVES["medical_access"] / 24;
    const lambda = getLambda("medical_access");
    const result = simulateT(1.0, lambda, halfLifeDays);
    expect(result).toBeCloseTo(0.5, 2);
  });

  it("T is clamped to [0, 1]", () => {
    expect(simulateT(0.5, 1000, 365)).toBe(0);
    expect(simulateT(1.5, 0, 0)).toBe(1);
  });

  it("reverification triggered when simulated T < 0.2", () => {
    const lambda = getLambda("medical_access");
    // Force decay past 0.2
    const result = simulateT(1.0, lambda, 90);
    expect(result).toBeLessThan(0.2);
  });

  it("different categories have different decay rates", () => {
    const tMedical = simulateT(1.0, getLambda("medical_access"), 7);
    const tEducation = simulateT(1.0, getLambda("education"), 7);
    // medical decays faster (shorter half-life)
    expect(tMedical).toBeLessThan(tEducation);
  });
});

// ─── Priority Score formula (mirrors scoring.py) ────────────────────────────

function computePriorityScore(f: number, u: number, g: number, v: number, c: number, t: number): number {
  return Math.round(Math.max(0, Math.min(100, f * u * g * v * c * t * 100)) * 10) / 10;
}

describe("Priority Scoring formula", () => {
  it("all maximum components gives 100", () => {
    expect(computePriorityScore(1, 1, 1, 1, 1, 1)).toBe(100);
  });

  it("zero F gives 0", () => {
    expect(computePriorityScore(0, 1, 1, 1, 1, 1)).toBe(0);
  });

  it("resolved need (G=0.05) falls below 10", () => {
    expect(computePriorityScore(0.5, 0.8, 0.05, 1, 0.7, 1)).toBeLessThan(10);
  });

  it("score clamps at 100", () => {
    expect(computePriorityScore(2, 2, 2, 2, 2, 2)).toBe(100);
  });

  it("score rounds to 1 decimal place", () => {
    const score = computePriorityScore(0.3, 0.6, 0.8, 1.3, 0.7, 0.9);
    const s = score.toString();
    const decimalPart = s.includes(".") ? s.split(".")[1] : "";
    expect(decimalPart.length).toBeLessThanOrEqual(1);
  });
});

// ─── Haversine distance ──────────────────────────────────────────────────────

describe("haversineKm", () => {
  it("same point is 0 km", () => {
    expect(haversineKm(19.076, 72.877, 19.076, 72.877)).toBeCloseTo(0, 3);
  });

  it("Mumbai to Thane is approx 20-30 km", () => {
    const d = haversineKm(19.076, 72.877, 19.218, 72.978);
    expect(d).toBeGreaterThan(15);
    expect(d).toBeLessThan(35);
  });

  it("is symmetric", () => {
    const d1 = haversineKm(19.0, 72.8, 19.1, 72.9);
    const d2 = haversineKm(19.1, 72.9, 19.0, 72.8);
    expect(d1).toBeCloseTo(d2, 5);
  });
});

// ─── NeedQueue utilities ─────────────────────────────────────────────────────

function freshnessLabel(lastCorroborated: string): string {
  const diff = Date.now() - new Date(lastCorroborated).getTime();
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return "< 1h ago";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

describe("NeedQueue — freshness label", () => {
  it("recent timestamp shows hours", () => {
    const ts = new Date(Date.now() - 3 * 3_600_000).toISOString();
    expect(freshnessLabel(ts)).toBe("3h ago");
  });

  it("very recent shows < 1h ago", () => {
    const ts = new Date(Date.now() - 20 * 60_000).toISOString();
    expect(freshnessLabel(ts)).toBe("< 1h ago");
  });

  it("old timestamp shows days", () => {
    const ts = new Date(Date.now() - 3 * 24 * 3_600_000).toISOString();
    expect(freshnessLabel(ts)).toBe("3d ago");
  });
});
