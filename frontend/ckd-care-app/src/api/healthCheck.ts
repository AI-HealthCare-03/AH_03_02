import { api } from "./client";

export type DialysisType = "none" | "hemodialysis" | "peritoneal" | "transplant";

export interface HealthCheckCreateRequest {
  checked_date: string;
  systolic_bp: number;
  diastolic_bp: number;
  fasting_glucose: number;
  creatinine?: number | null;
  total_cholesterol?: number | null;
  hdl_cholesterol?: number | null;
  triglycerides?: number | null;
  weight: number;
  height: number;
  waist_circumference?: number | null;
  dialysis_type?: DialysisType | null;
}

export interface HealthCheckResponse {
  id: number;
  user_id: number;
  checked_date: string;
  systolic_bp: number;
  diastolic_bp: number;
  fasting_glucose: number;
  creatinine: number | null;
  total_cholesterol: number | null;
  hdl_cholesterol: number | null;
  triglycerides: number | null;
  weight: number;
  height: number;
  bmi: number;
  waist_circumference: number | null;
  egfr_estimated: number | null;
  ckd_risk_score: number | null;
  ckd_stage: string | null;
  safety_warning: string | null;
  dialysis_type: DialysisType | null;
  created_at: string;
}

export interface HealthCheckListResponse {
  total: number;
  items: HealthCheckResponse[];
}

// ===== SHAP 리포트 타입 =====

export interface ShapItem1 {
  feature: string;
  value: number;
  shap: number;
  note?: string;
}

export interface LifestyleShapItem {
  feature: string;
  value: number;
  shap: number;
}

export interface PeerDistribution {
  counts: number[];
  edges: number[];
  my_bin: number;
}

export interface LifestyleShap {
  items: LifestyleShapItem[];
  lifestyle_score: number;
  peer_top_pct: number | null;
  peer_relative: string | null;
  peer_distribution?: PeerDistribution | null;
}

export interface ReportResponse {
  health_check_id: number;
  shap_model1: ShapItem1[];
  shap_model2: LifestyleShap | null;
  ai_guide: string;
  recommended_tests?: string[];
  model1_summary?: string;
}

// ===== API =====

export const healthCheckApi = {
  create: (body: HealthCheckCreateRequest) =>
    api.post<HealthCheckResponse>("/health-checks", body),
  list: (limit = 20, offset = 0) =>
    api.get<HealthCheckListResponse>(`/health-checks?limit=${limit}&offset=${offset}`),
  getReport: (id: number) =>
    api.get<ReportResponse>(`/health-checks/${id}/report`),
  delete: (id: number) =>
    api.delete<void>(`/health-checks/${id}`),
};
