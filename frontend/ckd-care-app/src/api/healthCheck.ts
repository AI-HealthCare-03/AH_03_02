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

// ===== 임상 상세 분석 타입 (Phase A 백엔드 추가분) =====

export interface ClinicalItem {
  feature: string;
  label: string;
  desc: string;
  category: string;
  normal_range: string;
  value_text: string;
  status: string;
  status_level: "good" | "info" | "caution" | "warnLight" | "danger";
  direction: "low" | "high" | "normal";
  disease_low: string;
  disease_high: string;
}

export interface LifestyleItem {
  feature: string;
  label: string;
  normal_range: string;
  value_text: string;
  status: string;
  status_level: "good" | "info" | "caution" | "warnLight" | "danger";
  group: "improve" | "maintain";
  action: string;
  domain: string; // diet | exercise | etc (Phase B)
}

// ===== 생활습관 도메인 분리 타입 (Phase B) =====

export interface LifestyleDomainSummary {
  domain: string;
  domain_label: string;
  improve_count: number;
  summary: string;
}

export interface ReportMeta {
  group: string | null;
  group_title: string;
  grade: string;
  score: number | null;
  group_message: string;
  age: number | null;
  gender: string | null;
  conditions: string[];
  family_history: string[];
  peer_top_pct: number | null;
  peer_relative: string | null;
}

export interface ReportResponse {
  health_check_id: number;
  shap_model1: ShapItem1[];
  shap_model2: LifestyleShap | null;
  ai_guide: string;
  recommended_tests?: string[];
  model1_summary?: string;
  clinical_items?: ClinicalItem[];
  lifestyle_items?: LifestyleItem[];
  lifestyle_domain_summary?: LifestyleDomainSummary[]; // 도메인별 생활습관 요약 (Phase B)
  report_meta?: ReportMeta | null;
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
