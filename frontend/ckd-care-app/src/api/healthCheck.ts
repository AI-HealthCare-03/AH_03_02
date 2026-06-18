import { api, BASE, getToken } from "./client";

export type DialysisType = "none" | "hemodialysis" | "peritoneal" | "transplant";
export type UrineResult = "POSITIVE" | "NEGATIVE";

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
  // 신규 검진 항목 (ML 모델 입력에 포함)
  ldl_cholesterol?: number | null;
  hemoglobin?: number | null;
  ast?: number | null;
  alt?: number | null;
  urine_protein?: UrineResult | null;
  urine_glucose?: UrineResult | null;
  // dialysis_type 제거 — CKD 진단·투석 종류는 문진(LifestyleSurvey)이 단일 진실
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
  ldl_cholesterol: number | null;
  hemoglobin: number | null;
  ast: number | null;
  alt: number | null;
  urine_protein: UrineResult | null;
  urine_glucose: UrineResult | null;
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
  side?: "improve" | "maintain" | "exclude";
}

export interface LifestyleShapItem {
  feature: string;
  value: number;
  shap: number;
  side?: "improve" | "maintain";
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

// ===== OCR 응답 타입 =====
export interface OCRField {
  text: string;
  confidence: number; // 0~1
}

export interface OCRMappedField {
  value: number;
  confidence: number;
  source_text: string;
}

// 자동 매핑되는 검진 필드 (ManualInputPage prefill용 필드명과 일치)
// LDL은 시스템에서 사용 안 함 → OCR 매핑에서 제외
export type OCRMappedKey =
  | "fasting_glucose"
  | "creatinine"
  | "hdl_cholesterol"
  | "total_cholesterol"
  | "triglycerides"
  | "systolic_bp"
  | "diastolic_bp"
  | "height"
  | "weight"
  | "waist_circumference";

export interface OCRLine {
  text: string;
  confidence: number;
}

export interface OCRResponse {
  engine: "clova" | "stub";
  filename: string;
  fields: OCRField[];
  lines?: OCRLine[];
  mapped?: Partial<Record<OCRMappedKey, OCRMappedField>>;
  low_confidence_count: number;
  page_count?: number;
  page_errors?: string[];
}

export const healthCheckApi = {
  create: (body: HealthCheckCreateRequest) =>
    api.post<HealthCheckResponse>("/health-checks", body),
  list: (limit = 20, offset = 0) =>
    api.get<HealthCheckListResponse>(`/health-checks?limit=${limit}&offset=${offset}`),
  getReport: (id: number) =>
    api.get<ReportResponse>(`/health-checks/${id}/report`),
  delete: (id: number) =>
    api.delete<void>(`/health-checks/${id}`),
  update: (id: number, body: HealthCheckCreateRequest) =>
    api.patch<HealthCheckResponse>(`/health-checks/${id}`, body),
  deleteAll: () =>
    api.delete<{ deleted_count: number }>("/health-checks"),
  ocrExtract: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.postForm<OCRResponse>("/health-checks/ocr", fd);
  },
  downloadPdf: async (id: number): Promise<void> => {
    const token = getToken();
    const res = await fetch(`${BASE}/health-checks/${id}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`PDF 다운로드 실패 (${res.status}): ${body.slice(0, 200)}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `건강리포트_${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
