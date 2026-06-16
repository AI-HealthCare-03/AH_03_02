import { api } from "./client";

export interface AdminUserRow {
  id: number;
  email_masked: string;
  name_masked: string;
  gender: string;
  is_active: boolean;
  is_admin: boolean;
  email_verified: boolean;
  last_login: string | null;
  created_at: string;
}

export interface AdminUserListResponse {
  total: number;
  items: AdminUserRow[];
}

export interface AdminUserDetail {
  id: number;
  email_masked: string;
  name_masked: string;
  phone_masked: string;
  gender: string;
  age: number;
  is_active: boolean;
  is_admin: boolean;
  email_verified: boolean;
  failed_login_count: number;
  locked_until: string | null;
  last_login: string | null;
  created_at: string;
  latest_health_summary: {
    checked_date: string;
    systolic_bp_category: string;
    fasting_glucose_category: string;
    egfr_category: string;
    ckd_stage: string | null;
  } | null;
}

export interface AdminChallenge {
  id: number;
  name: string;
  category: string;
  description: string;
  duration_days: number;
  track: string;
  stage: number;
  is_active: boolean;
  created_at: string;
}

export interface AdminChallengeListResponse {
  total: number;
  items: AdminChallenge[];
}

export interface SignupBucket {
  date: string;
  count: number;
}

export interface AdminStatsSummary {
  total_users: number;
  active_users: number;
  email_verified_users: number;
  new_users_7d: number;
  new_users_30d: number;
  total_health_checks: number;
  total_lifestyle_surveys: number;
  total_user_challenges: number;
  total_checkins: number;
  challenges_active_catalog: number;
  ckd_stage_distribution: Record<string, number>;
  challenges_by_category: Record<string, number>;
  signups_last_30d: SignupBucket[];
}

export interface AdminActionLogRow {
  id: number;
  admin_user_id: number;
  action: string;
  target_type: string;
  target_id: number;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface AdminActionLogListResponse {
  total: number;
  items: AdminActionLogRow[];
}

export interface AdminSafetyEventRow {
  id: number;
  user_id: number;
  user_email_masked: string;
  health_check_id: number | null;
  event_type: "BP_CRISIS" | "GLUCOSE_CRISIS" | "EGFR_CRISIS";
  value: number;
  message: string;
  acknowledged: boolean;
  acknowledged_by: number | null;
  acknowledged_at: string | null;
  created_at: string;
}

export interface AdminSafetyEventListResponse {
  total: number;
  items: AdminSafetyEventRow[];
}

export interface ImpersonateResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  target: { id: number; name_masked: string };
}

export const adminApi = {
  listUsers: (q?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q) params.set("q", q);
    return api.get<AdminUserListResponse>(`/admin/users?${params}`);
  },
  getUser: (id: number) => api.get<AdminUserDetail>(`/admin/users/${id}`),
  activateUser: (id: number, reason?: string) =>
    api.patch<void>(`/admin/users/${id}/activate`, { reason: reason ?? null }),
  deactivateUser: (id: number, reason: string) =>
    api.patch<void>(`/admin/users/${id}/deactivate`, { reason }),
  forceVerifyEmail: (id: number, reason?: string) =>
    api.patch<void>(`/admin/users/${id}/verify-email`, { reason: reason ?? null }),

  listChallenges: (limit = 50, offset = 0) =>
    api.get<AdminChallengeListResponse>(`/admin/challenges?limit=${limit}&offset=${offset}`),
  createChallenge: (body: {
    name: string; category: string; description: string;
    duration_days: number; track: string; stage?: number;
  }) => api.post<AdminChallenge>("/admin/challenges", body),
  updateChallenge: (id: number, body: Partial<{
    name: string; description: string; duration_days: number; is_active: boolean;
  }>) => api.patch<AdminChallenge>(`/admin/challenges/${id}`, body),
  deactivateChallenge: (id: number, reason?: string) =>
    api.delete<void>(`/admin/challenges/${id}${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`),

  statsSummary: () => api.get<AdminStatsSummary>("/admin/stats/summary"),

  listLogs: (params: {
    limit?: number; offset?: number;
    action?: string; target_type?: string;
    admin_user_id?: number; since?: string; until?: string;
  } = {}) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    if (params.action) qs.set("action", params.action);
    if (params.target_type) qs.set("target_type", params.target_type);
    if (params.admin_user_id) qs.set("admin_user_id", String(params.admin_user_id));
    if (params.since) qs.set("since", params.since);
    if (params.until) qs.set("until", params.until);
    return api.get<AdminActionLogListResponse>(`/admin/logs?${qs}`);
  },

  listSafetyEvents: (params: {
    limit?: number; offset?: number;
    event_type?: "BP_CRISIS" | "GLUCOSE_CRISIS" | "EGFR_CRISIS";
    only_unacknowledged?: boolean;
  } = {}) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    if (params.event_type) qs.set("event_type", params.event_type);
    if (params.only_unacknowledged) qs.set("only_unacknowledged", "true");
    return api.get<AdminSafetyEventListResponse>(`/admin/safety-events?${qs}`);
  },
  acknowledgeSafety: (id: number, note?: string) =>
    api.patch<void>(`/admin/safety-events/${id}/acknowledge`, { note: note ?? null }),

  impersonate: (id: number) =>
    api.post<ImpersonateResponse>(`/admin/users/${id}/impersonate`, {}),
};
