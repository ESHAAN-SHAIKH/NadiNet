// Typed API client using TanStack Query hooks
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  Need, Signal, Volunteer, Reporter, Task, KinshipGraph,
  DashboardStats, HeatmapCell, SignalLogEntry, CandidateResult,
} from "@/types";

const BASE = "/api/v1";

async function fetchJSON<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

// ─── Dashboard ───────────────────────────────────────────────

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ["dashboard", "stats"],
    queryFn: () => fetchJSON(`${BASE}/dashboard/stats`),
    refetchInterval: 30_000,
  });
}

export function useHeatmap() {
  return useQuery<HeatmapCell[]>({
    queryKey: ["dashboard", "heatmap"],
    queryFn: () => fetchJSON(`${BASE}/dashboard/heatmap`),
    refetchInterval: 60_000,
  });
}

export function useSignalLog(limit = 100) {
  return useQuery<SignalLogEntry[]>({
    queryKey: ["dashboard", "signal-log", limit],
    queryFn: () => fetchJSON(`${BASE}/dashboard/signal-log?limit=${limit}`),
    refetchInterval: 15_000,
  });
}

export function useKinshipGraph() {
  return useQuery<KinshipGraph>({
    queryKey: ["dashboard", "kinship"],
    queryFn: () => fetchJSON(`${BASE}/dashboard/kinship`),
    refetchInterval: 60_000,
  });
}

// ─── Needs ───────────────────────────────────────────────────

export function useNeeds(status = "active") {
  return useQuery<Need[]>({
    queryKey: ["needs", status],
    queryFn: () => fetchJSON(`${BASE}/needs?status=${status}`),
    refetchInterval: 15_000,
  });
}

export function useNeed(id: string) {
  return useQuery<Need>({
    queryKey: ["needs", id],
    queryFn: () => fetchJSON(`${BASE}/needs/${id}`),
    enabled: !!id,
  });
}

export function useCandidates(needId: string, skills: string[] = [], count = 1) {
  const skillParam = skills.join(",");
  return useQuery<CandidateResult>({
    queryKey: ["needs", needId, "candidates", skillParam, count],
    queryFn: () => fetchJSON(`${BASE}/needs/${needId}/candidates?skills=${skillParam}&count=${count}`),
    enabled: !!needId,
  });
}

export function usePromoteNeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ needId, justification }: { needId: string; justification?: string }) =>
      fetchJSON(`${BASE}/needs/${needId}/promote`, {
        method: "POST",
        body: JSON.stringify({ justification }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["needs"] }),
  });
}

export function useUpdateNeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ needId, data }: { needId: string; data: Partial<Need> }) =>
      fetchJSON(`${BASE}/needs/${needId}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["needs"] }),
  });
}

// ─── Volunteers ──────────────────────────────────────────────

export function useVolunteers(isAvailable?: boolean) {
  const param = isAvailable !== undefined ? `?is_available=${isAvailable}` : "";
  return useQuery<Volunteer[]>({
    queryKey: ["volunteers", isAvailable],
    queryFn: () => fetchJSON(`${BASE}/volunteers${param}`),
    refetchInterval: 30_000,
  });
}

export function useUpdateAvailability() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_available }: { id: string; is_available: boolean }) =>
      fetchJSON(`${BASE}/volunteers/${id}/availability?is_available=${is_available}`, { method: "PATCH" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["volunteers"] }),
  });
}

// ─── Reporters ───────────────────────────────────────────────

export function useReporters() {
  return useQuery<Reporter[]>({
    queryKey: ["reporters"],
    queryFn: () => fetchJSON(`${BASE}/reporters`),
  });
}

export function useUpdateReporterTrust() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, trust_score, justification }: { id: string; trust_score: number; justification: string }) =>
      fetchJSON(`${BASE}/reporters/${id}/trust`, {
        method: "PATCH",
        body: JSON.stringify({ trust_score, justification }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reporters"] }),
  });
}

// ─── Tasks ───────────────────────────────────────────────────

export function useTasks(status?: string) {
  const param = status ? `?status=${status}` : "";
  return useQuery<Task[]>({
    queryKey: ["tasks", status],
    queryFn: () => fetchJSON(`${BASE}/tasks${param}`),
    refetchInterval: 15_000,
  });
}

// ─── Dispatch ────────────────────────────────────────────────

export function useDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ need_id, volunteer_ids }: { need_id: string; volunteer_ids: string[] }) =>
      fetchJSON(`${BASE}/dispatch`, {
        method: "POST",
        body: JSON.stringify({ need_id, volunteer_ids, send_whatsapp: true }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["needs"] });
    },
  });
}
