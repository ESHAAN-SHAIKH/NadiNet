// Shared TypeScript types for NadiNet

export type NeedCategory =
  | "medical_access" | "nutrition" | "elderly_care" | "water_sanitation"
  | "shelter" | "education" | "mental_health" | "livelihood" | "other";

export type NeedStatus = "active" | "resolved" | "archived";
export type SignalState = "watch" | "active" | "archived";
export type TaskStatus = "pending" | "accepted" | "declined" | "complete";
export type Resolution = "resolved" | "partial" | "unresolved";

export interface Need {
  id: string;
  zone_id: string;
  need_category: NeedCategory;
  priority_score: number;
  f_score: number | null;
  u_score: number | null;
  g_score: number | null;
  v_score: number | null;
  c_score: number | null;
  t_score: number | null;
  lambda_per_hour: number | null;
  source_count: number;
  population_est: number | null;
  status: NeedStatus;
  first_reported: string;
  last_corroborated: string;
  created_at: string;
  updated_at: string;
}

export interface Signal {
  id: string;
  reporter_id: string | null;
  source_channel: string;
  zone_id: string;
  need_category: NeedCategory;
  urgency: number | null;
  population_est: number | null;
  raw_text: string | null;
  confidence: number | null;
  state: SignalState;
  collected_at: string;
  synced_at: string;
  corroboration_id: string | null;
}

export interface Volunteer {
  id: string;
  name: string;
  phone: string;
  skills: string[];
  languages: string[];
  has_transport: boolean;
  zone_id: string | null;
  trust_score: number;
  completion_rate: number;
  is_available: boolean;
  availability_schedule: Record<string, { start: string; end: string }[]> | null;
  created_at: string;
}

export interface Reporter {
  id: string;
  phone: string;
  name: string | null;
  trust_score: number;
  reports_filed: number;
  reports_verified: number;
  decay_modifier: number;
  created_at: string;
}

export interface Task {
  id: string;
  need_id: string;
  volunteer_id: string;
  status: TaskStatus;
  dispatched_at: string;
  accepted_at: string | null;
  completed_at: string | null;
  kinship_bonus: boolean;
}

export interface KinshipNode {
  id: string;
  name: string;
  initials: string;
  zone_id: string | null;
  skills: string[];
  trust_score: number;
  completion_rate: number;
  is_available: boolean;
}

export interface KinshipEdge {
  id: string;
  source: string;
  target: string;
  co_deployments: number;
  quality_score: number;
  last_deployed: string;
}

export interface KinshipGraph {
  nodes: KinshipNode[];
  edges: KinshipEdge[];
}

export interface DashboardStats {
  total_active_needs: number;
  total_watch_signals: number;
  total_volunteers: number;
  available_volunteers: number;
  kinship_matches_today: number;
  avg_decay_age_days: number;
  needs_needing_reverification: number;
}

export interface HeatmapCell {
  need_category: string;
  source_channel: string;
  count: number;
}

export interface SignalLogEntry {
  id: string;
  event_type: string;
  timestamp: string;
  description: string;
  metadata: Record<string, unknown>;
}

export interface Candidate {
  id: string;
  name: string;
  phone: string;
  skills: string[];
  zone_id: string | null;
  trust_score: number;
  completion_rate: number;
  is_available: boolean;
  pass2_score: number;
  is_recommended: boolean;
}

export interface CandidateResult {
  need_id: string;
  candidates: Candidate[];
  recommended_ids: string[];
  kinship_bonus: boolean;
  pool_size: number;
}
